from pathlib import Path
import os

from dotenv import load_dotenv

load_dotenv()

PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"

HF_TOKEN = os.getenv("HF_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

OLLAMA_ENDPOINT = os.getenv(
    "JARVIS_RESEARCH_OLLAMA_ENDPOINT",
    "http://localhost:11434/api/chat",
)

DUCKDUCKGO_SEARCH_ENDPOINT = "https://html.duckduckgo.com/html/"
OPEN_ROUTER_MODEL_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
OPEN_ROUTER_MODEL_HEADERS = (
    {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    if OPENROUTER_API_KEY
    else {}
)
TAVILY_HEADERS = (
    {
        "Authorization": f"Bearer {TAVILY_API_KEY}",
        "Content-Type": "application/json",
    }
    if TAVILY_API_KEY
    else {}
)