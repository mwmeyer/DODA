import os
from dotenv import load_dotenv

load_dotenv()

# Ollama Configuration — uses the NATIVE Ollama API (not OpenAI-compat)
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "mistral")
