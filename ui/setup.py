import chainlit as cl
from chainlit.data import get_data_layer
from chainlit.input_widget import Select, Switch, TextInput
from chainlit.user import User

from config import MODEL, get_available_models


async def setup_modes() -> None:
    modus_mode = cl.Mode(
        id="modus",
        name="Modus",
        options=[
            cl.ModeOption(id="snel", name="Snel", description="Precies het gevraagde, niet meer", icon="zap", default=True),
            cl.ModeOption(id="verdiep", name="Verdiep", description="Doorvragen + volledige analyse", icon="microscope"),
        ],
    )

    modes = [modus_mode]

    available = get_available_models()
    if available:
        model_options = [
            cl.ModeOption(
                id=mid,
                name=name,
                description=desc,
                icon=icon,
                default=(mid == MODEL),
            )
            for mid, name, desc, icon in available
        ]
        if not any(o.default for o in model_options):
            model_options[0].default = True
        modes.insert(0, cl.Mode(id="model", name="Model", options=model_options))

    await cl.context.emitter.set_modes(modes)


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
    settings = await cl.ChatSettings([
        Select(
            id="rol",
            label="Jouw rol",
            values=["Geen voorkeur", "Beleidsmedewerker", "Onderzoeker / Analist", "Schoolbestuur / Directeur", "Journalist", "Student"],
            initial_value=saved.get("rol", "Geen voorkeur"),
        ),
        Select(
            id="domein",
            label="Selecteer domein",
            values=["Geen voorkeur", "PO", "VO", "MBO", "HBO / WO"],
            initial_value=saved.get("domein", "Geen voorkeur"),
        ),
        Switch(
            id="sparren",
            label="Sparren-modus",
            description="Stel altijd een doorvraag voordat data wordt opgehaald",
            initial=saved.get("sparren", False),
        ),
        TextInput(
            id="context",
            label="Instelling / Regio",
            placeholder="Bijv. 'ROC Midden Nederland' of 'provincie Utrecht'",
            initial=saved.get("context", ""),
        ),
    ]).send()
    cl.user_session.set("chat_settings", settings)


async def setup_commands() -> None:
    await cl.context.emitter.set_commands([
        {
            "id": "Catalogus",
            "icon": "database",
            "description": "Beschikbare datasets doorzoeken",
            "button": True,
            "persistent": None,
            "selected": None,
        }
    ])


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
