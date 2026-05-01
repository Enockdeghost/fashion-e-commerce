from flask import jsonify


class APIError(Exception):
    """Base exception with status code and message."""
    status_code = 400

    def __init__(self, message: str = "Error", status_code: int = None, errors: list = None):
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.errors = errors or []

    def to_dict(self):
        body = {"success": False, "error": self.message}
        if self.errors:
            body["errors"] = self.errors
        return body


class BadRequestError(APIError):
    status_code = 400

class UnauthorisedError(APIError):
    status_code = 401

class ForbiddenError(APIError):
    status_code = 403

class NotFoundError(APIError):
    status_code = 404

class MethodNotAllowedError(APIError):
    status_code = 405

class ConflictError(APIError):
    status_code = 409

class UnprocessableError(APIError):
    status_code = 422

class RateLimitError(APIError):
    status_code = 429

class InternalServerError(APIError):
    status_code = 500


def register_error_handlers(app):
    """Catch unhandled APIErrors and return JSON (called from app factory)."""
    from .security import err as _err  # fallback helper

    @app.errorhandler(APIError)
    def handle_api_error(e):
        response = jsonify(e.to_dict())
        response.status_code = e.status_code
        return response

    # Also catch 404/405/500 that weren't caught by custom exceptions
    @app.errorhandler(404)
    def handle_404(e):
        return _err("Resource not found", 404)

    @app.errorhandler(405)
    def handle_405(e):
        return _err("Method not allowed", 405)

    @app.errorhandler(500)
    def handle_500(e):
        return _err("Internal server error", 500)