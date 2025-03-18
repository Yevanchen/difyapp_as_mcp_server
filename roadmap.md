# Dify Endpoint 中实现 MCP 服务器的架构设计

## 总体 Roadmap

### 阶段 1: 基础 MCP 功能实现
- 设计端点架构，支持 GET 和 POST 请求
- 实现核心 JSON-RPC 处理
- 适配 Werkzeug 与 MCP SDK (如可能)

### 阶段 2: SSE 支持与用户体验优化
- 在端点限制下实现基础 SSE 功能
- 添加进度通知和心跳机制
- 优化错误处理和重试机制

### 阶段 3: 高级功能与生产化
- 完善工具定义和文档
- 添加配置选项和自定义功能
- 提高安全性和性能

## 架构设计

由于 Dify 不支持 `ANY` 类型的端点，需要创建两个独立端点来处理不同类型的请求：

```
/difyapp_as_mcp_server    (GET) -> 处理 SSE 连接和说明页面
/difyapp_as_mcp_server    (POST) -> 处理 JSON-RPC 请求
```

### 端点结构定义

```yaml
# GET 端点配置
path: "/difyapp_as_mcp_server"
method: "GET"
extra:
  python:
    source: "endpoints/difyapp_as_mcp_server.py"

# POST 端点配置
path: "/difyapp_as_mcp_server"
method: "POST"
extra:
  python:
    source: "endpoints/difyapp_as_mcp_server.py"
```

## MCP SDK 与 Werkzeug 适配方案

### 挑战分析

1. **MCP SDK 设计为独立服务器**：
   - 通常由 SDK 控制整个 HTTP 服务器
   - 假设可以完全控制请求/响应生命周期

2. **Dify Endpoint 限制**：
   - 只是 HTTP 处理器，不是完整服务器
   - 没有控制服务器生命周期的权限
   - 无法直接使用 SDK 的 `run()` 方法

### 适配策略

采用**核心功能提取**策略：从 MCP SDK 中提取关键功能，而不是直接使用其服务器组件。

1. **引入 SDK 作为工具库**：
   ```python
   from mcp.server.fastmcp import FastMCP
   from mcp.server.tool_registry import ToolRegistry
   ```

2. **使用 SDK 注册工具**，但自行处理请求：
   ```python
   # 在类外创建全局工具注册表
   tool_registry = ToolRegistry()
   
   class DifyappAsMcpServerEndpoint(Endpoint):
       def __init__(self):
           super().__init__()
           # 工具定义，使用 SDK 的工具注册功能
           self._setup_tools(tool_registry)
       
       def _setup_tools(self, registry):
           @registry.tool
           async def dify_workflow(title: str, language: str = "English") -> str:
               """执行 Dify workflow 并返回结果"""
               # 实现...
   ```

3. **手动路由并调用 SDK 功能**：
   ```python
   def _invoke(self, r: Request, values: Mapping, settings: Mapping) -> Response:
       if r.method == "GET":
           return self._handle_get(r, settings)
       elif r.method == "POST" and r.is_json:
           data = r.get_json()
           if "jsonrpc" in data:
               return self._handle_jsonrpc(r, data, settings)
           else:
               return self._handle_direct_call(r, data, settings)
   ```

## SSE 实现方案

在 Dify Endpoint 中实现 SSE 确实存在挑战，但可以通过以下策略实现基础 SSE 功能：

### 1. 生成器响应模式

```python
def _handle_get(self, r: Request, settings: Mapping) -> Response:
    """处理 GET 请求 - 支持 SSE 和普通页面"""
    if r.headers.get("Accept") == "text/event-stream":
        return self._handle_sse_connection(r, settings)
    else:
        return self._serve_html_page(r, settings)

def _handle_sse_connection(self, r: Request, settings: Mapping) -> Response:
    """处理 SSE 连接请求"""
    connection_id = str(uuid.uuid4())
    
    def generate():
        # 1. 连接确认
        yield f"data: {{\"type\": \"connection\", \"id\": \"{connection_id}\"}}\n\n"
        
        # 2. 心跳机制 (有限次数，因为无法无限运行)
        for _ in range(12):  # 最多运行3分钟
            time.sleep(15)
            yield "data: {\"type\": \"ping\"}\n\n"
    
    return Response(
        generate(),
        status=200,
        content_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive"
        }
    )
```

