"""User registration REST endpoint."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

from .auth import check_auth
from maggy.services.users import DuplicateUserError, UserService

logger = logging.getLogger("maggy.api.users")

router = APIRouter(prefix="/api/users", tags=["users"])


class CreateUserRequest(BaseModel):
    """Request body for user creation."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=72)


class UserResponse(BaseModel):
    """Public user payload returned from the API."""

    id: str
    email: EmailStr
    created_at: str


def _user_service(request: Request) -> UserService:
    """Get or lazily initialize the user service."""
    service = getattr(request.app.state, "users", None)
    if service is None:
        service = UserService()
        request.app.state.users = service
    return service


@router.post("", response_model=UserResponse, status_code=201)
async def create_user(
    body: CreateUserRequest,
    request: Request,
    x_api_key: str | None = Header(None),
) -> UserResponse:
    """Create a user after validating email and hashing the password."""
    check_auth(request, x_api_key)
    service = _user_service(request)
    try:
        user = service.create_user(body.email, body.password)
    except DuplicateUserError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        logger.exception("User creation failed")
        raise HTTPException(
            status_code=500,
            detail="Failed to create user",
        ) from None
    return UserResponse.model_validate(user.to_public())
