from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Grid, Container, Center, Middle, Vertical, Horizontal, VerticalScroll
from textual.widget import Widget
from textual.reactive import var, reactive
from textual.widgets import Collapsible, DirectoryTree, Button, Footer, Header, Input, Static, TabbedContent, TabPane, Label, ListItem, ListView, ProgressBar, TextArea
from textual.screen import ModalScreen, Screen
from textual import on
from rich.syntax import Syntax
from rich.traceback import Traceback
import pyperclip
from chat import Conversation
import json
import os
from datetime import datetime

class WorkspaceScreen(Screen):
    BINDINGS = [("escape", "app.pop_screen", "Back to chat"),
                Binding("ctrl+s", "save_current_file", "Save File", key_display="Ctrl+S")]

    current_file_path = None

    def action_save_current_file(self):
        # Retrieve the current content from the TextArea
        text_area = self.query_one("#workspace-textarea", TextArea)
        file_content = text_area.text
        # Check if there's a currently opened file path stored
        if hasattr(self, 'current_file_path') and self.current_file_path:
            try:
                # Write the content back to the file
                with open(self.current_file_path, 'w') as file:
                    file.write(file_content)
                self.notify("File saved successfully.")
            except Exception as e:
                self.notify(f"Failed to save file: {e}", severity="error")
        else:
            self.notify("No file is currently opened.")

    def get_syntax(self, path):
        extension_to_language = {
            "py": "python", "md": "markdown", "json": "json", "yml": "yaml", "yaml": "yaml", "css": "css", "sql": "sql"
        }
        file_extension = path.split('.')[-1]
        language = extension_to_language.get(file_extension)
        return language

    def open_file(self, text_element, path):
        str_path = str(path)
        self.current_file_path = str_path
        with open(str_path) as file:
            try:
                syntax = self.get_syntax(str_path)
            except Exception as e:
                syntax = 'markdown'

            text_element.language = syntax
            text_element.theme = 'monokai'
            text_element.show_line_numbers = True

            text_element.load_text(file.read())

        text_element.focus()
        self.sub_title = str(path)

    def on_directory_tree_file_selected(
        self, event: DirectoryTree.FileSelected
    ) -> None:
        """Called when the user click a file in the directory tree."""
        event.stop()
        workspace_text = self.query_one("#workspace-textarea", TextArea)
        try:
            workspace_text.disabled = False
            self.open_file(workspace_text, event.path)
        except Exception as e:
            workspace_text.disabled = True
            workspace_text.load_text("Unsupported File Type")
        self.sub_title = str(event.path)

    def compose(self) -> ComposeResult:
        yield Header()
        with Container():
            yield DirectoryTree("./workspace", id="workspace-tree")
            yield TextArea(id="workspace-textarea")
            yield Footer()

class MessageBox(Widget, can_focus=True):  # type: ignore[call-arg]
    """Box widget for the message."""

    def __init__(self, text: str, role: str, collapsible_data=None) -> None:
        self.text = text
        self.collapsible_data = collapsible_data
        self.role = role
        super().__init__()

    def compose(self) -> ComposeResult:
        """Yield message component."""
        with Container(classes="message-container"):
            yield Static(self.text, classes=f"message-text {self.role}")
            if self.collapsible_data:
                with Collapsible(title="Show More", classes="message-collapsible"):
                    yield Static(self.collapsible_data, classes="message-collapsible-content")
        yield Button("Copy 📋", classes=f"copy-btn")

class LabelItem(ListItem):

    def __init__(self, label: str) -> None:
        super().__init__()
        self.label = label

    def compose( self ) -> ComposeResult:
        yield Label(self.label, classes="prompt-label")

