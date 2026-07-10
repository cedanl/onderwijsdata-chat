from .auth import router as auth_router
from .chat import router as chat_router
from .instellingen import router as instellingen_router
from .persistence import router as persistence_router

__all__ = [
    "auth_router",
    "chat_router",
    "instellingen_router",
    "persistence_router",
]
