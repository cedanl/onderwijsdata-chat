import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import litellm

Emit = Callable[[dict[str, Any]], Awaitable[None]]

_MAX_RETRIES = 4
_BASE_DELAY = 2.0


async def acompletion_with_backoff(emit: Emit, **kwargs):
    """litellm.acompletion with exponential backoff on rate limit errors."""
    for attempt in range(_MAX_RETRIES):
        try:
            return await litellm.acompletion(**kwargs)
        except litellm.RateLimitError:
            if attempt == _MAX_RETRIES - 1:
                raise
            delay = _BASE_DELAY * (2 ** attempt)
            await emit({
                "type": "toast",
                "message": f"API rate limit bereikt, nieuwe poging over {delay:.0f}s…",
                "level": "warning",
            })
            await asyncio.sleep(delay)
