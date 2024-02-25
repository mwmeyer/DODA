from internal.functions import run_command
import subprocess

def git_diff(repo_name):
    """Function to return a git diff"""
    command = f'git -C ./workspace/{repo_name} diff'
    output = subprocess.run(command, shell=True, check=True, capture_output=True, text=True).stdout
    return { "output": output, "show_collapsible": True }