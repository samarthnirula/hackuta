"""Shared configuration. Secrets come from environment / .env only."""
import os

from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or None
GEMINI_REASONING_MODEL = os.getenv("GEMINI_REASONING_MODEL", "gemini-4-hydrogen")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY") or None
IFIXIT_BASE_URL = os.getenv("IFIXIT_BASE_URL", "https://www.ifixit.com/api/2.0")
def _mongo_uri() -> str | None:
    if uri := os.getenv("MONGODB_URI"):
        return uri
    user, pw, host = (os.getenv(k) for k in ("MONGODB_USER", "MONGODB_PASSWORD", "MONGODB_CLUSTER_HOST"))
    if user and pw and host:
        from urllib.parse import quote_plus
        return f"mongodb+srv://{quote_plus(user)}:{quote_plus(pw)}@{host}/?retryWrites=true&w=majority"
    return None


MONGODB_URI = _mongo_uri()
MONGODB_DB = os.getenv("MONGODB_DB", "fixlens")
DECISION_TIMEOUT_S = float(os.getenv("DECISION_TIMEOUT_S", "3"))
RESEARCH_TIMEOUT_S = float(os.getenv("RESEARCH_TIMEOUT_S", "5"))
