import os
import json

def file_read(file_path: str):
        """Reads the content of a file.

        Args:
            file_path (str): The path to the file.

        Returns:
        json: A JSON object containing the content of the file.
        """
        try:
            if not os.path.isfile(file_path):
                return json.dumps({"error": "File not found"})

            with open(file_path, 'r') as file:
                content = file.read()

            return json.dumps({"content": content})
        except Exception as e:
            return json.dumps({"error": str(e)})
