from .auth import router as auth_router
from .chat import router as chat_router
from .config import router as config_router
from .data_export import router as data_export_router
from .feedback import router as feedback_router
from .instellingen import router as instellingen_router
from .persistence import router as persistence_router

__all__ = [
    "auth_router",
    "chat_router",
    "config_router",
    "data_export_router",
    "feedback_router",
    "instellingen_router",
    "persistence_router",
]
