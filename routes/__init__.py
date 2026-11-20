from .auth import router as auth_router
from .bronstatus import router as bronstatus_router
from .chat import router as chat_router
from .config import router as config_router
from .data_export import router as data_export_router
from .feedback import router as feedback_router
from .instellingen import router as instellingen_router
from .mijn_gegevens import router as mijn_gegevens_router
from .persistence import router as persistence_router
from .rapport_docx import router as rapport_docx_router

__all__ = [
    "auth_router",
    "bronstatus_router",
    "chat_router",
    "config_router",
    "data_export_router",
    "feedback_router",
    "instellingen_router",
    "mijn_gegevens_router",
    "persistence_router",
    "rapport_docx_router",
]
