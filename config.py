import os

MODEL = os.getenv("MODEL", "anthropic/claude-sonnet-4-6")
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "40960"))
MAX_TOOL_ITERATIONS = int(os.getenv("MAX_TOOL_ITERATIONS", "100"))
CBS_ROW_LIMIT = int(os.getenv("CBS_ROW_LIMIT", "200"))
RIO_PAGE_SIZE = int(os.getenv("RIO_PAGE_SIZE", "50"))

# Willma AI-Hub (SURF) — optioneel. Zet WILLMA_API_KEY om via Willma te draaien.
# Zet MODEL naar bijv. "openai/Qwen2.5-Coder-7B-Instruct" om een specifiek Willma-model te kiezen.
WILLMA_API_KEY = os.getenv("WILLMA_API_KEY")
WILLMA_BASE_URL = os.getenv("WILLMA_BASE_URL", "")
