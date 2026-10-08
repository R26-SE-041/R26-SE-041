import os
from pathlib import Path
import runpy
from unittest.mock import patch
import pytest

routing=runpy.run_path(str(Path(__file__).resolve().parents[2]/"ci/pack_vercel.py"))["api_routes"]

def test_api_route_precedes_spa_and_is_private():
    with patch.dict(os.environ,{"EXPO_PUBLIC_STUDIO_PROXY_PATH":"/studio-api","EXPO_PUBLIC_STUDIO_API_URL":"https://api.example"}):
        assert routing()==[{"src":"/studio\\-api/(.*)","dest":"https://api.example/$1","headers":{"Cache-Control":"private, no-store"}}]

def test_proxy_configuration_rejects_credentials_or_invalid_prefix():
    for origin,prefix in [("https://user:password@api.example","/studio-api"),("http://api.example","/studio-api"),("https://api.example","/.*")]:
        with patch.dict(os.environ,{"EXPO_PUBLIC_STUDIO_PROXY_PATH":prefix,"EXPO_PUBLIC_STUDIO_API_URL":origin}),pytest.raises(ValueError):
            routing()
