# AdultCam Ω 0.5.0 — OIDC JWT API i bramka bezpieczeństwa OBS

## Zmiany zaimplementowane

- Opcjonalna autoryzacja Bearer JWT podpisanym RS256 z publicznym JWKS,
  weryfikacja `iss`, `aud`, `sub`, `iat`, `exp` i timeout pobierania klucza.
- Role `viewer`, `operator`, `admin` z weryfikowanego claimu IdP,
  bez podnoszenia uprawnień przez nagłówki klienta.
- Odczyt `GET /api/auth/me` i wymóg `admin` dla księgi oraz oświadczeń.
- Rejestrowanie tożsamości operatora dla zatwierdzania OBS,
  uzgodnień RECOVERY, księgi i oświadczeń.
- Samodzielny, tylko odczytowy `python -m adultcam.obs_acceptance --check`
  dopuszcza test prawdziwego OBS wyłącznie przy dokładnym lokalnym
  serwerze RTMP, fikcyjnym kluczu i zatwierdzonej testowej scenie.
- Nowe testy bezpieczeństwa OIDC i preflight, instrukcje Android/SSH.

## Ograniczenia i bramki wydania

Brak zweryfikowanej fizycznej instancji OBS, zewnętrznego ingest RTMPS,
aktywnych platform, prawdziwego IdP i interaktywnego logowania OIDC w UI.
Nie wdrożono mTLS/HTTPS publicznego serwera, maskowania wideo, multistreamingu
ani obsługi produkcyjnej. Nie przyznano `READY_FOR_PRODUCTION`.
