from typing import Mapping, Dict, Any, Optional, List
from werkzeug.wrappers import Request, Response
from dify_plugin import Endpoint
import json
import uuid
import asyncio
import inspect
from functools import wraps

# 全局工具注册
class ToolDef:
    """工具定义类，用于描述和执行工具"""
    def __init__(self, func, name=None, description=None):
        self.func = func
        self.name = name or func.__name__
        self.description = description or func.__doc__
        self.signature = inspect.signature(func)
        
    def get_schema(self) -> Dict[str, Any]:
        """生成工具的 JSON Schema"""
        properties = {}
        required = []
        
        for name, param in self.signature.parameters.items():
            if name == 'self':
                continue
                
            param_type = "string"
            if param.annotation != inspect.Parameter.empty:
                if param.annotation == int or param.annotation == float:
                    param_type = "number"
                elif param.annotation == bool:
                    param_type = "boolean"
            
            prop = {"type": param_type}
            
            # 获取参数描述
            if self.description:
                for line in self.description.split('\n'):
                    if f"{name}:" in line or f"{name} :" in line:
                        prop["description"] = line.split(':', 1)[1].strip()
            
            properties[name] = prop
            
            # 如果参数没有默认值，则为必填
            if param.default == inspect.Parameter.empty:
                required.append(name)
        
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": properties,
                "required": required
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "output": {
                        "type": "string",
                        "description": "The result of the function call"
                    }
                }
            }
        }

    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """执行工具，同步方式处理异步函数"""
        try:
            result = self.func(**args)
            if inspect.iscoroutine(result):
                # 如果是协程，使用已存在的事件循环运行它，而不是创建新的循环
                try:
                    # 尝试获取当前事件循环
                    loop = asyncio.get_event_loop()
                    # 如果事件循环已经运行，直接使用同步方式调用
                    if loop.is_running():
                        # 使用一个新进程或线程来运行协程
                        import concurrent.futures
                        with concurrent.futures.ThreadPoolExecutor() as executor:
                            future = executor.submit(lambda: asyncio.run(self.func(**args)))
                            result = future.result()
                    else:
                        result = loop.run_until_complete(result)
                except RuntimeError:
                    # 如果出现RuntimeError可能是没有事件循环，创建一个新的
                    result = asyncio.run(self.func(**args))
            return {"output": result}
        except Exception as e:
            return {"output": f"Error: {str(e)}"}

