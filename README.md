# DODO

DODA Offers Dev Assistance.

It is a full featured LLM chat interface that runs natively within a developers terminal to help with system administration, scripting, and any other CLI oriented task.

## Setup

```bash
cd doda_core
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
echo "OPENAI_KEY=<key>" >> .env
```

### function calling confirmation

By default, all functions require confirmation before the LLM calls them.
To disable this, set `FUNCTION_CONFIRMATION_REQUIRED=false` in the `.env` file.

## Development

```bash
./.venv/bin/textual run --dev main.py
```

To view console run:
`textual console`
