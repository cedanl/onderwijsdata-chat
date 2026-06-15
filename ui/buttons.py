import chainlit as cl


def rapport_actions() -> list[cl.Action]:
    return [
        cl.Action(name="download_rapport_samenvatting", label="🧾 Samenvatting", payload={"action": "download_samenvatting"}),
        cl.Action(name="download_rapport", label="📥 HTML", payload={"action": "download"}),
    ]
