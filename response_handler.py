from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder

class ResponseHandler:
    @staticmethod
    def response(message, data=None, errors=None, status_code=200):
        is_success = 200 <= status_code < 300
        payload = {
            "status": "success" if is_success else "error",
            "message": message,
        }
        if data is not None:
            payload["data"] = jsonable_encoder(data)
        if errors is not None:
            payload["errors"] = errors
        return JSONResponse(content=payload, status_code=status_code)

    @staticmethod
    def ok(message="Success", data=None):
        return ResponseHandler.response(message, data, status_code=200)

    @staticmethod
    def bad_request(message="Bad request", errors=None):
        return ResponseHandler.response(message, errors=errors, status_code=400)

    @staticmethod
    def unauthorized(message="Unauthorized"):
        return ResponseHandler.response(message, status_code=401)
