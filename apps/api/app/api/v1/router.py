from fastapi import APIRouter
from app.api.v1.routers import auth, workspaces, reel_projects, media_assets

api_v1_router = APIRouter()

api_v1_router.include_router(auth.router, prefix="/auth", tags=["Auth"])
api_v1_router.include_router(workspaces.router, prefix="/workspaces", tags=["Workspaces"])
api_v1_router.include_router(reel_projects.router, prefix="/reel-projects", tags=["Reel Projects"])
api_v1_router.include_router(media_assets.router, prefix="/media-assets", tags=["Media Assets"])
