# DODA

DODA Offers Dev Assistance.

A full-featured **AI coding agent** that runs natively in your terminal, powered by local LLMs via [Ollama](https://ollama.com). DODA doesn't just chat — it actually reads, writes, searches, and executes code on your machine.

### Features

- 🧠 **Agentic tool loop** — the AI calls tools (read/write/search/bash) in a loop until the task is done
- 🔧 **Built-in tools**: `read_file`, `write_file`, `edit_file`, `list_files`, `bash`, `code_search`
- 🖥️ **TUI with live feedback** — see tool calls and results as the agent works
- 📁 **File browser** — browse and edit files from the sidebar
- 🏠 **100% local** — runs with Ollama, no cloud API keys needed

### Prerequisites

- [Ollama](https://ollama.com) installed and running
- A model pulled, e.g. `ollama pull mistral`

### Setup

```bash
cd doda_core
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # tweak model/url if needed
```

### Run

```bash
./.venv/bin/textual run --dev main.py
```

### Configuration

Edit `doda_core/.env`:

```env
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=mistral
FUNCTION_CONFIRMATION_REQUIRED=true
```

### Development

To view a debug console in another tab:
```bash
textual console
```

### Architecture

```
doda_core/
├── agent.py       # Agentic loop + tool definitions + Ollama API
├── tui.py         # Textual TUI (file browser, editor, chat)
├── settings.py    # Ollama configuration
├── main.py        # Entry point
├── internal/
│   └── custom_instructions.txt   # System prompt template
├── static/
│   └── styles.css
└── workspace/     # Default working directory for the agent
```