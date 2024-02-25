from urllib.parse import urlparse
import os
import json
import requests

def file_download(url: str):
    """
    Downloads a file from a url to the workspace directory.

        Args:
            url (str): The link to download the file.

        Returns:
            Tuple[str, Optional[str]]: A message about the process status and the filename, if processed.
    """
    save_directory = "./workspace/"
    file_name = os.path.basename(urlparse(url).path)
    save_path = os.path.join(save_directory, file_name)
        
    if os.path.isfile(save_path):
        return json.dumps(f'The file {file_name} already exists.')
    else:
        try:
            response = requests.get(url)
            response.raise_for_status()
            with open(save_path, 'wb') as file:
                file.write(response.content)
        except requests.exceptions.RequestException as e:
            return json.dumps(f"Failed to download the file: {e}")

        return json.dumps(f'File downloaded and is located at {save_path}.')