### 2. 有限心跳模式

由于 Dify Endpoint 请求处理有时间限制，无法永久保持连接。采用有限心跳策略：

- 限制心跳次数，例如最多发送12次（约3分钟）
- 客户端检测到连接关闭后会自动重连
- 每次重连获得新的连接 ID

### 3. 状态管理权衡

- 使用连接级别变量而不是全局变量
- 放弃支持全局连接表和长期状态管理
- 专注于提供"最小可行"的 SSE 体验

## 客户端配置方案

客户端应配置为使用 GET 端点：

```json
{
  "mcpServers": {
    "dify-workflow": {
      "url": "https://your-dify-instance.com/difyapp_as_mcp_server"
    }
  }
}
```

当指定 URL 时，MCP 客户端会自动:
- 向该 URL 发送 GET 请求建立 SSE 连接
- 向同一 URL 发送 POST 请求进行 JSON-RPC 调用

## 核心代码实现结构

以下是完整的架构设计实现方案：

```python
from typing import Mapping, Dict, Any, Optional
from werkzeug import Request, Response
from dify_plugin import Endpoint
import json
import uuid
import time
import asyncio
import inspect
from functools import wraps

# 全局工具注册
class ToolDef:
    def __init__(self, func, name=None, description=None):
        self.func = func
        self.name = name or func.__name__
        self.description = description or func.__doc__
        self.signature = inspect.signature(func)
        
    def get_schema(self):
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

    async def execute(self, args):
        """执行工具"""
        try:
            result = self.func(**args)
            if inspect.iscoroutine(result):
                result = await result
            return {"output": result}
        except Exception as e:
            return {"output": f"Error: {str(e)}"}

class ToolRegistry:
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
    
    def get_tools(self):
        """获取所有工具定义"""
        return [tool.get_schema() for tool in self.tools.values()]
    
    async def execute_tool(self, name, args):
        """执行指定名称的工具"""
        if name not in self.tools:
            raise ValueError(f"Tool {name} not found")
        return await self.tools[name].execute(args)

# 创建全局工具注册表
tool_registry = ToolRegistry()

class DifyappAsMcpServerEndpoint(Endpoint):
    def __init__(self):
        super().__init__()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
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
                # 暂存 self 和 settings，稍后使用
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
        
        if r.method == "GET":
            # 处理 GET 请求 (SSE 或 HTML)
            if r.headers.get("Accept") == "text/event-stream":
                return self._handle_sse_connection(r, settings)
            else:
                return self._serve_html_page(r, settings)
        elif r.method == "POST" and r.is_json:
            # 处理 POST 请求 (JSON-RPC 或直接调用)
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
    
    # GET 相关处理
    
    def _serve_html_page(self, r: Request, settings: Mapping) -> Response:
        """返回 HTML 说明页面"""
        server_name = settings.get("server_name", "Dify Workflow Server")
        server_desc = settings.get("server_description", "Access Dify workflows via MCP")
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{server_name}</title>
            <style>
                body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
                h1 {{ color: #2c3e50; }}
                code {{ background: #f8f8f8; padding: 2px 5px; border-radius: 3px; }}
                pre {{ background: #f8f8f8; padding: 10px; border-radius: 5px; overflow-x: auto; }}
            </style>
        </head>
        <body>
            <h1>{server_name}</h1>
            <p>{server_desc}</p>
            
            <h2>MCP Server Information</h2>
            <p>This endpoint implements the Model Context Protocol (MCP), allowing AI models to interact with Dify workflows.</p>
            
            <h2>Available Tools</h2>
            <p>This server exposes the following tools:</p>
            <ul>
                <li><strong>dify_workflow</strong>: Execute Dify workflows with custom inputs</li>
            </ul>
            
            <h2>Integration Instructions</h2>
            <p>To connect an MCP client (like Claude Desktop):</p>
            <ol>
                <li>Add this URL to your MCP client configuration</li>
                <li>The client will automatically discover available tools</li>
                <li>Start using the tools through natural language commands</li>
            </ol>
            
            <h2>Example Configuration</h2>
            <p>For Claude Desktop, add this to <code>claude_desktop_config.json</code>:</p>
            <pre>{{
  "mcpServers": {{
    "dify-service": {{
      "url": "{r.url_root}{r.path.lstrip('/')}"
    }}
  }}
}}</pre>
        </body>
        </html>
        """
        
        return Response(
            html,
            status=200,
            content_type="text/html"
        )
    
    def _handle_sse_connection(self, r: Request, settings: Mapping) -> Response:
        """处理 SSE 连接请求 - 有限心跳模式"""
        connection_id = str(uuid.uuid4())
        
        def generate():
            # 1. 发送连接确认
            yield f"data: {{\"type\": \"connection\", \"id\": \"{connection_id}\"}}\n\n"
            
            # 可选：发送初始化和工具列表 (有些客户端期望这个)
            tools_json = json.dumps({"type": "tools", "tools": tool_registry.get_tools()})
            yield f"data: {tools_json}\n\n"
            
            # 2. 心跳机制 (有限次数，因为无法无限运行)
            # 假设 Dify Endpoint 请求最多可处理 5 分钟 = 300 秒
            # 每 15 秒发送一次心跳，共 20 次
            for _ in range(20):
                time.sleep(15)
                yield "data: {\"type\": \"ping\"}\n\n"
        
        return Response(
            generate(),
            status=200,
            content_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive"
            }
        )
    
    # POST 相关处理
    
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
                result = self.loop.run_until_complete(self._handle_call_tool(params, settings))
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
    
    async def _handle_call_tool(self, params: Dict, settings: Mapping) -> Dict:
        """处理 call_tool 方法"""
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        
        if not tool_name:
            raise ValueError("Missing tool name")
        
        # 使用工具注册表执行工具
        return await tool_registry.execute_tool(tool_name, arguments)
    
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
```

