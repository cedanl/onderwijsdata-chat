import uvicorn

from server import app  # noqa: F401 — imported for uvicorn

if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
