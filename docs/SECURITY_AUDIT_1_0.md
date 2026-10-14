# AdultCam Omega 1.0.0rc1 - security review

Scope: source review only. This is not a real-device certification or independent penetration test.

Severity | Open issue | Production implication
--- | --- | ---
CRITICAL | Privacy frame transformer is not enforced on every live capture path entering OBS. OBS scene name is not proof of anonymity. | A camera-to-filter-to-encoder-to-receiver test must show zero unprotected frames during loss of face tracking, process crashes, switching cameras and two participants.
CRITICAL | External platform public/private transition adapters and independent STOP confirmations are not implemented. | Private transitions must stay blocked until every public output is confirmed stopped.
CRITICAL | No validated OBS Studio hardware test and no verified third-party platform delivery. | Synthetic FFmpeg, local HMAC receipts and a provider's online status do not demonstrate delivery.
HIGH | Age and consent record is primarily the operator's declaration. | Independent verification and legal/terms review required.
HIGH | OIDC/HTTPS and role controls not exercised with real IdP, public certificate or Samsung S24 Ultra. | Deployment remains blocked.
HIGH | OBS monitor is read-only; an alarm does not physically stop an unprotected broadcast. | Media-plane enforcement or a verified hardware-level failsafe needed.
MEDIUM | SQLite and session stores need encrypted backup recovery and retention tests. | Recovery not demonstrated.
MEDIUM | Owner Stats API credentials must never enter URL logs/telemetry or crash reports. | Harden operational logging.

1.0.0rc1 adds a fail-closed startup evidence gate with a pinned Ed25519 reviewer public key, hash-checked files and OIDC/HTTPS requirements. Signatures alone are not independent certification of physical events.

Decision: NOT_PRODUCTION_READY. Complete and review all acceptance criteria documented in RELEASE_1_0_ACCEPTANCE.md before any 1.0.0 general-availability release.
