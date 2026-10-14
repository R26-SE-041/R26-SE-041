import importlib.util
import json
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location('modal_status', Path(__file__).resolve().parents[2] / 'deploy/ec2/modal-status.py')
status = importlib.util.module_from_spec(spec)
spec.loader.exec_module(status)

def setup_files(tmp_path):
    for profile in status.PROFILES:
        endpoints = {f'MODEL_{i}': f'https://{profile}-{i}.modal.run' for i in range(3)}
        (tmp_path / f'{profile}.json').write_text(json.dumps({'endpoints': endpoints}))
    env = tmp_path / 'backend.env'
    env.write_text('SECRET=private\n' + '\n'.join(f'MODEL_{i}=https://visakanbaskaran-{i}.modal.run' for i in range(3)))
    return env

def test_infers_initial_workspace_without_marker_and_never_changes_env(tmp_path):
    env = setup_files(tmp_path)
    before = env.read_bytes()
    assert status.selected_workspace(env, tmp_path) == 'visakanbaskaran'
    assert env.read_bytes() == before

def test_mixed_workspace_endpoints_are_rejected(tmp_path):
    env = setup_files(tmp_path)
    env.write_text(env.read_text().replace('visakanbaskaran-1', 'varananrp-1'))
    with pytest.raises(ValueError):
        status.selected_workspace(env, tmp_path)

def test_stale_marker_is_rejected(tmp_path):
    env = setup_files(tmp_path)
    env.write_text(env.read_text() + '\nMODAL_WORKSPACE=varananrp\n')
    with pytest.raises(ValueError):
        status.selected_workspace(env, tmp_path)
