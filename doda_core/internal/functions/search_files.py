import subprocess
import json
import os

def search_files(query: str, directory_path: str = "."):
    """Searches for a string in all files recursively using grep.

    Args:
        query (str): The search term.
        directory_path (str): The directory to search in. Defaults to ".".

    Returns:
        json: A JSON object containing the search results.
    """
    try:
        # Using grep -rn to search recursively and include line numbers
        result = subprocess.run(
            ['grep', '-rn', query, directory_path],
            capture_output=True,
            text=True,
            check=False
        )
        
        matches = []
        if result.stdout:
            for line in result.stdout.splitlines():
                if line.strip():
                    matches.append(line)
        
        return json.dumps({"matches": matches[:100]}) # Limit to top 100 matches
    except Exception as e:
        return json.dumps({"error": str(e)})
