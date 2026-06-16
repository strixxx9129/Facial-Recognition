# app/models/__init__.py
from app.models.user import User
from app.models.auth_provider import AuthProvider
from app.models.session import Session
from app.models.emotion_session import EmotionSession
from app.models.emotion_snapshot import EmotionSnapshot
from app.models.recommendation import Recommendation, RecommendationTrack
from app.models.track import Track
from app.models.playlist import Playlist, PlaylistTrack
from app.models.user_preferences import UserPreferences
from app.models.user_music_interaction import UserMusicInteraction
from app.models.audit_log import AuditLog

__all__ = [
    "User",
    "AuthProvider",
    "Session",
    "EmotionSession",
    "EmotionSnapshot",
    "Recommendation",
    "RecommendationTrack",
    "Track",
    "Playlist",
    "PlaylistTrack",
    "UserPreferences",
    "UserMusicInteraction",
    "AuditLog",
]