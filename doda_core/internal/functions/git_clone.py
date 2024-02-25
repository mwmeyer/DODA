import git
import os

def git_clone(repo_url: str) -> dict:
    workspace_dir = "./workspace"
    try:
        repo_name = repo_url.split('.com')[1].split('/')[-1]
        repo_path = os.path.join(workspace_dir, repo_name)
        git.Repo.clone_from(repo_url, repo_path)
        return {'success': True, 'message': f'Repository cloned to {repo_path}.'}
    except Exception as e:
        return {'success': False, 'error': str(e)}
