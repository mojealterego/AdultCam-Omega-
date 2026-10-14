# AdultCam Omega - independent production acceptance

Status: 1.0.0rc1 / NOT_PRODUCTION_READY.

Release 1.0.0 requires nine independently witnessed and reviewed real-environment acceptance checks:

1. real_obs_studio_start_stop - actual installed OBS and loss/recovery test.
2. authorized_platform_api_and_delivery - permitted account API plus independent receiver confirmation, not OBS status.
3. end_to_end_privacy_fail_closed - camera through privacy transform and encoder with no unprotected frames at downstream receiver under detector failure.
4. public_private_exclusion_verified - confirmed shutdown of every public output before switching to private.
5. oidc_https_rbac_security_audit - actual HTTPS, identity provider and two-account role testing.
6. android_s24_ultra_device_acceptance - verified real Samsung device testing.
7. age_consent_and_platform_terms_review - verified adults, consent and current provider terms.
8. incident_response_and_rollback_drill - observed recovery and rollback exercise.
9. backup_restore_and_retention_review - encrypted recovery and retention assurance.

The release evidence bundle must include all checks with fresh supporting JSON files, their SHA-256 hashes and an Ed25519 signature from an independently trusted reviewer. The application verifies the public key supplied in ADULTCAM_RELEASE_REVIEW_PUBKEY. Signatures demonstrate integrity and the signer, not real-world truth by themselves; the auditor must verify original records and observations.

Validation:
  python -m pytest -q
  python -m compileall -q adultcam
  node --check adultcam/web/console.js
  python -m adultcam.rtmps_probe
  python -m adultcam.simulcast_lab --receivers 2 --duration 3
  python -m adultcam.release_gate

Without independent evidence the gate exits 2 with BLOCKED. ADULTCAM_RELEASE_MODE=production refuses startup unless OIDC, public HTTPS and evidence are verified. No mock or owned RTMP receiver receipt can substitute for genuine external platform delivery proof.

Current blockers: no real OBS device run, no genuine platform delivery observation, no proven mandatory video privacy gate before OBS, no independently audited consent/age process or phone E2E test. Thus general availability 1.0.0 is not released.
