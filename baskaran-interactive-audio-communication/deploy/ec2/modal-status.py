"""Report the selected workspace without inference or printing credentials."""
import argparse
import json
from pathlib import Path

PROFILES = ('visakanbaskaran', 'krishnavaranan1', 'krishnavaranan', 'varananrp')

def selected_workspace(env_file, manifest_dir):
    values = {}
    for line in env_file.read_text(encoding='utf-8-sig').splitlines():
        line = line.strip()
        if line.startswith('export '):
            line = line[7:]
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        values[key.strip()] = value.strip().strip('\"\'')
    matches = []
    for profile in PROFILES:
        manifest = manifest_dir / (profile + '.json')
        if not manifest.is_file():
            continue
        endpoints = json.loads(manifest.read_text(encoding='utf-8'))['endpoints']
        configured = [(key, value) for key, value in endpoints.items() if values.get(key)]
        if len(configured) >= 3 and all(values[key] == value for key, value in configured):
            matches.append(profile)
    if len(matches) != 1:
        raise ValueError('Configured model endpoints do not identify one workspace. No settings changed.')
    marker = values.get('MODAL_WORKSPACE')
    if marker and marker != matches[0]:
        raise ValueError('Workspace marker and model endpoints disagree. No settings changed.')
    return matches[0]

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', type=Path, default=Path('/etc/voicelearn/backend.env'))
    parser.add_argument('--manifest-dir', type=Path, default=Path('/srv/voicelearn/current/backend/modal_workspaces'))
    args = parser.parse_args()
    try:
        print('MODAL_WORKSPACE=' + selected_workspace(args.env_file, args.manifest_dir))
    except (ValueError, OSError, KeyError):
        parser.exit(1, 'Cloud workspace could not be identified safely. No settings changed.\n')
