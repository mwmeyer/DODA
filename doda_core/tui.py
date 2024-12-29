from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Grid, Container, Horizontal, VerticalScroll
from textual.widget import Widget
from textual.reactive import var
from textual.widgets import DirectoryTree, Button, Input, Static, TextArea, Label, Select
from textual import on
from textual.widgets._select import SelectCurrent
from textual.message import Message
import json
from chat import Conversation
import os

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

class VoiceMode(Container):
    """Voice mode widget."""
    
    def __init__(self) -> None:
        super().__init__()
        self.is_listening = False
    
    def compose(self) -> ComposeResult:
        """Compose the voice mode widget."""
        yield Label("Voice Mode", id="voice-status")
        yield Button("🎤", variant="default", id="voice-toggle")
    
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

class ChatInput(Container):
    """Chat input container with model selection."""
    
    DEFAULT_CSS = """
    ChatInput {
        height: auto;
        padding: 1;
        layout: horizontal;
        background: $panel;
        border-top: solid $primary-lighten-2;
    }
    
    ChatInput #model-select {
        width: 20;
        margin-right: 1;
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
        yield Select(
            [(model, model) for model in ["GPT-4", "GPT-3.5"]], 
            id="model-select",
            value="GPT-4"
        )
        yield Input(placeholder="Ask about the code...", id="chat-input")
        yield Button("Send", variant="primary", id="chat-send")

class DodaTUI(App):
    """DODA TUI application."""
    
    TITLE = "DODA"
    SUB_TITLE = "Offers Dev Assistance"
    CSS_PATH = "static/workspace.css"
    
    show_sidebar = var(True)
    show_chat = var(True)
    voice_mode = var(False)
    conversation = Conversation()
    current_file_path = None
    home_dir = os.path.expanduser("~")
    has_unsaved_changes = var(False)

    BINDINGS = [
        Binding("q", "quit", "Quit", key_display="Q / CTRL+C"),
        Binding("ctrl+b", "toggle_sidebar", "Sidebar"),
        Binding("ctrl+s", "save_current_file", "Save File", key_display="Ctrl+S"),
        Binding("ctrl+\\", "toggle_chat", "Toggle Chat"),
        Binding("ctrl+v", "toggle_voice", "Voice Mode", key_display="Ctrl+V")
    ]

    def compose(self) -> ComposeResult:
        """Compose our UI."""
        with Horizontal():
            with Container(id="sidebar-container"):
                yield DirectoryTree(self.home_dir, id="workspace-tree")
            with Container(id="editor-container"):
                with Horizontal(id="editor-header"):
                    yield Label("", id="file-path-label")
                    yield Label("", id="save-status")
                yield TextArea(id="workspace-textarea", language="python")
            with Container(id="chat-container"):
                with VerticalScroll(id="chat-messages"):
                    yield Static("Welcome! Open a file and ask questions about the code.", id="messages-view")
                yield ChatInput()
            yield VoiceMode()

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        """Handle text area changes."""
        if event.text_area.id == "workspace-textarea":
            self.has_unsaved_changes = True
            save_status = self.query_one("#save-status", Label)
            save_status.update("*")

    def action_save_current_file(self) -> None:
        """Save the current file."""
        text_area = self.query_one("#workspace-textarea", TextArea)
        file_content = text_area.text
        if self.current_file_path:
            try:
                with open(self.current_file_path, 'w') as file:
                    file.write(file_content)
                self.has_unsaved_changes = False
                save_status = self.query_one("#save-status", Label)
                save_status.update("")
                self.notify("File saved successfully!")
            except Exception as e:
                self.notify(f"Error saving file: {str(e)}", severity="error")
        else:
            self.notify("No file is currently open", severity="warning")

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        """Handle file selection."""
        try:
            if self.has_unsaved_changes:
                self.notify("Warning: You have unsaved changes!", severity="warning")
            
            self.current_file_path = str(event.path)
            with open(event.path) as file:
                content = file.read()
            
            text_area = self.query_one("#workspace-textarea", TextArea)
            text_area.load_text(content)
            
            extension = event.path.suffix.lower()
            if extension in ['.py', '.js', '.html', '.css', '.json']:
                text_area.language = extension[1:]  # Remove the dot
            
            # Update file path label and save status
            file_label = self.query_one("#file-path-label", Label)
            file_label.update(os.path.basename(self.current_file_path))
            save_status = self.query_one("#save-status", Label)
            save_status.update("")
            self.has_unsaved_changes = False
            
            self.sub_title = str(event.path)
        except Exception as e:
            self.notify(f"Error opening file: {str(e)}", severity="error")

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

    def on_voice_mode_voice_toggled(self, event: VoiceMode.VoiceToggled) -> None:
        """Handle voice mode toggle."""
        self.voice_mode = event.is_listening
        self.show_chat = not self.voice_mode
        self.query_one("#chat-container").display = not self.voice_mode
        
        if event.is_listening:
            self.notify("Voice mode activated! (Not yet implemented)")
        else:
            self.notify("Voice mode deactivated")

    @on(Button.Pressed, "#voice-mode-toggle")
    def on_voice_toggle_pressed(self, event: Button.Pressed) -> None:
        """Handle voice mode toggle button press."""
        self.action_toggle_voice()
        # Update button appearance based on mode
        button = self.query_one("#voice-mode-toggle", Button)
        button.variant = "error" if self.voice_mode else "primary"

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
        messages_view = self.query_one("#messages-view", Static)
        model_select = self.query_one("#model-select", Select)
        
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