from fastapi import APIRouter
from app.api.v1.routers import auth, workspaces

api_v1_router = APIRouter()

api_v1_router.include_router(auth.router, prefix="/auth", tags=["Auth"])
api_v1_router.include_router(workspaces.router, prefix="/workspaces", tags=["Workspaces"])
