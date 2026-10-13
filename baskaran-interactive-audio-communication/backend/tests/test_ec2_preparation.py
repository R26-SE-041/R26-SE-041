import importlib.util
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'deploy/ec2' / (name+'.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def test_release_excludes_private_data_and_env():
    files = [name for _, name in module('package_release').source_files()]
    assert 'backend/app/main.py' in files
    assert 'deploy/ec2/compose.yaml' in files
    assert all(not any(part.startswith('.') or part.startswith('local_') or part=='chroma_data' for part in Path(name).parts[:-1]) for name in files)
    assert not any(name.endswith('.env') for name in files)


def test_preflight_rejects_example_credentials():
    check = module('validate_env')
    with pytest.raises(ValueError, match='Configure'):
        check.validate(check.read_env(ROOT/'deploy/ec2/backend.env.example'),
                       check.read_env(ROOT/'deploy/ec2/openclaw.env.example'),
                       check.read_env(ROOT/'deploy/ec2/compose.env.example'))


def test_ec2_stack_keeps_internal_services_on_loopback_and_persists_data():
    import yaml
    services = yaml.safe_load((ROOT/'deploy/ec2/compose.yaml').read_text())['services']
    assert services['backend']['environment']['REQUIRE_AUTH'] == 'true'
    assert services['backend']['environment']['ACTIONS_ALLOW_LOCAL_GUEST'] == 'false'
    assert '/srv/voicelearn/data:/data' in services['backend']['volumes']
    assert all('ports' not in service for service in services.values())
    assert '127.0.0.1' in (ROOT/'backend/Dockerfile.ec2').read_text()
    assert 'loopback' in (ROOT/'deploy/ec2/openclaw.json').read_text()