## 设计权衡与考虑

### 1. MCP SDK 使用方式的权衡

**选择**: 提取 SDK 核心功能，不直接使用其服务器组件

**理由**:
- Dify Endpoint 无法运行完整 SDK 服务器
- SDK 的工具注册和模式生成仍然有价值
- 手动实现协议处理比修改 SDK 更简单可控

### 2. SSE 实现策略权衡

**选择**: 有限心跳模式 + 生成器响应

**理由**:
- 完全符合 HTTP/SSE 标准，客户端兼容性最佳
- 在 Dify Endpoint 限制下提供最佳用户体验
- 不需要维护服务器状态，每个请求独立处理

### 3. 工具注册与执行权衡

**选择**: 全局工具注册表 + 实例级执行

**理由**:
- 避免每次请求重新注册工具（效率）
- 保持工具执行需要的上下文（会话和应用 ID）
- 兼容 Dify Endpoint 实例化模型

### 4. 错误处理策略

**选择**: JSON-RPC 标准错误 + 简洁错误信息

**理由**:
- 遵循 MCP 协议规范，保持兼容性
- 提供有用但不过度详细的错误信息
- 错误状态码保持为 200，符合 JSON-RPC 标准

## 推荐实施路径

1. **核心功能先行**：先实现 GET/POST 端点和基本 JSON-RPC 处理
2. **添加有限 SSE**：实现基础 SSE 连接和心跳机制
3. **工具模板化**：完善工具定义和文档自动生成
4. **测试与优化**：确保与主流 MCP 客户端兼容

此架构设计在 Dify Endpoint 限制下提供了最佳 MCP 实现方案，平衡了功能完整性和实现复杂度，让 Dify Workflow 可以作为 MCP 工具被 Claude 等客户端使用。
