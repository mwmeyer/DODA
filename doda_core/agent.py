"""
DODA Agent – agentic tool loop over Ollama's NATIVE /api/chat endpoint.

The native Ollama API has proper tool-calling support (unlike the
OpenAI-compatible /v1 endpoint which many models ignore).

The agent repeatedly calls the model, executes any tool calls it returns,
feeds results back, and loops until the model produces a final text answer.
"""

import os
import json
import select
import subprocess
import platform
import textwrap
import time
import requests
import settings


# ── Tool implementations ─────────────────────────────────────────────────────

def read_file(path: str) -> str:
    """Read the contents of a file."""
    try:
        with open(path, "r") as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {e}"


def write_file(path: str, content: str) -> str:
    """Create or overwrite a file with the given content."""
    try:
        dir_part = os.path.dirname(path)
        if dir_part:
            os.makedirs(dir_part, exist_ok=True)
        with open(path, "w") as f:
            f.write(content)
        return f"Successfully wrote {path}"
    except Exception as e:
        return f"Error writing file: {e}"


def edit_file(path: str, old_str: str, new_str: str) -> str:
    """
    Edit a file by replacing old_str with new_str (first occurrence).
    If old_str is empty, create the file with new_str as content.
    """
    try:
        if old_str == "":
            return write_file(path, new_str)
        with open(path, "r") as f:
            content = f.read()
        if old_str not in content:
            return f"Error: old_str not found in {path}"
        new_content = content.replace(old_str, new_str, 1)
        with open(path, "w") as f:
            f.write(new_content)
        return f"Successfully edited {path}"
    except Exception as e:
        return f"Error editing file: {e}"


def list_files(path: str = ".") -> str:
    """List files and directories (max 3 levels deep)."""
    try:
        items = []
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            level = root.replace(path, "").count(os.sep)
            indent = "  " * level
            items.append(f"{indent}{os.path.basename(root)}/")
            for file in files:
                items.append(f"{indent}  {file}")
            if level >= 2:
                dirs.clear()
        return "\n".join(items) or "(empty directory)"
    except Exception as e:
        return f"Error listing files: {e}"


# Timeouts for bash commands
BASH_LINE_TIMEOUT = 10   # seconds of silence before we consider it stalled
BASH_TOTAL_TIMEOUT = 120  # hard cap on total runtime

def bash(command: str, on_output=None) -> str:
    """
    Execute a bash command, streaming output line-by-line.
    Uses select() so interactive/hanging commands get killed
    after BASH_LINE_TIMEOUT seconds of no output.
    """
    try:
        proc = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        lines = []
        start = time.time()
        fd = proc.stdout.fileno()

        while True:
            # Total timeout guard
            elapsed = time.time() - start
            if elapsed > BASH_TOTAL_TIMEOUT:
                proc.kill()
                lines.append(f"\n(killed: exceeded {BASH_TOTAL_TIMEOUT}s total timeout)")
                break

            # Wait for data with a per-line timeout
            ready, _, _ = select.select([fd], [], [], BASH_LINE_TIMEOUT)
            if not ready:
                # No output for BASH_LINE_TIMEOUT seconds — likely stuck/interactive
                proc.kill()
                lines.append(f"\n(killed: no output for {BASH_LINE_TIMEOUT}s — likely waiting for input)")
                break

            line = proc.stdout.readline()
            if line == "":  # EOF
                break

            line = line.rstrip("\n")
            lines.append(line)
            if on_output:
                on_output(line)

        proc.stdout.close()
        try:
            retcode = proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            retcode = -1

        output = "\n".join(lines)
        if retcode and retcode != 0:
            output += f"\n(exit code {retcode})"
        return output or "(no output)"
    except Exception as e:
        return f"Error running command: {e}"


def code_search(pattern: str, path: str = ".", file_type: str = "") -> str:
    """Search for a pattern in code using ripgrep (falls back to grep)."""
    cmd = ["rg", "--line-number", pattern, path]
    if file_type:
        cmd += ["-t", file_type]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return result.stdout or f"No matches found for: {pattern}"
    except FileNotFoundError:
        cmd = ["grep", "-rn", pattern, path]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return result.stdout or f"No matches found for: {pattern}"
    except Exception as e:
        return f"Error searching: {e}"


# ── Tool registry (Ollama native format) ──────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file at the given path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file to read"}
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Create or overwrite a file with the given content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file to write"},
                    "content": {"type": "string", "description": "Content to write to the file"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Edit a file by replacing old_str with new_str (first occurrence only). Pass old_str='' to create a new file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file"},
                    "old_str": {"type": "string", "description": "Text to replace (empty string = create new file)"},
                    "new_str": {"type": "string", "description": "Replacement text"},
                },
                "required": ["path", "old_str", "new_str"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files and directories at a path (max 3 levels deep).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path to list (default: current directory)"}
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "bash",
            "description": "Execute a bash command and return its output. Use for running scripts, installing packages, git operations, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The bash command to execute"}
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "code_search",
            "description": "Search for a regex pattern in files using ripgrep (falls back to grep).",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Search pattern (regex supported)"},
                    "path": {"type": "string", "description": "Directory to search (default: current)"},
                    "file_type": {"type": "string", "description": "File type filter e.g. 'py', 'js', 'rb'"},
                },
                "required": ["pattern"],
            },
        },
    },
]

TOOL_DISPATCH = {
    "read_file":    lambda args: read_file(args["path"]),
    "write_file":   lambda args: write_file(args["path"], args["content"]),
    "edit_file":    lambda args: edit_file(args["path"], args["old_str"], args["new_str"]),
    "list_files":   lambda args: list_files(args.get("path", ".")),
    "bash":         lambda args: bash(args["command"]),
    "code_search":  lambda args: code_search(args["pattern"], args.get("path", "."), args.get("file_type", "")),
}


