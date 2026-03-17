import os
import json

def list_files(directory_path: str = "."):
    """Lists all files in a directory recursively.

    Args:
        directory_path (str): The path to the directory. Defaults to ".".

    Returns:
        json: A JSON object containing the list of files.
    """
    try:
        files_list = []
        for root, dirs, files in os.walk(directory_path):
            # Skip hidden directories and .venv
            dirs[:] = [d for d in dirs if not d.startswith('.') and d != '.venv']
            for file in files:
                if not file.startswith('.'):
                    rel_path = os.path.relpath(os.path.join(root, file), directory_path)
                    files_list.append(rel_path)
        
        return json.dumps({"files": files_list})
    except Exception as e:
        return json.dumps({"error": str(e)})
