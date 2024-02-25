import gitlab
import os

def gitlab_snippet_create(title, file_name, content):
    """Function to create a gitlab snippet"""
    gl = gitlab.Gitlab('https://gitlab.com', private_token=os.environ.get('GITLAB_PRIVATE_TOKEN'))
    snippet = gl.snippets.create({
        'title': title,
        'visibility': 'public',
        'files': [{
            'file_path': file_name,
            'content': content
        }],
    })

    return {'output': f'Snippet created! {snippet.web_url}'}