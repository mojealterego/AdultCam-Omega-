# AdultCam Ω 0.6 — RTMPS TLS synthetic reception test

Execute on a trusted machine with FFmpeg and OpenSSL installed:

    python -m adultcam.rtmps_probe

This starts a real localhost FFmpeg RTMP receiver, local Python TLS
server, and FFmpeg sender of synthetic color bars (160x90, 5 fps).
An ephemeral certificate with IP:127.0.0.1 SAN is created inside
a private temporary directory; FFmpeg explicitly validates it using
-tls_verify 1 and -ca_file. All network endpoints bind to 127.0.0.1.
The receiver discards video frames and reports their count; no user
stream keys, real-person video, provider connections or media files.

Passing means:
verification=RECEIVER_VIDEO_FRAMES, tls_verified=true,
video_frames >= 3, receiver_exit_status=0, sender_exit_status=0.
Always report platform_delivery=UNVERIFIED, obs_tested=false.

This is **not** OBS Studio E2E; it is also not a third-party RTMPS
ingest receipt or validation of a public production CA certificate.

## Manual real-device OBS acceptance remains open

1. On the actual OBS host, configure synthetic test bars only.
2. Run python -m adultcam.obs_acceptance --check --port 19350.
3. Use docs/OBS_PRIVATE_INGEST_0_4.md for loopback RTMP testing
   with a real human starting and stopping a real OBS instance.
4. For an external RTMPS acceptance test, use an operator-authorized
   receiver with a trusted publicly verified certificate and test key.
5. Record timestamp, software versions, GetStreamStatus, target
   (without stream key), receiver proof, shutdown confirmation,
   failure/reconnect behavior and operator approval.
6. Do not mark external transmission successful until there is
   a verifiable destination receipt, not just OBS_OUTPUT_ONLY.

Real OBS installation, actual external RTMPS destination and
Samsung S24 Ultra browser tests have NOT been performed.
