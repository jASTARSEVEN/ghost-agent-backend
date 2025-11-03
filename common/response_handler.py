from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder


class ResponseHandler:
    @staticmethod
    def response(message: str, data=None, errors=None, status_code: int = 200):
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
    def ok(message: str = "Success", data=None):
        return ResponseHandler.response(message, data, status_code=200)

    @staticmethod
    def created(message: str = "Created successfully", data=None):
        return ResponseHandler.response(message, data, status_code=201)

    @staticmethod
    def bad_request(message: str = "Bad request", errors=None):
        return ResponseHandler.response(message, errors=errors, status_code=400)

    @staticmethod
    def unauthorized(message: str = "Unauthorized"):
        return ResponseHandler.response(message, status_code=401)

    @staticmethod
    def forbidden(message: str = "Forbidden"):
        return ResponseHandler.response(message, status_code=403)

    @staticmethod
    def not_found(message: str = "Not found"):
        return ResponseHandler.response(message, status_code=404)