def _build_system_prompt() -> str:
    """Build a system prompt with machine context."""
    return textwrap.dedent(f"""\
        You are DODA, an expert AI coding agent running in a terminal on {platform.platform()}.
        You have access to tools to read, write, search, and execute code on the user's machine.
        The current working directory is {os.getcwd()}.
        The users primary workspace is {os.getcwd()}/workspace — prefer creating files there.

        CRITICAL RULES:
        - Always USE your tools to accomplish tasks. Never just describe what you would do.
        - When asked to create a file, call the write_file tool. Do NOT just print the code as text.
        - After creating or editing files, verify your work by running them with the bash tool.
        - Explore before editing: use list_files and read_file to understand the project first.
        - Be concise. Act, don't narrate.
        - NEVER run interactive commands. Always pass non-interactive flags:
          * npm/npx: use --yes or -y flags
          * apt: use -y flag
          * git: use --no-edit or config to avoid prompts
          * For any command that might prompt for input, find the non-interactive version.
        - If a command hangs (no output for 10s), it will be killed automatically.
    """)


class Agent:
    """
    Agentic loop: sends messages to Ollama's native /api/chat endpoint,
    executes any tool calls, feeds results back, and repeats until the
    model produces a final text response.
    """

    def __init__(self):
        self.model = settings.OLLAMA_MODEL
        self.host = settings.OLLAMA_HOST.rstrip("/")
        self.messages: list[dict] = [
            {"role": "system", "content": _build_system_prompt()},
        ]
        self.on_tool_start = None   # callback(tool_name, args_dict)
        self.on_tool_end = None     # callback(tool_name, result_str)
        self.on_bash_output = None  # callback(line_str) — real-time bash streaming
        self.on_text = None         # callback(text)
        self._max_iterations = 15   # safety guard

    # ── public API ────────────────────────────────────────────────────────

    async def send(self, user_message: str) -> dict:
        """
        Send a user message and run the full agentic loop.
        Returns {'response_content': str, 'tool_log': list[dict]}
        """
        self.messages.append({"role": "user", "content": user_message})

        tool_log: list[dict] = []
        final_text = ""

        for _ in range(self._max_iterations):
            response_message = self._call_ollama()

            text_content = response_message.get("content") or ""
            tool_calls = response_message.get("tool_calls") or []

            # Append the assistant turn to conversation history
            self.messages.append(self._sanitize_assistant_message(response_message))

            if text_content and self.on_text:
                self.on_text(text_content)

            if not tool_calls:
                # Model is done — return the final text
                final_text = text_content
                break

            # Execute each tool call and feed results back
            for tc in tool_calls:
                fn_name = tc["function"]["name"]
                fn_args_raw = tc["function"].get("arguments", {})

                # arguments may be a string (JSON) or already a dict
                if isinstance(fn_args_raw, str):
                    try:
                        fn_args = json.loads(fn_args_raw)
                    except json.JSONDecodeError:
                        fn_args = {}
                else:
                    fn_args = fn_args_raw

                if self.on_tool_start:
                    self.on_tool_start(fn_name, fn_args)

                if fn_name == "bash":
                    # Special-case bash to pass the streaming callback
                    result = bash(fn_args["command"], on_output=self.on_bash_output)
                else:
                    dispatcher = TOOL_DISPATCH.get(fn_name)
                    if dispatcher:
                        result = dispatcher(fn_args)
                    else:
                        result = f"Unknown tool: {fn_name}"

                if self.on_tool_end:
                    self.on_tool_end(fn_name, result)

                tool_log.append({"tool": fn_name, "args": fn_args, "result": result[:500]})

                # Feed the tool result back to Ollama (native format)
                self.messages.append({
                    "role": "tool",
                    "content": result,
                })

        return {"response_content": final_text, "tool_log": tool_log}

    def clear(self):
        """Reset the conversation."""
        self.messages = [
            {"role": "system", "content": _build_system_prompt()},
        ]

    # ── private ──────────────────────────────────────────────────────────

    def _sanitize_assistant_message(self, msg: dict) -> dict:
        """
        Build a clean assistant message for the conversation history.
        Ollama's native API expects assistant messages with tool_calls
        to have a specific shape.
        """
        clean = {"role": "assistant", "content": msg.get("content") or ""}
        if msg.get("tool_calls"):
            clean["tool_calls"] = msg["tool_calls"]
        return clean

    def _call_ollama(self) -> dict:
        """
        Single call to Ollama's NATIVE /api/chat endpoint.

        This endpoint returns tool_calls properly when tools are provided,
        unlike the OpenAI-compatible /v1 endpoint which many models ignore.

        Native response format:
        {
          "message": {
            "role": "assistant",
            "content": "...",
            "tool_calls": [
              {"function": {"name": "...", "arguments": {...}}}
            ]
          }
        }
        """
        payload = {
            "model": self.model,
            "messages": self.messages,
            "tools": TOOLS,
            "stream": False,
        }

        try:
            resp = requests.post(
                f"{self.host}/api/chat",
                json=payload,
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["message"]
        except Exception as e:
            # Retry once without tools as a fallback
            print(f"[agent] tool-call request failed ({e}), retrying without tools...")
            payload.pop("tools", None)
            try:
                resp = requests.post(
                    f"{self.host}/api/chat",
                    json=payload,
                    timeout=120,
                )
                resp.raise_for_status()
                data = resp.json()
                return data["message"]
            except Exception as e2:
                return {"role": "assistant", "content": f"Error contacting Ollama: {e2}"}
