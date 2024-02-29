# DODO

DODA Offers Dev Assistance.

It is a full featured LLM chat interface that runs natively within a developers terminal to help with system administration, scripting, and any other CLI oriented task.

![doda-gif](doda-intro.gif)

### Setup

```bash
cd doda_core
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env # add openAI ... other values optional
```

### Optional .env vars

By default, all functions require confirmation before the LLM calls them.
To disable this, set `FUNCTION_CONFIRMATION_REQUIRED=false` in the `.env` file.

⚠️ DODA runs code **on your machine**. Be careful with what you allow it to do! ⚠️

### Git Remotes

Creating functions to interact with remote git providers is a promising feature of AI agents. Currently SDKs for both GitLab and GitHub are installed.

`GITLAB_TOKEN` -  https://docs.gitlab.com/ee/user/profile/personal_access_tokens.html
`GITHUB_TOKEN` - https://github.com/settings/tokens

### Development

```bash
./.venv/bin/textual run --dev main.py
```

To view a debug console in another tab, run:
`textual console`

### Adding new LLM functions

All functions available to the LLM are defined in `doda_core/internal/functions`. To add a new function, create a python file in this directory with a function matching the name and then update the `doda_core/internal/functions.json` file according to the openai function calling description: https://platform.openai.com/docs/guides/function-calling