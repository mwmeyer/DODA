"""Git-aware directory tree widget."""
from textual.widgets import DirectoryTree
from textual.widgets._directory_tree import DirEntry
from typing import Iterable
import os
from pathlib import Path
from textual.worker import Worker, get_current_worker
from textual.reactive import var

class GitDirectoryTree(DirectoryTree):
    """A directory tree that only shows Git repositories."""
    
    show_only_git = var(False)  # Toggle for showing only git repos, start with showing all

    def has_git_repo(self, path: Path) -> bool:
        """Check if this directory or any subdirectory has a .git folder."""
        # First check current directory
        git_path = path / '.git'
        if git_path.exists():
            self.app.log(f"Found git repo at {path}")
            return True
        
        # Then check immediate subdirectories only
        try:
            for item in path.iterdir():
                if item.is_dir():
                    git_path = item / '.git'
                    if git_path.exists():
                        self.app.log(f"Found git repo in subdirectory {item}")
                        return True
        except (PermissionError, OSError):
            pass
        
        return False

    def toggle_git_only(self) -> None:
        """Toggle between showing only git repos or all directories."""
        self.show_only_git = not self.show_only_git
        self.app.log(f"Toggled show_only_git to {self.show_only_git}")
        # Force a refresh
        self.reload()

    def _directory_content(self, path: Path, worker: Worker | None = None) -> Iterable[DirEntry]:
        """Get directory content, filtering for Git repos."""
        try:
            # Get all entries in directory
            entries = list(super()._directory_content(path, worker))
            self.app.log(f"Checking directory {path}, found {len(entries)} entries")
            
            if not self.show_only_git:
                return entries
            
            # If this directory has a .git folder, show everything in it
            if (path / '.git').exists():
                self.app.log(f"Directory {path} is a git repo, showing all entries")
                return entries
            
            # Otherwise only show directories that contain git repos
            filtered_entries = []
            for entry in entries:
                # Get the full path from the entry
                entry_path = Path(os.path.join(str(path), entry.name))
                if entry.is_dir and self.has_git_repo(entry_path):
                    filtered_entries.append(entry)
            
            self.app.log(f"Filtered down to {len(filtered_entries)} entries with git repos")
            return filtered_entries
            
        except Exception as e:
            self.app.log(f"Error in _directory_content: {e}")
            return []
