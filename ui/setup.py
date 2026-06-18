import chainlit as cl
from chainlit.data import get_data_layer
from chainlit.input_widget import Select, TextInput
from chainlit.user import User

from config import MODEL, get_available_models


async def _load_user_settings() -> dict:
    user = cl.context.session.user
    if not user:
        return {}
    layer = get_data_layer()
    if not layer:
        return {}
    persisted = await layer.get_user(user.identifier)
    if not persisted:
        return {}
    return persisted.metadata.get("chat_settings", {})


async def setup_settings() -> None:
    saved = await _load_user_settings()

    widgets = [
        Select(
            id="rol",
            label="Jouw rol",
            values=["Geen voorkeur", "Beleidsmedewerker", "Onderzoeker / Analist", "Schoolbestuur / Directeur", "Journalist"],
            initial_value=saved.get("rol", "Geen voorkeur"),
        ),
        Select(
            id="domein",
            label="Selecteer domein",
            values=["Geen voorkeur", "PO", "VO", "MBO", "HBO / WO"],
            initial_value=saved.get("domein", "Geen voorkeur"),
        ),
        TextInput(
            id="context",
            label="Instelling / Regio",
            placeholder="Bijv. 'ROC Midden Nederland' of 'provincie Utrecht'",
            initial=saved.get("context", ""),
        ),
    ]

    available = get_available_models()
    if available:
        model_items = {name: mid for mid, name, desc, icon in available}
        widgets.append(Select(
            id="model",
            label="Model",
            items=model_items,
            initial_value=saved.get("model") or MODEL,
        ))

    settings = await cl.ChatSettings(widgets).send()
    cl.user_session.set("chat_settings", settings)



@cl.on_settings_update
async def on_settings_update(settings: dict) -> None:
    cl.user_session.set("chat_settings", settings)

    user = cl.context.session.user
    if not user:
        return
    layer = get_data_layer()
    if not layer:
        return
    persisted = await layer.get_user(user.identifier)
    if not persisted:
        return
    updated_metadata = {**persisted.metadata, "chat_settings": settings}
    await layer.create_user(User(identifier=user.identifier, metadata=updated_metadata))
