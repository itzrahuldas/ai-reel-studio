from fastapi import APIRouter, Depends, HTTPException, status
import structlog
from typing import Any

from app.api.deps import DbSession, CurrentUser
from app.schemas.schemas import UserCreate, LoginRequest, AuthResponse, TokenResponse, UserResponse
from app.services.auth import register_user, authenticate_user
from app.core.security import create_access_token

logger = structlog.get_logger(__name__)
router = APIRouter()

@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(user_in: UserCreate, db: DbSession) -> Any:
    """Register a new user and create a default workspace."""
    return await register_user(db, user_in)

@router.post("/login", response_model=TokenResponse)
async def login(login_in: LoginRequest, db: DbSession) -> Any:
    """Authenticate user and return a JWT access token."""
    user = await authenticate_user(db, email=login_in.email, password=login_in.password)
    if not user:
        logger.warning("login_failed_invalid_credentials", email=login_in.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    if not user.is_active:
        logger.warning("login_failed_inactive", user_id=str(user.id))
        raise HTTPException(status_code=400, detail="Inactive user")
        
    token = create_access_token(subject=user.id)
    logger.info("user_logged_in", user_id=str(user.id))
    return {"access_token": token, "token_type": "bearer", "expires_in": 3600}

@router.get("/me", response_model=UserResponse)
async def get_me(current_user: CurrentUser) -> Any:
    """Return the currently authenticated user."""
    return current_user

@router.post("/logout")
async def logout(current_user: CurrentUser) -> Any:
    """Stateless logout endpoint. Tells client to discard token."""
    logger.info("user_logged_out", user_id=str(current_user.id))
    return {"message": "Successfully logged out. Please discard your token locally."}
