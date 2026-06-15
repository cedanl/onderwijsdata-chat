import asyncio
import json

import litellm
import chainlit as cl

from config import MAX_TOKENS, MAX_TOOL_ITERATIONS, MODEL
from tools import LABELS, SCHEMAS, SCHEMAS_VERDIEP, dispatch
from ui.buttons import rapport_actions
from .history import trim
from .models import build_system, litellm_kwargs

# LiteLLM bug: transform_request for ollama_chat converts tool_calls in history
# messages but never writes them to the output Ollama message, causing orphaned
# tool-result messages on the second LLM call. Patch it here.
if MODEL.startswith("ollama_chat/") or MODEL.startswith("ollama/"):
    from litellm.llms.ollama.chat.transformation import OllamaChatConfig

    _orig_transform = OllamaChatConfig.transform_request

    def _patched_transform(self, model, messages, optional_params, litellm_params, headers):
        result = _orig_transform(self, model, messages, optional_params, litellm_params, headers)
        for orig, out in zip(messages, result.get("messages", [])):
            if not isinstance(orig, dict):
                continue
            raw_tools = orig.get("tool_calls")
            if raw_tools and "tool_calls" not in out:
                converted = []
                for tc in raw_tools:
                    args = tc.get("function", {}).get("arguments", "{}")
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except Exception:
                            args = {}
                    converted.append({"function": {"name": tc["function"]["name"], "arguments": args}})
                out["tool_calls"] = converted
        return result

    OllamaChatConfig.transform_request = _patched_transform  # ty: ignore[invalid-assignment]


async def _show_clarification(args: dict) -> None:
    lines = ["**Voordat ik begin wil ik de scope scherp stellen.**\n"]
    lines.append(f"*Interpretatie:* {args['interpretatie']}")
    if args.get("open_dimensies"):
        lines.append(f"*Openstaande keuzes:* {', '.join(args['open_dimensies'])}")
    lines.append(f"\n{args['vraag']}")

    opties = args.get("opties") or []
    actions = []
    source_opts = []

    for opt in opties:
        if isinstance(opt, dict):
            label = opt.get("label", "")
            beschrijving = opt.get("beschrijving", "")
            aanbevolen = opt.get("aanbevolen", False)
            btn_label = f"✓ {label} — {beschrijving}" if aanbevolen else f"{label} — {beschrijving}"
            actions.append(cl.Action(
                name="clarification_choice",
                label=btn_label,
                payload={"choice": label},
            ))
            source_opts.append(opt)
        else:
            actions.append(cl.Action(
                name="clarification_choice",
                label=str(opt),
                payload={"choice": str(opt)},
            ))

    if source_opts:
        lines.append("\n*De uitkomsten kunnen per bron verschillen.*")
        cl.user_session.set("source_options", source_opts)

    await cl.Message(content="\n".join(lines), actions=actions).send()



async def _call_tool(tc: dict) -> tuple[str, object]:
    if tc["name"] == "suggest_followups":
        args = json.loads(tc["arguments"])
        cl.user_session.set("pending_suggestions", args.get("suggestions", []))
        return "OK", None
    if tc["name"] == "clarify_scope":
        args = json.loads(tc["arguments"])
        cl.user_session.set("pending_clarification", args)
        cl.user_session.set("source_alternatives", [])
        cl.user_session.set("chosen_source", "")
        return "OK", None
    args = json.loads(tc["arguments"])
    label = LABELS.get(tc["name"], tc["name"])
    async with cl.Step(name=label, type="tool") as step:
        step.input = args
        result, figure = await asyncio.to_thread(dispatch, tc["name"], args)
        step.output = result
    return result, figure


def _call_key(tc: dict) -> str:
    return f"{tc['name']}:{tc['arguments']}"


