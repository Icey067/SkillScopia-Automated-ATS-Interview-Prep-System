from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request


def get_user_id(request: Request) -> str:
    if hasattr(request.state, "user_id") and request.state.user_id:
        return f"user:{request.state.user_id}"
    return get_remote_address(request)


limiter = Limiter(key_func=get_user_id)