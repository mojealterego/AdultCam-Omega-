# AdultCam Ω — Control Tower 1.0.0rc1

## Status release candidate: NOT_PRODUCTION_READY

Wdrożono fail-closed bramkę akceptacji produkcyjnej. W trybie ADULTCAM_RELEASE_MODE=production serwer odmawia uruchomienia, dopóki niezależny audytor nie podpisze aktualnego, kompletnego pakietu dowodów, a zdalne OIDC/HTTPS nie będzie skonfigurowane. Podpis dowodzi pochodzenia dokumentów, lecz nie zastępuje faktycznej weryfikacji testów sprzętowych.

Nadal nie wykonano rzeczywistej, niezależnie potwierdzonej emisji z OBS do platformy, pełnego testu anonimizacji przed enkoderem ani testu na Samsungu S24 Ultra. Wersja 1.0.0 GA NIE jest wydana.

- Kryteria przyjęcia: [RELEASE_1_0_ACCEPTANCE.md](docs/RELEASE_1_0_ACCEPTANCE.md)
- Przegląd ryzyka: [SECURITY_AUDIT_1_0.md](docs/SECURITY_AUDIT_1_0.md)

Test techniczny bramki: `python -m adultcam.release_gate` (bez dowodów wynik BLOCKED i kod 2).


