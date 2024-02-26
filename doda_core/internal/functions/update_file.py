import os
import json

def file_update(file_path: str, content: str):
        """Reads the content of a file and returns its sentences.

        Args:
            file_path (str): The path to the file.

        Returns:
        json: A JSON object containing the sentences of the file content.
        """
        try:
            if not os.path.isfile(file_path):
                return json.dumps({"error": "File not found"})

            with open(file_path, 'w') as file:
                file.write(content)

            return json.dumps({"status": "success"})
        except Exception as e:
            return json.dumps({"error": str(e)})
