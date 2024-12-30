"""Git preview widget that shows repository status."""
from textual.widgets import Static, Button
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.message import Message
from pathlib import Path
import subprocess
from typing import Optional

class FileSelected(Message):
    """Message sent when a file is selected in the git preview."""
    def __init__(self, path: str, is_modified: bool) -> None:
        self.path = path
        self.is_modified = is_modified
        super().__init__()

class ClickableFile(Static):
    """A clickable file entry that can show its diff."""
    def __init__(self, path: str, is_modified: bool = True):
        self.file_path = path
        self.is_modified = is_modified
        super().__init__(f"• {path}")
    
    def on_click(self) -> None:
        """Handle click event."""
        self.app.post_message(FileSelected(self.file_path, self.is_modified))

class GitPreview(Container):
    """Widget to display Git repository information."""
    
    current_repo: Optional[Path] = reactive(None)
    
    DEFAULT_CSS = """
    GitPreview {
        layout: vertical;
        height: 2fr;
        min-height: 5;
        width: 100%;
        border-top: solid $primary;
    }
    
    #git-content {
        height: 1fr;
        width: 100%;
        overflow: auto;
        padding: 1;
    }
    
    #git-actions {
        width: 100%;
        height: 3;
        dock: bottom;
        background: $panel;
        border-top: solid $primary;
    }
    
    #git-actions Button {
        width: 1fr;
        height: 100%;
        border: none;
    }
    """
    
    def compose(self):
        """Create child widgets."""
        yield Static("", id="git-content")
        with Horizontal(id="git-actions"):
            yield Button("Accept", id="accept-changes", variant="success", disabled=True)
            yield Button("Reject", id="reject-changes", variant="error", disabled=True)
    
    def _run_git_command(self, args: list[str]) -> str:
        """Run a git command and return its output."""
        if not self.current_repo:
            return ""
            
        try:
            result = subprocess.run(
                ["git"] + args,
                cwd=str(self.current_repo),
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return ""
    
    def get_file_diff(self, file_path: str) -> str:
        """Get the diff for a specific file."""
        diff = self._run_git_command(["diff", "--color=never", "--", file_path])
        if not diff:
            return ""
            
        # Convert git diff format to rich/textual markup
        formatted_lines = []
        for line in diff.split("\n"):
            if line.startswith("+"):
                formatted_lines.append(f"[green]{line}[/]")
            elif line.startswith("-"):
                formatted_lines.append(f"[red]{line}[/]")
            else:
                formatted_lines.append(line)
        return "\n".join(formatted_lines)
    
    def _get_change_summary(self) -> tuple[bool, list[Static]]:
        """Get a summary of changes in the repository."""
        if not self.current_repo:
            return False, [Static("No suggested changes")]
            
        try:
            # Get modified files
            modified = self._run_git_command(["diff", "--name-only"]).split("\n")
            modified = [f for f in modified if f]
            
            # Get untracked files
            untracked = self._run_git_command(["ls-files", "--others", "--exclude-standard"]).split("\n")
            untracked = [f for f in untracked if f]
            
            if not modified and not untracked:
                return False, [Static("No suggested changes")]
            
            # Build change summary
            widgets = []
            if modified:
                widgets.append(Static("Modified Files:"))
                for f in modified:  # Show all files
                    widgets.append(ClickableFile(f, True))
                    
            if untracked:
                if widgets:
                    widgets.append(Static(""))
                widgets.append(Static("Untracked Files:"))
                for f in untracked:  # Show all files
                    widgets.append(ClickableFile(f, False))
            
            return True, widgets
            
        except Exception as e:
            return False, [Static(f"Error: {str(e)}")]
    
    def watch_current_repo(self, repo: Optional[Path]) -> None:
        """React to changes in the current repository."""
        self.refresh_status()
    
    def refresh_status(self) -> None:
        """Refresh the displayed Git status."""
        has_changes, widgets = self._get_change_summary()
        
        # Update buttons state
        accept_btn = self.query_one("#accept-changes", Button)
        reject_btn = self.query_one("#reject-changes", Button)
        accept_btn.disabled = not has_changes
        reject_btn.disabled = not has_changes
        
        # Update content
        content = self.query_one("#git-content", Static)
        content.remove_children()
        for widget in widgets:
            content.mount(widget)
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "accept-changes":
            try:
                self._run_git_command(["add", "."])
                self._run_git_command(["commit", "-m", "Accepted changes"])
                self.app.notify("Changes committed successfully!", severity="information")
            except Exception as e:
                self.app.notify(f"Error committing changes: {e}", severity="error")
            
        elif event.button.id == "reject-changes":
            try:
                self._run_git_command(["reset", "--hard"])
                self._run_git_command(["clean", "-fd"])  # Also remove untracked files
                self.app.notify("Changes discarded successfully!", severity="information")
            except Exception as e:
                self.app.notify(f"Error discarding changes: {e}", severity="error")
            
        self.refresh_status()
