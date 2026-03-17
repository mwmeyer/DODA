from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, DirectoryTree, Label, TextArea, Static, Input
from textual.message import Message
from textual.binding import Binding
from textual.screen import ModalScreen
from textual import on, work
from textual.reactive import var
import os
import shutil
from pathlib import Path

from agent import Agent


# ── Dialogs ───────────────────────────────────────────────────────────────────

class SavePathSelected(Message):
    def __init__(self, path: str) -> None:
        self.path = path
        super().__init__()


class SaveDialog(ModalScreen):
    DEFAULT_CSS = """
    SaveDialog { align: center middle; }
    #save-dialog {
        grid-size: 2; grid-gutter: 1 2; grid-rows: 4;
        padding: 1 2; width: 60; height: 11;
        border: thick $background 80%; background: $surface;
    }
    #save-prompt  { column-span: 2; height: 1; content-align: center middle; }
    #save-path    { column-span: 2; height: 3; }
    #save-button  { width: 100%; }
    #cancel-button { width: 100%; }
    """

    def compose(self) -> ComposeResult:
        with Container(id="save-dialog"):
            yield Label("Enter file path to save:", id="save-prompt")
            yield Input(value=os.path.expanduser("~"), id="save-path")
            yield Button("Save", id="save-button", variant="primary")
            yield Button("Cancel", id="cancel-button")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save-button":
            self.app.post_message(SavePathSelected(self.query_one("#save-path").value))
        self.app.pop_screen()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.app.post_message(SavePathSelected(event.value))
        self.app.pop_screen()


class DeleteConfirmed(Message):
    """Message sent when user confirms a delete."""
    def __init__(self, path: Path) -> None:
        self.path = path
        super().__init__()


class DeleteConfirmDialog(ModalScreen):
    """Confirmation dialog for deleting a file or folder."""
    DEFAULT_CSS = """
    DeleteConfirmDialog { align: center middle; }
    #delete-dialog {
        padding: 1 2; width: 60; height: 9;
        border: thick $error 60%; background: $surface;
        layout: vertical;
    }
    #delete-prompt  { height: 2; content-align: center middle; margin-bottom: 1; }
    #delete-buttons { height: 3; layout: horizontal; align: center middle; }
    #delete-yes     { margin-right: 2; }
    """

    def __init__(self, path: Path) -> None:
        super().__init__()
        self.target_path = path

    def compose(self) -> ComposeResult:
        name = self.target_path.name
        kind = "folder" if self.target_path.is_dir() else "file"
        with Container(id="delete-dialog"):
            yield Label(f"Delete {kind} [bold]{name}[/bold]?", id="delete-prompt")
            with Horizontal(id="delete-buttons"):
                yield Button("Delete", id="delete-yes", variant="error")
                yield Button("Cancel", id="delete-no")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "delete-yes":
            self.app.post_message(DeleteConfirmed(self.target_path))
        self.app.pop_screen()


