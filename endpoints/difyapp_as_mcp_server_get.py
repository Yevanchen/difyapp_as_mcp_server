from typing import Mapping
from werkzeug import Request, Response
from dify_plugin import Endpoint
import json

class DifyappAsMcpServerGetEndpoint(Endpoint):
    def _invoke(self, r: Request, values: Mapping, settings: Mapping) -> Response:
        """
        Invokes the GET endpoint to retrieve status or information about the Dify app.
        """
        try:
            # Extract query parameters if any
            query_params = r.args.to_dict()
            
            app_id = settings.get('app_id', {}).get("app_id", "")
            
            # Basic functionality - return status information
            # In a real implementation, you might want to get app status or other information
            return Response(
                json.dumps({
                    "status": "success",
                    "message": "Dify MCP Server is running",
                    "app_id": app_id,
                    "query_params": query_params
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