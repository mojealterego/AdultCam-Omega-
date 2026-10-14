import base64
import hashlib
import json
from datetime import datetime, timedelta, timezone

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

from adultcam.release_gate import REQUIRED_CHECKS, evaluate_release


def make_bundle(tmp_path, *, fail=None, expired=False):
    key=Ed25519PrivateKey.generate()
    public=key.public_key().public_bytes(serialization.Encoding.Raw,
                                          serialization.PublicFormat.Raw).hex()
    now=datetime.now(timezone.utc)
    checks={}
    for name in REQUIRED_CHECKS:
        proof={'check_id':name,'passed':name!=fail,
               'observed_at':now.isoformat(),
               'review_reference':'audit-'+name}
        file=tmp_path/(name+'.json')
        file.write_text(json.dumps(proof))
        checks[name]={'status':'PASS','evidence':file.name,
                      'sha256':hashlib.sha256(file.read_bytes()).hexdigest()}
    manifest={'schema_version':1,'project':'AdultCam Omega','release':'1.0.0',
              'issued_at':(now-timedelta(minutes=1)).isoformat(),
              'expires_at':(now-timedelta(days=1) if expired else now+timedelta(days=1)).isoformat(),
              'checks':checks}
    canon=json.dumps(manifest,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
    manifest['signature']=base64.urlsafe_b64encode(key.sign(canon)).decode().rstrip('=')
    file=tmp_path/'release-evidence.json'
    file.write_text(json.dumps(manifest))
    return file, public


def test_signature_and_complete_artifacts_verify(tmp_path):
    file,key=make_bundle(tmp_path)
    result=evaluate_release(file,key)
    assert result.approved and result.status=='REVIEW_EVIDENCE_VERIFIED',result
    assert not evaluate_release(file,'00'*32).approved


def test_hashed_evidence_is_immutable(tmp_path):
    file,key=make_bundle(tmp_path)
    artifact=tmp_path/(REQUIRED_CHECKS[0]+'.json')
    artifact.write_bytes(artifact.read_bytes()+b' ')
    assert not evaluate_release(file,key).approved


def test_auditor_rejects_failed_and_expired_checks(tmp_path):
    fail_dir=tmp_path/'fail'
    fail_dir.mkdir()
    file,key=make_bundle(fail_dir,fail=REQUIRED_CHECKS[0])
    assert not evaluate_release(file,key).approved
    expired_dir=tmp_path/'expired'
    expired_dir.mkdir()
    file,key=make_bundle(expired_dir,expired=True)
    assert not evaluate_release(file,key).approved


def test_symlink_cannot_be_treated_as_reviewed_evidence(tmp_path):
    file,key=make_bundle(tmp_path)
    artifact=tmp_path/(REQUIRED_CHECKS[0]+'.json')
    renamed=tmp_path/'source.json'
    artifact.rename(renamed)
    artifact.symlink_to(renamed)
    assert not evaluate_release(file,key).approved
