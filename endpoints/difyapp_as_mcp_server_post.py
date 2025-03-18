from typing import Mapping
from werkzeug import Request, Response
from dify_plugin import Endpoint
import json

class DifyappAsMcpServerEndpoint(Endpoint):
    def _invoke(self, r: Request, values: Mapping, settings: Mapping) -> Response:
        """
        Invokes the endpoint with the given request, utilizing the workflow interface.
        """
        try:
            # Extract request data and prepare workflow inputs
            data = r.get_json()
            workflow_inputs = {}
            for key, value in data.get("responseValues", {}).items():
                workflow_inputs[key] = value.get("value")
            
            app_id = settings.get('app_id', {}).get("app_id", "")
            
            # Invoke the Dify workflow
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
