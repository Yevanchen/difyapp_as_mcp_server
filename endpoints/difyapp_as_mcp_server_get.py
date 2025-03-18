from typing import Mapping, Dict, Any
from werkzeug.wrappers import Request, Response
from dify_plugin import Endpoint
import json
import uuid
import time

# 导入 POST 端点的工具注册表，确保工具信息一致
try:
    from .difyapp_as_mcp_server_post import tool_registry
except ImportError:
    # 当模块直接测试时可能需要这样导入
    try:
        from difyapp_as_mcp_server_post import tool_registry
    except ImportError:
        # 创建一个空的工具注册表作为后备
        from .difyapp_as_mcp_server_post import ToolRegistry
        tool_registry = ToolRegistry()

class DifyappAsMcpServerGetEndpoint(Endpoint):
    """Dify MCP 服务器端点 - 处理 GET 请求"""
    
    def __init__(self, session=None):
        super().__init__(session=session)
    
    def _invoke(self, r: Request, values: Mapping, settings: Mapping) -> Response:
        """请求处理入口点"""
        try:
            if r.method == "GET":
                # 处理 GET 请求 (SSE 或 HTML)
                if r.headers.get("Accept") == "text/event-stream":
                    return self._handle_sse_connection(r, settings)
                else:
                    return self._serve_html_page(r, settings)
            else:
                # 不支持的请求
                return Response(
                    "Unsupported request type",
                    status=400,
                    content_type="text/plain"
                )
        except Exception as e:
            return Response(
                json.dumps({
                    "error": str(e)
                }),
                status=500,
                content_type="application/json"
            )
    
    def _handle_sse_connection(self, r: Request, settings: Mapping) -> Response:
        """处理 SSE 连接请求 - 有限心跳模式"""
        connection_id = str(uuid.uuid4())
        
        def generate():
            # 发送标准JSON-RPC初始化消息
            init_msg = {
                "jsonrpc": "2.0",
                "method": "connection.established",
                "params": {"id": connection_id},
                "id": str(uuid.uuid4())
            }
            yield f"data: {json.dumps(init_msg)}\n\n"
            
            # 发送工具列表消息（符合JSON-RPC格式）
            tools_msg = {
                "jsonrpc": "2.0",
                "method": "notification.tools",
                "params": {"tools": tool_registry.get_tools()},
                "id": str(uuid.uuid4())
            }
            yield f"data: {json.dumps(tools_msg)}\n\n"
            
            # 心跳消息（符合JSON-RPC格式）
            for i in range(20):
                ping_msg = {
                    "jsonrpc": "2.0",
                    "method": "notification.ping",
                    "params": {"timestamp": time.time()},
                    "id": str(uuid.uuid4())
                }
                time.sleep(15)
                yield f"data: {json.dumps(ping_msg)}\n\n"
        
        return Response(
            generate(),
            status=200,
            content_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive"
            }
        )
    def _serve_html_page(self, r: Request, settings: Mapping) -> Response:
        """返回 HTML 说明页面 (简化版本)"""
        return Response(
            json.dumps({
                "status": "success",
                "message": "Dify MCP Server is running",
                "app_id": settings.get('app_id', {}).get("app_id", ""),
                "query_params": r.args.to_dict()
            }),
            status=200,
            content_type="application/json"
        ) 