class ToolRegistry:
    """工具注册表，管理所有可用工具"""
    def __init__(self):
        self.tools = {}
        
    def tool(self, func=None, name=None, description=None):
        """工具注册装饰器"""
        def decorator(f):
            tool_def = ToolDef(f, name=name, description=description)
            self.tools[tool_def.name] = tool_def
            
            @wraps(f)
            def wrapper(*args, **kwargs):
                return f(*args, **kwargs)
            return wrapper
            
        if func is None:
            return decorator
        return decorator(func)
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """获取所有工具定义"""
        return [tool.get_schema() for tool in self.tools.values()]
    
    def execute_tool(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """执行指定名称的工具，非异步方式"""
        if name not in self.tools:
            raise ValueError(f"Tool {name} not found")
        return self.tools[name].execute(args)

# 创建全局工具注册表
tool_registry = ToolRegistry()

class DifyappAsMcpServerEndpoint(Endpoint):
    """Dify MCP 服务器端点 - 处理 POST 请求"""
    def __init__(self, session=None):
        super().__init__(session=session)
        # 移除显式的事件循环创建，改为按需使用
        
        # 注册工具
        # 注意：这里使用全局 tool_registry，所以工具只会注册一次
        if not tool_registry.tools:
            self._register_tools()
    
    def _register_tools(self):
        """注册 Dify workflow 工具"""
        @tool_registry.tool
        async def dify_workflow(title: str, language: str = "English") -> str:
            """执行 Dify workflow 并返回结果
            
            Args:
                title: 要处理的标题或主题
                language: 输出使用的语言 (默认英文)
            """
            try:
                # 获取当前应用 ID
                app_id = getattr(self, 'current_app_id', "")
                
                if not app_id:
                    return "Error: App ID not configured"
                
                # 调用 Dify workflow
                workflow_response = self.session.app.workflow.invoke(
                    app_id=app_id,
                    inputs={"title": title, "language": language},
                    response_mode="blocking"
                )
                
                # 从响应中提取输出
                output = workflow_response.get("data", {}).get("outputs", {}).get("output", "")
                if not output:
                    output = "Workflow completed but returned no output"
                    
                return output
            except Exception as e:
                return f"Error executing workflow: {str(e)}"
    
    def _invoke(self, r: Request, values: Mapping, settings: Mapping) -> Response:
        """请求处理入口点"""
        # 保存当前应用 ID，供工具使用
        self.current_app_id = settings.get('app_id', {}).get("app_id", "")
        
        # 处理 POST 请求 (JSON-RPC 或直接调用)
        if r.method == "POST" and r.is_json:
            data = r.get_json()
            if "jsonrpc" in data:
                return self._handle_jsonrpc(r, data, settings)
            else:
                return self._handle_direct_call(r, data, settings)
        else:
            # 不支持的请求
            return Response(
                "Unsupported request type",
                status=400,
                content_type="text/plain"
            )
    
    def _handle_jsonrpc(self, r: Request, data: Dict, settings: Mapping) -> Response:
        """处理 JSON-RPC 请求"""
        method = data.get("method")
        params = data.get("params", {})
        req_id = data.get("id")
        
        try:
            if method == "initialize":
                result = self._handle_initialize(params, settings)
            elif method == "list_tools":
                result = self._handle_list_tools(params, settings)
            elif method == "call_tool":
                # 不再使用run_until_complete，直接调用非异步版本
                result = self._handle_call_tool(params, settings)
            else:
                return self._jsonrpc_error(req_id, -32601, f"Method '{method}' not found")
            
            return self._jsonrpc_success(req_id, result)
        except Exception as e:
            return self._jsonrpc_error(req_id, -32000, str(e))
    
    def _handle_initialize(self, params: Dict, settings: Mapping) -> Dict:
        """处理 initialize 方法"""
        server_name = settings.get("server_name", "Dify Workflow Server")
        server_desc = settings.get("server_description", "Access Dify workflows via MCP")
        
        return {
            "name": server_name,
            "description": server_desc,
            "schema_version": "mcp-0.7.0",
            "protocol_version": "0.7.0",
            "server_source": "dify-plugin"
        }
    
    def _handle_list_tools(self, params: Dict, settings: Mapping) -> Dict:
        """处理 list_tools 方法"""
        app_id = settings.get('app_id', {}).get("app_id", "")
        if not app_id:
            raise ValueError("App ID not configured")
        
        # 使用工具注册表获取工具列表
        tools = tool_registry.get_tools()
        return {"tools": tools}
    
    def _handle_call_tool(self, params: Dict, settings: Mapping) -> Dict:
        """处理 call_tool 方法 - 已修改为非异步方法"""
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        
        if not tool_name:
            raise ValueError("Missing tool name")
        
        # 使用非异步方式执行工具
        return tool_registry.execute_tool(tool_name, arguments)
    
    def _handle_direct_call(self, r: Request, data: Dict, settings: Mapping) -> Response:
        """处理直接 workflow 调用（保持兼容）"""
        try:
            # 提取请求数据并准备工作流输入
            workflow_inputs = {}
            for key, value in data.get("responseValues", {}).items():
                workflow_inputs[key] = value.get("value")
            
            app_id = settings.get('app_id', {}).get("app_id", "")
            
            # 调用 Dify 工作流
            workflow_response = self.session.app.workflow.invoke(
                app_id=app_id,
                inputs=workflow_inputs,
                response_mode="blocking",
            )

            return Response(
                json.dumps({
                    "status": "success",
                    "workflow_response": workflow_response
                }),
                status=200,
                content_type="application/json"
            )
        except Exception as e:
            return Response(
                json.dumps({
                    "error": str(e)
                }),
                status=500,
                content_type="application/json"
            )
    
    # 工具函数
    
    def _jsonrpc_success(self, req_id: Any, result: Any) -> Response:
        """构建 JSON-RPC 成功响应"""
        return Response(
            json.dumps({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": result
            }),
            status=200,
            content_type="application/json"
        )
    
    def _jsonrpc_error(self, req_id: Any, code: int, message: str) -> Response:
        """构建 JSON-RPC 错误响应"""
        return Response(
            json.dumps({
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": code,
                    "message": message
                }
            }),
            status=200,  # JSON-RPC 总是返回 200，错误在响应内容中
            content_type="application/json"
        )
