# Granica zewnętrznych adapterów platform — AdultCam Ω 0.3.0

## Stan wykonawczy

Wersja 0.3.0 **nie łączy się z żadną platformą dla dorosłych** i nie emuluje obecności połączenia. `GET /api/platforms/capabilities` zwraca `verified_integrations=0`, pusty katalog providerów oraz `default_capability=MANUAL_ONLY`.

## Kontrakt przyszłego adaptera

Przed dodaniem adaptera trzeba udokumentować dla konkretnej platformy i operacji:

1. Oficjalną ścieżkę API albo dozwolony sposób autoryzowanego użycia przeglądarki, wraz z aktualnym regulaminem oraz datą odczytu dowodu.
2. Właściciela/autoryzację konta, zakres uprawnień, limit częstotliwości, uprawnienie do transmisji oraz zgodę wszystkich uczestników.
3. Rekord capability: `provider`, `operation`, `capability_state`, `auth_type`, `risk_class`, `terms_evidence`, `verified_at`, `ttl_seconds`, `rate_limit`, `credential_reference` (nigdy jawny sekret).
4. `ActionIntent` z identyfikatorem korelacji, zakresem i zatwierdzeniem operatora dla wszystkich operacji zewnętrznych z zapisem, transmisją i komunikacją z odbiorcami.
5. `ActionReceipt` z `SUCCEEDED`, `FAILED`, `PARTIAL` lub `UNKNOWN`. `SUCCEEDED` tylko na podstawie zaobserwowanego i zweryfikowanego wyniku konkretnego zewnętrznego działania.
6. Oddzielne potwierdzenie odbioru po stronie platformy — **status wyjścia OBS nie jest takim potwierdzeniem**.
7. Testy awarii, limitów, zablokowanych funkcji, wielokrotnych żądań oraz rezygnacji z uprawnień.

## Zakazane skróty

- Nie uruchamiaj automatyzacji kont przez nieudokumentowane prywatne API, obchodzenie CAPTCHA, DRM lub blokad dostępu.
- Nie zapisuj sekretów RTMP ani sesji w SQLite, logach albo repozytorium.
- Nie nadawaj ani nie wysyłaj wiadomości bez weryfikowalnej autoryzacji i niezbędnych zatwierdzeń.
- Nie deklaruj potwierdzonego odbioru na platformie na podstawie `GetStreamStatus` lub danych wpisanych ręcznie.
