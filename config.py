import os

MODEL = os.getenv("MODEL", "anthropic/claude-sonnet-4-6")
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "40960"))
MAX_TOOL_ITERATIONS = int(os.getenv("MAX_TOOL_ITERATIONS", "50"))