class NewPromptScreen(ModalScreen):
    """Screen with a dialog to quit."""

    def compose(self) -> ComposeResult:
        yield Grid(
            TextArea(id="new_prompt_textarea"),
            Button("Save", variant="success", id="modal-save-prompt"),
            Button("Cancel", variant="error", id="modal-cancel-prompt"),
            id="save_prompt_grid",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "modal-cancel-prompt":
            self.app.pop_screen()
        elif event.button.id == "modal-save-prompt":
            # get text from the textarea
            new_prompt = self.query_one("#new_prompt_textarea", TextArea).text
            if not new_prompt:
                self.app.pop_screen()
            else:
                # append it to the prompts file
                with open(self.app.prompts_file_path, 'r') as file:
                    prompts = json.load(file)
                    prompts['tab_pane'].append(new_prompt)
                    # write it back to the file
                    with open(self.app.prompts_file_path, 'w') as file:
                        json.dump(prompts, file, indent=4)
                self.query_one("#new_prompt_textarea", TextArea).text = ""
                self.dismiss(new_prompt)

class DodaTUI(App):
    TITLE = "DODA"
    SUB_TITLE = "Offers Dev Assistance"
    CSS_PATH = "static/styles.css"
    SCREENS = {"workspace": WorkspaceScreen, "new_prompt": NewPromptScreen}
    BINDINGS = [
        Binding("q", "quit", "Quit", key_display="Q / CTRL+C"),
        ("ctrl+b", "toggle_sidebar", "Sidebar"),
        ("ctrl+t", "push_screen('workspace')", "Workspace")
    ]

    show_sidebar = var(True)
    conversation = Conversation()

    prompts_file_path = "./internal/prompts.json"
    
    history_file_path = "./internal/history.json"
    def __init__(self) -> None:
        """Initialize the app."""
        super().__init__()
        # Create history file if it doesn't exist
        if not os.path.isfile(self.history_file_path):
            # create it with an empty object
            with open(self.history_file_path, 'w') as file:
                file.write("{}")

    def watch_show_sidebar(self, show_sidebar: bool) -> None:
        """Called when show_sidebar is modified."""
        self.set_class(show_sidebar, "-show-sidebar")

    def on_list_view_selected(self, event: ListView.Selected):
        self.query_one("#message_input",Input).value = event.item.label

    def compose(self) -> ComposeResult:
        """Yield components."""
        yield Header()
        with Horizontal():
            with Vertical(id="sidebar"):
                with TabbedContent():
                    with TabPane("Prompts", id="prompts_tab"):
                        yield ListView(id="prompt_items_list_view")
                        yield Button("Create New Prompt", id="create_prompt_button")
                    with TabPane("History"):
                        with open(self.history_file_path, 'r') as file:
                            history = json.load(file)
                            total_tokens = sum(len(message["content"].split()) for date, messages in history.items() for message in messages)
                            yield Static(f'Token Count: {total_tokens}', classes="history-tokens")
                            for date, messages in history.items():
                                with Static(classes='history-container'):
                                    yield Label(date, classes="history-date")
                                    for message in messages:
                                            yield Static(f'{message["role"]}:')
                                            yield Static(message["content"], classes="history-message")
            with Vertical():
                with VerticalScroll(id="conversation_box"):
                    yield Static("Welcome, type your request and I'll do my best!", classes="message")
                with Center(id="progress_bar_container"):
                        with Middle():
                            yield ProgressBar(show_eta=False, show_percentage=False)
                with Horizontal(id="input_box"):
                    yield Input(placeholder="Enter your message", id="message_input")
                    yield Button(label="Send", variant="primary", id="send_button")
        yield Footer()

    def on_mount(self) -> None:
        """Start the conversation and focus input widget."""
        self.query_one(Input).focus()

        with open(self.prompts_file_path, 'r') as file:
            prompts = json.load(file)['tab_pane']
            self.query_one("#prompt_items_list_view").extend([LabelItem(prompt) for prompt in prompts])

    def new_prompt_dismiss_callback(self, prompt_val: str) -> None:
        """Called when NewPromptScreen is dismissed."""
        if prompt_val:
            self.notify("new prompt created!")
            self.query_one("#prompt_items_list_view").append(LabelItem(prompt_val))
                
    @on(Button.Pressed, "#create_prompt_button")
    def on_save_prompt_button_pressed(self, event: Button.Pressed):
        self.app.push_screen('new_prompt', self.new_prompt_dismiss_callback)

    @on(Button.Pressed, ".copy-btn")  
    def copy(self, event: Button.Pressed):
        """Called when the message copy button called."""
        pyperclip.copy(event.button.parent.text)
        self.notify("copied!")

    def action_toggle_sidebar(self) -> None:
        """Called in response to key binding."""
        self.show_sidebar = not self.show_sidebar

    @on(Button.Pressed, "#send_button")
    async def on_send_button_button_pressed(self) -> None:
        """Process when send was pressed."""
        await self.process_conversation()

    async def on_input_submitted(self) -> None:
        """Process when input was submitted."""
        await self.process_conversation()

    async def process_conversation(self) -> None:
        """Process a single question/answer in conversation."""
        message_input = self.query_one("#message_input", Input)
        # Don't do anything if input is empty
        if message_input.value == "":
            return
        button = self.query_one("#send_button")
        conversation_box = self.query_one("#conversation_box")

        self.toggle_widgets(message_input, button, show_progress=True)

        # Create question message, add it to the conversation and scroll down
        message_box = MessageBox(message_input.value, "question")
        conversation_box.mount(message_box)
        conversation_box.scroll_end(animate=False)

        # Clean up the input without triggering events
        with message_input.prevent(Input.Changed):
            message_input.value = ""

        # Take answer from the chat and add it to the conversation
        r = await self.conversation.send(message_box.text)
        self.log_message_history([{"role": "user", "content": message_box.text}, {"role": "assistant", "content": r.get('response_content')}])

        conversation_box.mount(
            MessageBox(
                r.get('response_content'),
                "answer",
                r.get('collapsible_data')
            )
        )

        self.toggle_widgets(message_input, button, show_progress=False)
        # For some reason single scroll doesn't work
        conversation_box.scroll_end(animate=False)
        conversation_box.scroll_end(animate=False)
    
    def log_message_history(self, last_message_pair: list):
        """Append a message to the conversation history."""
        history_path = "./internal/history.json"
        try:
            with open(history_path, 'r+') as file:
                history = json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            history = {}
    
        todays_date = datetime.today().strftime('%Y-%m-%d')
        history.setdefault(todays_date, []).extend(last_message_pair)
    
        with open(history_path, 'w') as file:
            json.dump(history, file, indent=4) 

    def toggle_widgets(self, *widgets: Widget, show_progress: False) -> None:
        """Toggle a list of widgets."""
        self.set_class(show_progress, "-show-progress-bar")
        for w in widgets:
            w.disabled = not w.disabled