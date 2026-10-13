"""Deploy this public repo's production branch only after its GitHub checks pass."""
import json
import re
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path

REPO = 'R26-SE-041/R26-SE-041'
BRANCH = 'baskaran/expo-web-migration'
COMPONENT = 'baskaran-interactive-audio-communication'
BASE = Path('/srv/voicelearn')


def run(*args, cwd=None):
    return subprocess.run(args, cwd=cwd, check=True, text=True, capture_output=True,
                          timeout=1800).stdout.strip()


def deploy():
    origin = f'https://github.com/{REPO}.git'
    head = run('git', 'ls-remote', origin, f'refs/heads/{BRANCH}').split()[0]
    if not re.fullmatch('[0-9a-f]{40}', head):
        raise ValueError('Invalid production commit')
    marker = BASE / 'deployed-sha'
    if marker.exists() and marker.read_text().strip() == head:
        print('Current release is up to date.')
        return
    query = urllib.parse.urlencode({'branch': BRANCH, 'head_sha': head, 'per_page': 10})
    request = urllib.request.Request(
        f'https://api.github.com/repos/{REPO}/actions/workflows/voicelearn-backend.yml/runs?{query}',
        headers={'Accept': 'application/vnd.github+json', 'User-Agent': 'VoiceLearn-deploy'})
    with urllib.request.urlopen(request, timeout=20) as response:
        runs = json.load(response)['workflow_runs']
    approved = any(r['head_sha'] == head and r['head_branch'] == BRANCH
                   and r['event'] in {'push', 'workflow_dispatch'}
                   and r['status'] == 'completed' and r['conclusion'] == 'success' for r in runs)
    if not approved:
        print('Latest commit has no successful backend checks; current release retained.')
        return
    release = BASE / 'releases' / head
    release.mkdir(parents=True, exist_ok=True)
    if not (release / '.git').exists():
        run('git', 'init', str(release))
        run('git', 'remote', 'add', 'origin', origin, cwd=release)
    run('git', 'sparse-checkout', 'init', '--cone', cwd=release)
    run('git', 'sparse-checkout', 'set', COMPONENT, cwd=release)
    run('git', 'fetch', '--depth=1', '--filter=blob:none', 'origin', head, cwd=release)
    run('git', 'checkout', '--detach', 'FETCH_HEAD', cwd=release)
    app = release / COMPONENT
    print(f'Deploying verified commit {head}', flush=True)
    # Do not emit Docker environment files or credentials into service logs.
    current = BASE / 'current'
    previous = current.resolve() if current.is_symlink() else None
    try:
        run('bash', str(app / 'deploy/ec2/deploy.sh'))
    except subprocess.SubprocessError:
        if previous and (previous / 'deploy/ec2/deploy.sh').is_file():
            print('Release failed; restoring the previous application release.', flush=True)
            run('bash', str(previous / 'deploy/ec2/deploy.sh'))
        raise
    next_link = BASE / 'current-next'
    if next_link.is_symlink():
        next_link.unlink()
    next_link.symlink_to(app, target_is_directory=True)
    next_link.replace(current)
    marker.write_text(head + '\n')
    print('Backend deployment passed health; persistent data retained.')


if __name__ == '__main__':
    try:
        deploy()
    except Exception as error:
        print(f'Automatic deployment failed: {type(error).__name__}; inspect the release manually.')
        raise SystemExit(1)