class ShortcutsDialog(ModalScreen):
    """Dialog displaying keyboard shortcuts and instructions."""
    DEFAULT_CSS = """
    ShortcutsDialog { align: center middle; }
    #shortcuts-dialog {
        padding: 1 2; width: 60; height: 19;
        border: thick $primary 80%; background: $surface;
        layout: vertical;
    }
    #shortcuts-title { height: 2; content-align: center middle; text-style: bold; color: $accent; }
    #shortcuts-content { height: 1fr; margin-bottom: 1; }
    #shortcuts-close { width: 100%; }
    """

    def compose(self) -> ComposeResult:
        shortcuts = """\
[bold]Global Shortcuts[/bold]
Ctrl+S       : Save current file
Ctrl+Q       : Quit DODA
Ctrl+B       : Toggle file sidebar
Ctrl+C       : Toggle chat panel
Ctrl+V       : Voice input (coming soon)
?            : Show this help dialog

[bold]File Explorer[/bold]
d / Delete   : Delete selected file or folder
Enter        : Open file in editor

[bold]Chat[/bold]
Enter        : Send message (in input box)
"""
        with Container(id="shortcuts-dialog"):
            yield Label("DODA Keyboard Shortcuts", id="shortcuts-title")
            yield Static(shortcuts, id="shortcuts-content")
            yield Button("Got it", id="shortcuts-close", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "shortcuts-close":
            self.app.pop_screen()


# ── Tree with delete support ──────────────────────────────────────────────────

class WorkspaceTree(DirectoryTree):
    """DirectoryTree with delete support via 'd' or 'Delete' key."""

    BINDINGS = [
        Binding("d", "delete_node", "Delete", show=True),
        Binding("delete", "delete_node", "Delete"),
    ]

    def action_delete_node(self) -> None:
        """Delete the currently highlighted file or directory."""
        if self.cursor_node and self.cursor_node.data:
            path = self.cursor_node.data.path
            self.app.push_screen(DeleteConfirmDialog(Path(path)))


# ── Chat widgets ──────────────────────────────────────────────────────────────


class ChatMessage(Static):
    DEFAULT_CSS = """
    ChatMessage {
        width: 100%; margin: 1 0; padding: 1;
    }
    ChatMessage.user {
        background: $primary-background; margin-right: 4;
        border: solid $primary;
    }
    ChatMessage.assistant {
        background: $surface; margin-left: 4;
        border: solid $primary-lighten-2;
    }
    ChatMessage.tool {
        background: $boost; margin-left: 6; margin-right: 6;
        border: dashed $accent; color: $text-muted;
    }
    ChatMessage.stdout {
        background: #1a1a2e; margin-left: 8; margin-right: 2;
        padding: 0 1; margin-top: 0; margin-bottom: 0;
        color: #00ff41; border: none; height: auto;
    }
    """

    def __init__(self, sender: str, message: str) -> None:
        super().__init__()
        self.sender = sender
        self.message = message
        css_class = sender.lower().replace(" ", "-")
        if css_class in ("you", "user"):
            css_class = "user"
        elif css_class in ("assistant", "doda"):
            css_class = "assistant"
        elif "stdout" in css_class:
            css_class = "stdout"
        else:
            css_class = "tool"
        self.add_class(css_class)

    def render(self) -> str:
        if self.has_class("stdout"):
            return f"  {self.message}"
        return f"[bold]{self.sender}[/bold]: {self.message}"


class ChatInput(Container):
    DEFAULT_CSS = """
    ChatInput {
        height: auto; padding: 1; layout: horizontal;
        background: $panel; border-top: solid $primary-lighten-2;
    }
    ChatInput #chat-input { width: 1fr; margin-right: 1; }
    ChatInput #chat-send  { width: 10; min-width: 10; }
    """

    def compose(self) -> ComposeResult:
        yield Input(placeholder="Ask DODA to code something…", id="chat-input")
        yield Button("Send", id="chat-send")


# ── Main app ──────────────────────────────────────────────────────────────────

class DodaTUI(App):
    TITLE = "DODA"
    SUB_TITLE = "Offers Dev Assistance"
    CSS_PATH = "static/styles.css"

    show_sidebar = var(True)
    show_chat = var(True)
    tree_minimized = var(False)
    current_file_path = None
    workspace_dir = os.path.join(os.getcwd(), "workspace")
    has_unsaved_changes = var(False)

    BINDINGS = [
        Binding("ctrl+s", "save", "Save File", show=True),
        Binding("ctrl+q", "quit", "Quit", key_display="Q"),
        Binding("ctrl+b", "toggle_sidebar", "Sidebar"),
        Binding("ctrl+c", "toggle_chat", "Toggle Chat"),
        Binding("ctrl+v", "voice_input", "Voice"),
        Binding("?", "show_shortcuts", "Help"),
    ]

    def __init__(self):
        super().__init__()
        self.agent = Agent()

    def compose(self) -> ComposeResult:
        with Horizontal():
            with Container(id="sidebar-container"):
                with Vertical(id="sidebar-content"):
                    yield WorkspaceTree(self.workspace_dir, id="workspace-tree")
            with Container(id="editor-container"):
                with Horizontal(id="editor-header"):
                    yield Label("No file open", id="file-path-label")
                    yield Label("", id="save-status")
                    yield Button("💾", id="save-button", classes="header-button")
                yield TextArea(id="workspace-textarea")
            with Container(id="chat-container"):
                yield Static("", id="chat-messages")
                yield ChatInput()
            with Container(id="actions-container"):
                yield Button("Tree", id="tree-toggle", classes="action-button")
                yield Button("Clear", id="clear-button", classes="action-button")
                yield Button("Help", id="help-button", classes="action-button")

    def on_mount(self) -> None:
        self.query_one("#workspace-textarea").focus()
        self.sub_title = f"{self.SUB_TITLE} | {self.agent.model}"
        # Ensure workspace exists
        os.makedirs(self.workspace_dir, exist_ok=True)
        # Welcome message
        self._append_chat("DODA", f"Ready! Model: [bold]{self.agent.model}[/bold]. Ask me to build something.")
        # Show shortcuts dialog on boot
        self.push_screen(ShortcutsDialog())

    def action_show_shortcuts(self) -> None:
        """Show the shortcuts dialog."""
        self.push_screen(ShortcutsDialog())

    @on(Button.Pressed, "#help-button")
    def on_help_pressed(self, event: Button.Pressed) -> None:
        self.action_show_shortcuts()

    # ── File tree ─────────────────────────────────────────────────────────

    @on(DirectoryTree.FileSelected)
    def handle_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        try:
            if self.has_unsaved_changes:
                self.notify("Warning: You have unsaved changes!", severity="warning")
            path = Path(event.path)
            if not path.exists():
                self.notify(f"File not found: {path}", severity="error")
                return
            with open(path, "r") as f:
                content = f.read()
            text_area = self.query_one("#workspace-textarea", TextArea)
            text_area.load_text(content)
            self.query_one("#file-path-label", Label).update(str(path))
            self.current_file_path = path
            self.has_unsaved_changes = False
            self.sub_title = str(event.path)
        except Exception as e:
            self.notify(f"Error opening file: {str(e)}", severity="error")

    # ── Delete ────────────────────────────────────────────────────────────

    @on(DeleteConfirmed)
    def handle_delete_confirmed(self, message: DeleteConfirmed) -> None:
        """Handle confirmed file/folder deletion."""
        path = message.path
        try:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
            self.notify(f"Deleted {path.name}")
            self._refresh_tree()
            # Clear editor if the deleted file was open
            if self.current_file_path and Path(self.current_file_path) == path:
                self.query_one("#workspace-textarea", TextArea).load_text("")
                self.query_one("#file-path-label", Label).update("No file open")
                self.current_file_path = None
        except Exception as e:
            self.notify(f"Error deleting: {e}", severity="error")

    # ── Save ──────────────────────────────────────────────────────────────

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        if event.text_area.id == "workspace-textarea":
            self.has_unsaved_changes = True
            self.query_one("#save-status", Label).update("●")

    def action_save(self) -> None:
        if not self.current_file_path:
            self.push_screen(SaveDialog())
            return
        self._save_file()

    def _save_file(self) -> None:
        try:
            text_area = self.query_one("#workspace-textarea", TextArea)
            with open(self.current_file_path, "w") as file:
                file.write(text_area.text)
            self.has_unsaved_changes = False
            self.query_one("#save-status", Label).update("")
            self.query_one("#file-path-label", Label).update(os.path.basename(str(self.current_file_path)))
            self.notify("File saved!")
        except Exception as e:
            self.notify(f"Error saving file: {str(e)}", severity="error")

    @on(SavePathSelected)
    def handle_save_path(self, message: SavePathSelected) -> None:
        self.current_file_path = message.path
        self._save_file()

    @on(Button.Pressed, "#save-button")
    def on_save_button_pressed(self) -> None:
        self.action_save()

    # ── Sidebar / toggles ─────────────────────────────────────────────────

    def action_toggle_chat(self) -> None:
        c = self.query_one("#chat-container")
        c.display = not c.display

    def action_toggle_sidebar(self) -> None:
        self.show_sidebar = not self.show_sidebar
        self.query_one("#sidebar-container").display = self.show_sidebar
        
    def action_voice_input(self) -> None:
        self.notify("🎙️ Voice input coming soon!", title="Feature Not Implemented")

    @on(Button.Pressed, "#tree-toggle")
    def on_tree_toggle_pressed(self, event: Button.Pressed) -> None:
        self.tree_minimized = not self.tree_minimized
        self.query_one("#sidebar-container").set_class(self.tree_minimized, "minimized")

    @on(Button.Pressed, "#clear-button")
    def on_clear_pressed(self, event: Button.Pressed) -> None:
        self.agent.clear()
        self.query_one("#chat-messages", Static).update("")
        self._append_chat("DODA", "Conversation cleared. What's next?")

    # ── Chat ──────────────────────────────────────────────────────────────

    @on(Button.Pressed, "#chat-send")
    async def on_send_pressed(self, event: Button.Pressed) -> None:
        await self._handle_send()

    @on(Input.Submitted, "#chat-input")
    async def on_input_submitted(self, event: Input.Submitted) -> None:
        await self._handle_send()

    async def _handle_send(self) -> None:
        chat_input = self.query_one("#chat-input", Input)
        user_message = chat_input.value.strip()
        if not user_message:
            return
        chat_input.value = ""

        self._append_chat("You", user_message)

        # Include current file context if one is open
        text_area = self.query_one("#workspace-textarea", TextArea)
        file_content = text_area.text
        if file_content.strip() and self.current_file_path:
            context = f"[Currently viewing: {self.current_file_path}]\n```\n{file_content}\n```\n\n{user_message}"
        else:
            context = user_message

        # Run the agent loop in a worker so the TUI stays responsive
        self._run_agent(context)

    @work(thread=True)
    def _run_agent(self, message: str) -> None:
        """Run the agent loop in a background thread."""
        import asyncio

        # Set up callbacks so we can show tool activity in the chat
        def on_tool_start(name, args):
            args_short = str(args)
            if len(args_short) > 120:
                args_short = args_short[:120] + "…"
            self.call_from_thread(self._append_chat, "🔧 Tool", f"[bold]{name}[/bold]({args_short})")

        def on_tool_end(name, result):
            # Refresh tree after tools that might create/modify files
            if name in ("write_file", "edit_file", "bash"):
                self.call_from_thread(self._refresh_tree)
            if name == "bash":
                # bash output was already streamed line-by-line
                return
            preview = result[:300].replace("\n", " ") if result else "(no output)"
            if len(result) > 300:
                preview += "…"
            self.call_from_thread(self._append_chat, "✅ Result", preview)

        def on_bash_line(line):
            self.call_from_thread(self._append_chat, "💻 stdout", line)

        self.agent.on_tool_start = on_tool_start
        self.agent.on_tool_end = on_tool_end
        self.agent.on_bash_output = on_bash_line

        self.call_from_thread(self.notify, "Agent is working…")

        try:
            # Run the async send in a new event loop (we're in a thread)
            loop = asyncio.new_event_loop()
            result = loop.run_until_complete(self.agent.send(message))
            loop.close()

            response_text = result.get("response_content", "")
            if response_text:
                self.call_from_thread(self._append_chat, "DODA", response_text)

            # Refresh the file tree in case agent created new files
            self.call_from_thread(self._refresh_tree)
        except Exception as e:
            self.call_from_thread(self._append_chat, "DODA", f"[red]Error: {e}[/red]")
            self.call_from_thread(self.notify, f"Agent error: {e}", severity="error")

    def _append_chat(self, sender: str, text: str) -> None:
        """Append a message to the chat panel."""
        messages_view = self.query_one("#chat-messages", Static)
        messages_view.mount(ChatMessage(sender, text))
        messages_view.scroll_end(animate=False)

    def _refresh_tree(self) -> None:
        """Force-reload the directory tree by resetting its path."""
        try:
            tree = self.query_one("#workspace-tree", WorkspaceTree)
            tree.path = tree.path  # force full re-scan
        except Exception:
            pass