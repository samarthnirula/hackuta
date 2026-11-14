"""One real Gemini Interactions API call. Run: python scripts/gemini_smoke.py"""
import sys

from google import genai

from shared import config

if not config.GEMINI_API_KEY:
    sys.exit("GEMINI_API_KEY not set. Create one at https://aistudio.google.com/apikey and put it in .env")

client = genai.Client(api_key=config.GEMINI_API_KEY)
interaction = client.interactions.create(
    model=config.GEMINI_REASONING_MODEL,
    input="In one short friendly sentence: what's the first thing to check on a laptop with a cracked screen?",
)
print(f"model={config.GEMINI_REASONING_MODEL}")
print(interaction.output_text)
