# AdultCam Ω 0.6.0 — multioperator console & synthetic RTMPS receipt

Implemented in source:
- OIDC Authorization Code browser login with PKCE S256, one-use state,
  signed RS256 ID/access tokens, nonce and subject verification.
- Independent 15-minute server-side sessions, secure HttpOnly cookies,
  rotating CSRF and strict Origin verification; admin revocation.
- Viewer / operator / admin role policies and attribution of operator
  identity to write/audit events; hide financial data from viewers.
- External JS console (no inline scripts), logout control, Caddy HTTPS
  example while API and OBS ports remain loopback-only.
- Real encrypted localhost RTMPS media roundtrip with FFmpeg sender
  and receiver, self-signed ephemeral localhost certificate that
  the client explicitly verifies, and frame count evidence.
- Test coverage in the repository plus RTMPS CI step and runbook.

Not tested or connected:
- Physical OBS installation or real external RTMPS destination;
- Public HTTPS DNS/certificate, real IdP, mobile Samsung hardware;
- Real platform API, payout, age/consent identity verification,
  production hardening, ingest receipt, privacy masking pipeline.

**Status: 0.6.0 BETA; NOT READY FOR PRODUCTION.**
