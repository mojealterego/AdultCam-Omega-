# AdultCam Ω 1.0.0rc2 — offline-first release candidate

Dodano bezkontowy rejestr planowanych połączeń, trwałe stany NOT_CONNECTED / AWAITING_AUTHORIZATION / DISABLED, kontrolę uprawnień, audyt i panel przygotowania przyszłych integracji. Dodano osobny punkt uruchomienia adultcam-omega-lab: blokuje START OBS oraz odczyty zewnętrznych adapterów, nawet jeżeli wcześniejsze ustawienia środowiska zawierają dostęp do API.

Pakiet obsługuje lokalną konsolę, symulatory i testy własnego odbiornika. Brak aktywnego połączenia do zewnętrznych platform. Ukończono zakres lokalnego onboarding scaffold, a nie produkcyjną integrację.

Wydanie 1.0.0 GA nadal niezatwierdzone: brak testów prawdziwego OBS, zewnętrznego odbioru, produkcyjnego maskowania i testu Android. Szczegóły w docs/STANDALONE_1_0_RC2.md.
