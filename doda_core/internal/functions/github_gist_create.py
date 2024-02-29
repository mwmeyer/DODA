from github import Github, InputFileContent
import os

def github_gist_create(title, file_name, content):
    """Function to create a GitHub Gist"""
    g = Github(os.environ.get('GITHUB_TOKEN'))
    user = g.get_user()
    gist = user.create_gist(
        public=False,
        files={file_name: InputFileContent(content)},
        description=title
    )

    return {'output': f'Gist created! {gist.html_url}'}

print(github_gist_create('Test Gist', 'test.txt', 'This is a test gist!'))