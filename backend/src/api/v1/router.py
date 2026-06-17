from fastapi import APIRouter

from src.api.v1.youtube import router as youtube_router
from src.api.v1.playlists import router as playlists_router
from src.api.v1 import auth

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(youtube_router)
api_router.include_router(playlists_router)
api_router.include_router(auth.router)