from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, Grid
from textual.widgets import Button, DirectoryTree, Label, TextArea, Static, Input, Select
from textual.message import Message
from textual.binding import Binding
from textual.screen import ModalScreen
from textual import on
from textual.reactive import var
from textual.widgets._select import SelectCurrent
import json
from chat import Conversation
import os
from typing import Optional
from git_tree import GitDirectoryTree
from git_preview import GitPreview, FileSelected
from pathlib import Path

class SavePathSelected(Message):
    """Message sent when a save path is selected."""
    def __init__(self, path: str) -> None:
        self.path = path
        super().__init__()

class SaveDialog(ModalScreen):
    """Save file dialog."""
    
    DEFAULT_CSS = """
    SaveDialog {
        align: center middle;
    }

    #save-dialog {
        grid-size: 2;
        grid-gutter: 1 2;
        grid-rows: 4;
        padding: 1 2;
        width: 60;
        height: 11;
        border: thick $background 80%;
        background: $surface;
    }

    #save-prompt {
        column-span: 2;
        height: 1;
        content-align: center middle;
    }

    #save-path {
        column-span: 2;
        height: 3;
    }

    #save-button {
        width: 100%;
    }

    #cancel-button {
        width: 100%;
    }
    """
    
    def compose(self) -> ComposeResult:
        """Compose the save dialog."""
        with Container(id="save-dialog"):
            yield Label("Enter file path to save:", id="save-prompt")
            yield Input(value=os.path.expanduser("~"), id="save-path")
            yield Button("Save", id="save-button", variant="primary")
            yield Button("Cancel", id="cancel-button")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        if event.button.id == "save-button":
            path = self.query_one("#save-path").value
            self.app.post_message(SavePathSelected(path))
        self.app.pop_screen()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission."""
        self.app.post_message(SavePathSelected(event.value))
        self.app.pop_screen()

class ChatMessage(Static):
    """A chat message widget."""
    
    DEFAULT_CSS = """
    ChatMessage {
        width: 100%;
        margin: 1 0;
        padding: 1;
    }
    
    ChatMessage.user {
        background: $primary-background;
        margin-right: 8;
        border: solid $primary;
    }
    
    ChatMessage.assistant {
        background: $surface;
        margin-left: 8;
        border: solid $primary-lighten-2;
    }
    """
    
    def __init__(self, sender: str, message: str) -> None:
        """Initialize a chat message."""
        super().__init__()
        self.sender = sender
        self.message = message
        self.add_class(sender.lower())
    
    def render(self) -> str:
        """Render the message."""
        return f"{self.sender}: {self.message}"

class ChatInput(Container):
    """Chat input container."""
    
    DEFAULT_CSS = """
    ChatInput {
        height: auto;
        padding: 1;
        layout: horizontal;
        background: $panel;
        border-top: solid $primary-lighten-2;
    }
    
    ChatInput #chat-input {
        width: 1fr;
        margin-right: 1;
    }
    
    ChatInput #chat-send {
        width: 10;
        min-width: 10;
    }
    """
    
    def compose(self) -> ComposeResult:
        """Compose the chat input."""
        yield Input(placeholder="Ask about the code...", id="chat-input")
        yield Button("Send", id="chat-send")

class DiffView(Static):
    """A widget to display colored diffs."""
    
    def update_content(self, text: str) -> None:
        """Update the content with rich text markup."""
        self.update(text)

class DodaTUI(App):
    """DODA TUI application."""
    
    TITLE = "DODA"
    SUB_TITLE = "Offers Dev Assistance"
    CSS_PATH = "static/styles.css"
    
    show_sidebar = var(True)
    show_chat = var(True)
    voice_mode = var(False)
    tree_minimized = var(False)
    conversation = Conversation()
    current_file_path = None
    home_dir = os.path.expanduser("~")
    has_unsaved_changes = var(False)

    BINDINGS = [
        Binding("ctrl+s", "save", "Save File", show=True),
        Binding("ctrl+q", "quit", "Quit", key_display="Q / CTRL+C"),
        Binding("ctrl+b", "toggle_sidebar", "Sidebar"),
        Binding("ctrl+\\", "toggle_chat", "Toggle Chat"),
        Binding("ctrl+v", "toggle_voice", "Voice Mode", key_display="Ctrl+V")
    ]

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        with Horizontal():
            with Container(id="sidebar-container"):
                with Horizontal(id="tree-header"):
                    yield Button("Git Filter", id="git-toggle", classes="header-button")
                with Vertical(id="sidebar-content"):
                    yield GitDirectoryTree(self.home_dir, id="workspace-tree")
                    yield GitPreview(id="git-preview")
            with Container(id="editor-container"):
                with Horizontal(id="editor-header"):
                    yield Label("No file open", id="file-path-label")
                    yield Label("", id="save-status")
                    yield Button("", id="save-button", classes="header-button")
                yield TextArea(id="workspace-textarea")
                yield DiffView("", id="diff-view", classes="hidden")
            with Container(id="chat-container"):
                yield Static("Welcome! Open a file and ask questions about the code.", id="chat-messages")
                yield ChatInput()
            with Container(id="actions-container"):
                yield Button("Tree", id="tree-toggle", classes="action-button")
                yield Button("AI", id="ai-button", classes="action-button")
                yield Button("Settings", id="settings-button", classes="action-button")
                yield Button("Search", id="search-button", classes="action-button")
                yield Button("Help", id="help-button", classes="action-button")
                yield Button("Voice", variant="default", id="voice-toggle")
                yield Label("Voice Mode", id="voice-status")

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        """Handle text area changes."""
        if event.text_area.id == "workspace-textarea":
            self.has_unsaved_changes = True
            save_status = self.query_one("#save-status", Label)
            save_status.update("*")

    def action_save(self) -> None:
        """Save the current file."""
        if not self.current_file_path:
            # No file open, show save dialog
            self.push_screen(SaveDialog())
            return
        
        self._save_file()

    def _save_file(self) -> None:
        """Save the file to disk."""
        try:
            text_area = self.query_one("#workspace-textarea", TextArea)
            with open(self.current_file_path, "w") as file:
                file.write(text_area.text)
            
            self.has_unsaved_changes = False
            save_status = self.query_one("#save-status", Label)
            save_status.update("")
            
            # Update file path label after successful save
            file_label = self.query_one("#file-path-label", Label)
            file_label.update(os.path.basename(self.current_file_path))
            self.sub_title = str(self.current_file_path)
            
            self.notify("File saved successfully!")
        except Exception as e:
            self.notify(f"Error saving file: {str(e)}", severity="error")

    @on(SavePathSelected)
    def handle_save_path(self, message: SavePathSelected) -> None:
        """Handle save path selection."""
        self.current_file_path = message.path
        self._save_file()

    @on(DirectoryTree.DirectorySelected)
    def handle_directory_selected(self, event: DirectoryTree.DirectorySelected) -> None:
        """Handle directory selection in the tree."""
        # Update git preview if this is in a git repo
        git_preview = self.query_one("#git-preview", GitPreview)
        path = Path(event.path)
        if (path / ".git").exists():
            git_preview.current_repo = path
        else:
            git_preview.current_repo = None

    @on(DirectoryTree.FileSelected)
    def handle_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        """Handle file selection in the directory tree."""
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
            
            # Update file path label
            label = self.query_one("#file-path-label", Label)
            label.update(str(path))
            
            self.current_file_path = path
            self.has_unsaved_changes = False
            
            self.sub_title = str(event.path)
            
            # Update git preview if this is in a git repo
            git_preview = self.query_one("#git-preview", GitPreview)
            while path != Path("/"):
                if (path / ".git").exists():
                    git_preview.current_repo = path
                    break
                path = path.parent
            else:
                git_preview.current_repo = None
        except Exception as e:
            self.notify(f"Error opening file: {str(e)}", severity="error")

    @on(FileSelected)  
    def handle_git_file_selected(self, message: FileSelected) -> None:
        """Handle git file selection."""
        try:
            git_preview = self.query_one("#git-preview", GitPreview)
            text_area = self.query_one("#workspace-textarea", TextArea)
            diff_view = self.query_one("#diff-view", DiffView)
            
            if message.is_modified:
                # Show colored diff for modified file
                diff = git_preview.get_file_diff(message.path)
                text_area.add_class("hidden")
                diff_view.remove_class("hidden")
                diff_view.update_content(diff)
            else:
                # Show contents of untracked file
                path = git_preview.current_repo / message.path
                with open(path, "r") as f:
                    content = f.read()
                diff_view.add_class("hidden")
                text_area.remove_class("hidden")
                text_area.load_text(content)
            
            # Update file path label
            label = self.query_one("#file-path-label", Label)
            label.update(f"Git: {message.path}")
            
        except Exception as e:
            self.notify(f"Error showing file: {str(e)}", severity="error")

    def on_mount(self) -> None:
        """Handle app mount."""
        self.query_one("#workspace-textarea").focus()

    def action_toggle_chat(self) -> None:
        """Toggle the chat panel."""
        chat_container = self.query_one("#chat-container")
        chat_container.display = not chat_container.display

    def action_toggle_sidebar(self) -> None:
        """Toggle the sidebar."""
        self.show_sidebar = not self.show_sidebar
        sidebar = self.query_one("#sidebar-container")
        sidebar.display = not sidebar.display

    def action_toggle_voice(self) -> None:
        """Toggle voice mode."""
        self.voice_mode = not self.voice_mode
        self.show_chat = not self.voice_mode
        self.query_one("#chat-container").display = not self.voice_mode

    def action_toggle_tree(self) -> None:
        """Toggle tree minimized state."""
        self.tree_minimized = not self.tree_minimized
        container = self.query_one("#sidebar-container")
        container.set_class(self.tree_minimized, "minimized")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        if event.button.id == "voice-toggle":
            self.is_listening = not self.is_listening
            event.button.variant = "error" if self.is_listening else "default"
            self.post_message(self.VoiceToggled(self.is_listening))

    class VoiceToggled(Message):
        """Voice mode toggled message."""
        def __init__(self, is_listening: bool) -> None:
            self.is_listening = is_listening
            super().__init__()

    def on_voice_mode_voice_toggled(self, event: VoiceToggled) -> None:
        """Handle voice mode toggle."""
        self.voice_mode = event.is_listening
        self.show_chat = not self.voice_mode
        self.query_one("#chat-container").display = not self.voice_mode
        
        if event.is_listening:
            self.notify("Voice mode activated! (Not yet implemented)")
        else:
            self.notify("Voice mode deactivated")

    @on(Button.Pressed, "#voice-toggle")
    def on_voice_toggle_pressed(self, event: Button.Pressed) -> None:
        """Handle voice mode toggle button press."""
        self.action_toggle_voice()
        # Update button appearance based on mode
        button = self.query_one("#voice-toggle", Button)
        button.variant = "error" if self.voice_mode else "primary"

    @on(Button.Pressed, "#tree-toggle")
    def on_tree_toggle_pressed(self, event: Button.Pressed) -> None:
        """Handle tree toggle button press."""
        self.action_toggle_tree()

    @on(Button.Pressed, "#git-toggle")
    def on_git_toggle_pressed(self) -> None:
        """Handle git toggle button press."""
        tree = self.query_one("#workspace-tree", GitDirectoryTree)
        tree.toggle_git_only()
        # Update button text based on state
        button = self.query_one("#git-toggle", Button)
        button.label = "All Files" if tree.show_only_git else "Git Filter"

    @on(Button.Pressed, "#chat-send")
    async def on_send_pressed(self, event: Button.Pressed) -> None:
        """Handle send button press."""
        await self.send_chat_message()

    @on(Input.Submitted, "#chat-input")
    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission."""
        await self.send_chat_message()

    async def send_chat_message(self) -> None:
        """Send a message to the chat."""
        chat_input = self.query_one("#chat-input", Input)
        messages_view = self.query_one("#chat-messages", Static)
        
        user_message = chat_input.value
        if not user_message.strip():
            return

        self.notify("Sending message...")
        
        # Add user message
        current_content = messages_view.render()
        messages_view.update(current_content + "\n\n")
        messages_view.mount(ChatMessage("You", user_message))
        
        # Clear input
        chat_input.value = ""
        
        # Get current file content for context
        text_area = self.query_one("#workspace-textarea", TextArea)
        file_content = text_area.text
        
        try:
            # Get AI response
            context = f"Current file content:\n```\n{file_content}\n```\n\nQuestion: {user_message}"
            response = await self.conversation.send(context)
            
            # Update messages view with AI response
            current_content = messages_view.render()
            messages_view.update(current_content + "\n")
            messages_view.mount(ChatMessage("Assistant", response["response_content"]))
            
            # Scroll to bottom
            messages_container = self.query_one("#chat-messages")
            messages_container.scroll_end(animate=False)
        except Exception as e:
            self.notify(f"Error getting AI response: {str(e)}", severity="error")

    @on(Button.Pressed, "#save-button")
    def on_save_button_pressed(self) -> None:
        """Handle save button press."""
        self.action_save()