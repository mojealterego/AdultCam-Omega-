# AdultCam Ω v0.4.0 — lokalny test realnego transportu i manual recovery gate

- Naprawiono poważny błąd bezpieczeństwa: sam `POST /api/obs/check` mógł
  automatycznie przełączyć `RECOVERY → LIVE_PUBLIC` przy ponownej aktywności OBS.
- Dodano jawne, rejestrowane w audycie `POST /api/obs/recovery/approve`
  z zatwierdzeniem operatora i odczytowym sprawdzeniem OBS bez uruchamiania emisji.
- Ograniczono niezabezpieczone `rtmp://` do loopback, wymagając `rtmps://`
  dla adresów zdalnych w allowliście transmisji.
- Dodano rzeczywisty test transportu RTMP localhost z syntetyczną emisją FFmpeg,
  odbiorem klatek i wynikowym JSON; oddzielny tryb nasłuchu testowego OBS.
- Dodano testy regresji, test rzeczywistego transportu i dokumentację odbioru.
- Zaktualizowano panel operatora, wersję aplikacji, bramkę CI i roadmapę.

## Dowody i nieukończone wymagania

- Próba transportu używa FFmpeg, a nie prawdziwego OBS Studio.
- Nie stwierdzono rzeczywistego odbioru transmisji na zewnętrznej platformie.
- Nadal nie wdrożono OIDC, RBAC, mTLS, trwałej konfiguracji wielu platform,
  autoanonimizacji twarzy ani zatwierdzonej operacyjnej integracji z platformami.
- To wydanie nie uzyskało statusu READY_FOR_PRODUCTION.
