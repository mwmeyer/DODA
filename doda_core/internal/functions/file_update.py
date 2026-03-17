import os
import json

def file_update(file_path: str, content: str):
        """Updates the content of a file (overwrites it).

        Args:
            file_path (str): The path to the file.
            content (str): The new content for the file.

        Returns:
        json: A JSON object containing the status of the update.
        """
        try:
            if not os.path.isfile(file_path):
                return json.dumps({"error": "File not found"})

            with open(file_path, 'w') as file:
                file.write(content)

            return json.dumps({"status": "success"})
        except Exception as e:
            return json.dumps({"error": str(e)})