async def run(
    messages: list[dict],
    stop_event: asyncio.Event | None = None,
    model: str | None = None,
    modus: str = "snel",
) -> str:
    settings: dict = cl.user_session.get("chat_settings") or {}
    chosen_model = model or MODEL
    system = build_system(modus, settings)
    extra_kwargs = litellm_kwargs(chosen_model)

    history, was_trimmed = trim(list(messages))
    if was_trimmed:
        await cl.context.emitter.send_toast(
            "Oudere berichten vallen buiten de context van het model.",
            type="warning",
        )

    call_cache: dict[str, tuple[str, object]] = {}
    last_text_msg: cl.Message | None = None
    turn_tool_calls: list[dict] = []
    tools_list = SCHEMAS_VERDIEP if modus == "verdiep" else SCHEMAS

    for _ in range(MAX_TOOL_ITERATIONS):
        if stop_event and stop_event.is_set():
            break

        stream = await litellm.acompletion(
            model=chosen_model,
            max_tokens=MAX_TOKENS,
            num_retries=3,
            messages=system + history,
            tools=tools_list,
            stream=True,
            **extra_kwargs,
        )

        msg = cl.Message(content="")
        await msg.send()

        text_parts: list[str] = []
        raw_tcs: dict[int, dict] = {}

        async for chunk in stream:
            if stop_event and stop_event.is_set():
                break

            delta = chunk.choices[0].delta

            if delta.content:
                text_parts.append(delta.content)
                await msg.stream_token(delta.content)

            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in raw_tcs:
                        raw_tcs[idx] = {"id": "", "name": "", "arguments": ""}
                    if tc.id:
                        raw_tcs[idx]["id"] = tc.id
                    if tc.function:
                        if tc.function.name:
                            raw_tcs[idx]["name"] = tc.function.name
                        if tc.function.arguments:
                            raw_tcs[idx]["arguments"] += tc.function.arguments

        text_content = "".join(text_parts)
        tool_calls = [raw_tcs[i] for i in sorted(raw_tcs)]

        if stop_event and stop_event.is_set():
            if text_content:
                await msg.update()
            else:
                await msg.remove()
            return text_content

        if not tool_calls:
            msg.actions = rapport_actions()
            await msg.update()
            cl.user_session.set("_last_turn_tool_calls", turn_tool_calls)
            return text_content

        if not text_content:
            await msg.remove()
        else:
            last_text_msg = msg
            await msg.update()

        history.append({
            "role": "assistant",
            "content": text_content or "",
            "tool_calls": [
                {"id": tc["id"], "type": "function", "function": {"name": tc["name"], "arguments": tc["arguments"]}}
                for tc in tool_calls
            ],
        })

        turn_tool_calls.extend({"name": tc["name"], "arguments": tc["arguments"]} for tc in tool_calls)

        # Deduplicate: run only calls not seen earlier this conversation
        new_calls = [(i, tc) for i, tc in enumerate(tool_calls) if _call_key(tc) not in call_cache]
        new_results = await asyncio.gather(*[_call_tool(tc) for _, tc in new_calls])
        for (i, tc), res in zip(new_calls, new_results):
            call_cache[_call_key(tc)] = res

        results = [call_cache[_call_key(tc)] for tc in tool_calls]

        for tc, (result, figure) in zip(tool_calls, results):
            if figure is not None:
                figures = cl.user_session.get("figures", [])
                figures.append(figure)
                cl.user_session.set("figures", figures)
                turn_figs = cl.user_session.get("turn_figures", [])
                turn_figs.append(figure)
                cl.user_session.set("turn_figures", turn_figs)
                fig_meta = getattr(getattr(figure, "layout", None), "meta", None) or {}
                if not fig_meta.get("chat_hidden"):
                    label = LABELS.get(tc["name"], tc["name"])
                    await cl.Message(
                        content="",
                        elements=[cl.Plotly(name=label, figure=figure, display="inline")],
                    ).send()
            history.append({"role": "tool", "tool_call_id": tc["id"], "content": result})

        # Terminal: clarify_scope was called — show structured question and return
        if any(tc["name"] == "clarify_scope" for tc in tool_calls):
            cl.user_session.set("_last_turn_tool_calls", turn_tool_calls)
            pending = cl.user_session.get("pending_clarification")
            cl.user_session.set("pending_clarification", None)
            if pending:
                await _show_clarification(pending)
            return text_content

        # Terminal: only suggest_followups was called — show labelled suggestion block and return
        if all(tc["name"] == "suggest_followups" for tc in tool_calls):
            cl.user_session.set("_last_turn_tool_calls", turn_tool_calls)
            pending = cl.user_session.get("pending_suggestions", [])
            cl.user_session.set("pending_suggestions", [])
            target = msg if text_content else last_text_msg
            if target:
                target.actions = rapport_actions()
                await target.update()
            if pending:
                followup_actions = [
                    cl.Action(name="followup", label=s, payload={"question": s})
                    for s in pending
                ]
                await cl.Message(content="**Vraag suggesties**", actions=followup_actions).send()
            alternatives = cl.user_session.get("source_alternatives", [])
            if alternatives:
                chosen = cl.user_session.get("chosen_source", "")
                alt_actions = [
                    cl.Action(
                        name="alternative_source",
                        label=f"{a['label']} — {a.get('beschrijving', '')}".rstrip(" —"),
                        payload={"label": a["label"]},
                    )
                    for a in alternatives
                ]
                note = f"*Geanalyseerd met **{chosen}**.* " if chosen else ""
                await cl.Message(content=f"{note}**Andere bron proberen?**", actions=alt_actions).send()
            return text_content

    await cl.Message(content="Het maximale aantal stappen is bereikt. Probeer een specifiekere vraag.").send()
    return "Het maximale aantal stappen is bereikt."
