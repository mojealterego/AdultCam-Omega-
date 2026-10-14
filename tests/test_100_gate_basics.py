import pytest
from adultcam.release_gate import REQUIRED_CHECKS, evaluate_release, enforce_mode
from adultcam.app import create_app

def test_release_requires_evidence(tmp_path):
    result=evaluate_release(tmp_path/'absent.json','00'*32)
    assert result.approved is False
    assert result.status=='BLOCKED'
    assert len(REQUIRED_CHECKS)==9

def test_production_is_blocked_without_evidence(monkeypatch):
    monkeypatch.setenv('ADULTCAM_RELEASE_MODE','production')
    monkeypatch.delenv('ADULTCAM_RELEASE_BUNDLE',raising=False)
    with pytest.raises(RuntimeError,match='RELEASE_GATE_BLOCKED'):
        enforce_mode()

def test_api_startup_denies_unreviewed_production(monkeypatch):
    monkeypatch.setenv('ADULTCAM_RELEASE_MODE','production')
    monkeypatch.delenv('ADULTCAM_RELEASE_BUNDLE',raising=False)
    with pytest.raises(RuntimeError,match='RELEASE_GATE_BLOCKED'):
        create_app()
