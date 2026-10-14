# AdultCam Ω — Control Tower 1.0.0rc2

## OFFLINE_LAB — działanie bez kont na platformach

Wydanie 1.0.0rc2 udostępnia samodzielne lokalne centrum sterowania i katalog **przyszłych** kont. Polecenie `adultcam-omega-lab` uruchamia tryb, w którym START OBS oraz odczyt zewnętrznych API są blokowane. Zapisywanie planowanych kont nie wymaga haseł, tokenów ani zewnętrznego API. Wszystkie pozycje pozostają NIEPODŁĄCZONE.

Instrukcja: [docs/STANDALONE_1_0_RC2.md](docs/STANDALONE_1_0_RC2.md). Zakres zmian: [RELEASE_NOTES_1.0.0-rc2.md](RELEASE_NOTES_1.0.0-rc2.md).

**Ważne:** tryb bezkontowy jest gotowy do testów lokalnych, ale wydanie **1.0.0 GA nadal nie jest zatwierdzone do rzeczywistej transmisji produkcyjnej**.

## Status release candidate: NOT_PRODUCTION_READY

Wdrożono fail-closed bramkę akceptacji produkcyjnej. W trybie ADULTCAM_RELEASE_MODE=production serwer odmawia uruchomienia, dopóki niezależny audytor nie podpisze aktualnego, kompletnego pakietu dowodów, a zdalne OIDC/HTTPS nie będzie skonfigurowane. Podpis dowodzi pochodzenia dokumentów, lecz nie zastępuje faktycznej weryfikacji testów sprzętowych.

Nadal nie wykonano rzeczywistej, niezależnie potwierdzonej emisji z OBS do platformy, pełnego testu anonimizacji przed enkoderem ani testu na Samsungu S24 Ultra. Wersja 1.0.0 GA NIE jest wydana.

- Kryteria przyjęcia: [RELEASE_1_0_ACCEPTANCE.md](docs/RELEASE_1_0_ACCEPTANCE.md)
- Przegląd ryzyka: [SECURITY_AUDIT_1_0.md](docs/SECURITY_AUDIT_1_0.md)

Test techniczny bramki: `python -m adultcam.release_gate` (bez dowodów wynik BLOCKED i kod 2).

## Historia: AdultCam Ω 0.9.0

## Wydanie 0.9.0 — oficjalny odczyt stanu i RGB24 fail-closed

Dodano odczyt własnych statystyk konta Chaturbate przez oficjalne Stats API. Wymaga lokalnie przechowywanego tokenu właściciela i nie steruje transmisją; wynik jest odświeżany przez dostawcę co około pięć minut. Jest to adapter READ_ONLY, nie dowód odebrania obrazu.

Adapter Twitch Helix udostępnia wyłącznie odczyt statusu *uprawnionego kanału niepornograficznego*. Platforma zabrania nadawania treści pornograficznych, dlatego nie jest to integracja dla emisji AdultCam. `LIVE` to wyłącznie status platformy, nie dowód dostarczenia obrazu. Brak zewnętrznej transmisji ani autoryzowanego adaptera platform 18+. Procesor `adultcam.privacy_pipeline` bez zweryfikowanego detektora produkuje jedynie całkowicie czarny obraz. Szczegóły: [docs/PHASE_0_9_OFFICIAL_READ_ONLY_AND_PRIVACY.md](docs/PHASE_0_9_OFFICIAL_READ_ONLY_AND_PRIVACY.md).

## Wydanie 0.8.0 — planowanie tras i testy lokalnego rozdzielania sygnału

Dodano trwały rejestr tras sesji, kontrolę konfliktu PUBLIC/PRIVATE oraz test FFmpeg, w którym syntetyczny obraz dociera do kilku lokalnych odbiorników. Sprawdzenie podpisanego dowodu dotyczy jedynie własnych odbiorników. Zewnętrzne integracje pozostają `MANUAL_ONLY`.

Szczegóły: [dokumentacja 0.8](docs/PHASE_0_8_ROUTE_SAFETY_AND_LAB_SIMULCAST.md).

```bash
python -m adultcam.simulcast_lab --receivers 2 --duration 3
python -m pytest -q
```

## Wydanie 0.7.0 — laboratoryjny odbiór i bramka prywatności

Nowe: podpisywane potwierdzenia odbioru **własnego** RTMPS, opcjonalna blokada START przy niepoprawnej scenie OBS oraz strumieniowy filtr pełnego zaciemnienia RGB24. To nie jest niezależne potwierdzenie odbioru przez zewnętrzną platformę ani wdrożona anonimizacja twarzy. Szczegóły: [docs/PHASE_0_7_SECURITY_AND_DELIVERY.md](docs/PHASE_0_7_SECURITY_AND_DELIVERY.md). `platform_delivery = UNVERIFIED`.

## Wydanie 0.6.0 — logowanie przeglądarkowe OIDC/PKCE i test RTMPS (13.10.2026)

Wprowadzono serwerowe sesje przeglądarkowe OIDC, kod autoryzacji z PKCE S256,
JWT RS256, CSRF, role `viewer/operator/admin`, administracyjne cofanie sesji,
panel operatorski z wylogowaniem oraz konfigurację reverse-proxy HTTPS (Caddy).
Test RTMPS wykorzystuje **rzeczywiste** połączenie TLS i odczyt syntetycznych
klatek przez FFmpeg. **NIE wykonano testu prawdziwego OBS Studio, platformy
zewnętrznej ani Samsunga S24 Ultra.** Kod został przetestowany lokalnie,
ale nie dopuszczony do produkcji. Szczegóły: [RELEASE_NOTES_0.6.0.md](RELEASE_NOTES_0.6.0.md),
[docs/REMOTE_CONSOLE_0_6.md](docs/REMOTE_CONSOLE_0_6.md),
[docs/RTMPS_ACCEPTANCE_0_6.md](docs/RTMPS_ACCEPTANCE_0_6.md).

Uruchom lokalny test transportu RTMPS (FFmpeg i OpenSSL wymagane):

```sh
python -m adultcam.rtmps_probe
```

## Wydanie 0.5.0 — JWT/OIDC API, role-based access i test prawdziwego OBS (13.10.2026)

**Nowy zakres lokalny:** opcjonalne OIDC Bearer JWT (weryfikacja RS256/JWKS,
issuer/audience/exp), role `viewer`/`operator`/`admin`, jawny dostęp admin-only
do rejestru finansowego i oświadczeń oraz preflight prawdziwego OBS, który
**niczego nie uruchamia**. Domyślny tryb lokalny HTTP Basic zachowano.

* [Zdalne OIDC JWT API / role / Android SSH](docs/OIDC_API_0_5.md)
* [Bezpieczna bramka testu na prawdziwym OBS](docs/OBS_REAL_DEVICE_GATE_0_5.md)
* [Notatki wydania](RELEASE_NOTES_0.5.0.md)

```bash
python -m adultcam.obs_acceptance --check --port 19350
python -m pytest -q
```

**Nie jest to produkcyjna zdalna konsola:** frontend HTML nie ma jeszcze
logowania OIDC, a HTTPS / mTLS, rzeczywisty OBS, zewnętrzny RTMPS ingest i
konektory platform nie zostały przetestowane end-to-end. Nie wystawiaj portu
8765 poza localhost. Nie udostępniaj kluczy transmisji ani tokenów.

## Wydanie 0.4.0 — priorytet P0: kontrolowany test prywatnego RTMP i fail-closed RECOVERY (13.10.2026)

- Naprawiono automatyczne przywracanie `RECOVERY → LIVE_PUBLIC` przez ręczny odczyt OBS. Wznowienie wewnętrznego stanu wymaga jawnego zatwierdzenia operatora i odczytu stanu OBS z weryfikacją zatwierdzonego celu.
- Dodano prywatny odbiornik `ffmpeg` testujący faktyczne przyjęcie syntetycznych klatek przez lokalny transport RTMP. **To nie jest test zewnętrznej platformy, ani sam w sobie test OBS**.
- Zdalne adresy strumieni na allowliście wymagają `rtmps://`; zwykłe `rtmp://` działa wyłącznie z `localhost` / `127.0.0.1` dla testu prywatnego.
- Dodano przycisk zatwierdzania `RECOVERY`, testy bezpieczeństwa i instrukcję [docs/OBS_PRIVATE_INGEST_0_4.md](docs/OBS_PRIVATE_INGEST_0_4.md).

**Szybki test transportu (wymaga FFmpeg):**

```bash
python -m adultcam.rtmp_probe --self-test --port 0 --duration 2 --timeout 20
```

`verification=RECEIVER_VIDEO_FRAMES` potwierdza rzeczywiste odebranie klatek przez lokalny odbiornik testowy; pole `platform_delivery` pozostaje `UNVERIFIED`.

Przed użyciem z prawdziwą transmisją konieczne są testy na rzeczywistym OBS, niezależny odbiór RTMPS po stronie uprawnionego endpointu, ochrona danych/wizerunku i audyt autoryzacji.

## Wydanie 0.3.0 — monitoring bezpieczeństwa i repozytorium główne (13.10.2026)

**Zmiana operacyjna:** dostępny jest bezpieczny monitor odczytowy OBS, trwałe i deduplikowane incydenty, kontrolowana zmiana `LIVE_PUBLIC → RECOVERY`, ręczny endpoint monitoringu i opcjonalny proces z harmonogramem odpytywania. Monitor nigdy nie wysyła START/STOP i nie przywraca stanu LIVE automatycznie. `OBS_OUTPUT_ONLY` nie oznacza zweryfikowanego odbioru na platformie.

Dostęp operatorski ze smartfona: [docs/ANDROID_REMOTE.md](docs/ANDROID_REMOTE.md) (tunel SSH do loopback; nadal brak produkcyjnego OIDC/mTLS). Granica interfejsów zewnętrznych: [docs/PLATFORM_ADAPTER_CONTRACT.md](docs/PLATFORM_ADAPTER_CONTRACT.md). Bramka wydania: [docs/RELEASE_GATE_0_3.md](docs/RELEASE_GATE_0_3.md).

### Uruchomienie monitoringu (na hoście z OBS i lokalnym backendem)

```bash
# Najpierw skonfiguruj lokalnie OBS_WS_PASSWORD, OBS_WS_URL,
# ADULTCAM_DB_PATH oraz ADULTCAM_OBS_ALLOWED_SERVERS.
python -m adultcam.monitor_worker --once
# Kod 0: OK / DEFERRED; kod 2: wykryto alarm (nie jest to sukces transmisji).
python -m adultcam.monitor_worker --interval 30
```

Worker nie startuje automatycznie z serwerem HTTP — operator uruchamia go jako **jeden osobny proces**. Odpytywanie jest wyłącznie odczytem `GetStreamStatus` i, gdy potrzebne, `GetStreamServiceSettings`. Brak dostępu do OBS jest incydentem; zawartość wyjątków i dane klucza transmisji nie są ujawniane w interfejsie. Porty pozostają ograniczone do loopback. Nie traktuj wersji 0.3.0 jako gotowej do emisji produkcyjnej.


**Stan:** działający lokalny rdzeń API i interfejsu operatorskiego, NIE kompletny system produkcyjny. Żadna integracja z platformami dla dorosłych nie jest automatycznie aktywowana.

System jest przeznaczony tylko do uprawnionej działalności zweryfikowanych osób pełnoletnich za ich świadomą zgodą. Nie przechowuj dokumentów tożsamości w tej bazie.

## Wymagania

- Python 3.11+ (Linux, Windows, macOS, Termux/Android po doinstalowaniu odpowiednich zależności).
- OBS Studio z obs-websocket v5 na tym samym hoście (`127.0.0.1:4455`), **z włączonym uwierzytelnianiem** do sterowania rzeczywistym wyjściem OBS.

## Uruchomienie — Linux/macOS/Termux

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[test]'
read -rsp "Hasło operatora (co najmniej 16 znaków): " ADULTCAM_ADMIN_PASSWORD; echo
export ADULTCAM_ADMIN_PASSWORD
# Zapisz mocne hasło w lokalnym menedżerze haseł.
# Aby sterować transmisją, ustaw OBS_WS_PASSWORD oraz ADULTCAM_OBS_ALLOWED_SERVERS lokalnie.
python -m adultcam
```

Otwórz `http://127.0.0.1:8765` i zaloguj się jako `operator` z hasłem zapisanym w `ADULTCAM_ADMIN_PASSWORD`.

**Uwaga:** ustaw własne silne hasło o długości co najmniej 16 znaków i zapisz je w swoim menedżerze haseł. Nie zapisuj go w repozytorium.

Na Windows (PowerShell) ustaw `$env:ADULTCAM_ADMIN_PASSWORD = '<własne silne hasło>'`, następnie wykonaj `py -m adultcam`.

Możesz ustawić `ADULTCAM_DB_PATH` na prywatną ścieżkę pliku SQLite; domyślnie `~/.adultcam-omega/adultcam.sqlite3`.

## Funkcje faktycznie zaimplementowane

- Lokalna konsola PL responsywna na telefon i komputer; HTTP Basic na loopback.
- Tworzenie profili oraz **ręczne** oznaczanie ich jako ONLINE / OFFLINE / UNVERIFIED.
- Zapis zdarzeń przy zmianach statusu bez duplikowania niezmienionych stanów.
- Operator deklaruje 4 warunki pełnoletności, zgody, uprawnień i znajomości zasad; data oświadczenia ważna 24 h. To nie stanowi prawnej weryfikacji wieku.
- Cykl życia sesji i bramki kontrolne (READY, LIVE, ENDING, CLOSED).
- Akcje OBS tworzone jako `PENDING_APPROVAL`, wyraźnie zatwierdzane, wykonywane raz i weryfikowane odczytem statusu. Niepewność = `UNKNOWN`, bez automatycznych ponowień.
- Komunikacja OBS przez natywne API obs-websocket v5, kompatybilne z protokołem Hello/Identify/Request/Response.
- Szablony SHOWRUNNER Ω: 10-godzinny i 30-dniowy, bez udawania prawdziwych danych finansowych.
- Ręczna księga przychodów/zwrotów w najmniejszych jednostkach waluty, bez integracji z wypłatami.
- Append-only events, idempotency key, trwała baza SQLite, logika blokowania ryzykownych operacji, testy automatyczne.

## Uruchomienie testów

```sh
python -m pytest -q
```

## Status integracji

| System | Stan | Znaczenie |
|---|---|---|
| Lokalny backend/API/GUI | IMPLEMENTED_LOCAL | działa na urządzeniu lokalnym |
| OBS WebSocket v5 | MOCK_WIRE_TESTED_NOT_LIVE_VERIFIED | adapter, kontrola adresu docelowego, zatwierdzenie, status i recovery przetestowane na lokalnym symulatorze OBS v5; wymaga testów na prawdziwym OBS |
| ShowUp.tv / pozostałe platformy | MANUAL_ONLY | brak wiarygodnego i autoryzowanego adaptera do zmian konta lub odczytu statusu |
| Rozsyłanie powiadomień | NOT_IMPLEMENTED | lokalny rejestr incydentów bez dostawy na zewnętrzny kanał |
| Monitor statusu OBS | IMPLEMENTED_LOCAL_OPT_IN | odczyt lokalnego OBS, worker z interwałem, SQLite i incydenty; brak potwierdzenia platformy |
| Równoczesne nadawanie RTMP | NOT_IMPLEMENTED | wymaga obsługi scen/kanałów i sprawdzenia regulaminów |
| WebRTC/Maskowanie twarzy | NOT_IMPLEMENTED | wymaga osobnego lokalnego pipeline z testami awaryjnymi |
| Płatności i dane o fanach | NOT_CONNECTED | brak autoryzowanego zewnętrznego źródła |
| Android APK | NOT_BUILT | dostęp przez przeglądarkę lokalną, ewentualnie Termux |
| Użycie produkcyjne/publiczny internet | NOT_APPROVED | brak OIDC/TLS, pełnego RBAC, audytu bezpieczeństwa i testów urządzeniowych |

## Bezpieczeństwo i granice

- Serwer wiąże się WYŁĄCZNIE z `127.0.0.1`. Nie wystawiaj portu 8765 publicznie.
- Nie przechowuj sekretów w kodzie ani JSON konfiguracji. Hasła dostarczaj przez lokalny manager sekretów/zmienne środowiskowe.
- Zewnętrzne akcje wymagają decyzji operatora; brak zatwierdzenia = brak transmisji.
- Po utracie odpowiedzi z OBS zwracany jest `UNKNOWN`. Nowy START jest blokowany do czasu jawnego uzgodnienia `/api/obs/reconcile`; awaryjny STOP pozostaje możliwy dla właściwej sesji.
- HTTP Basic bez TLS służy wyłącznie do lokalnego połączenia (loopback). Dla pracy wielourządzeniowej konieczny jest bezpieczny, uwierzytelniony serwer HTTPS.
- Wszelkie materiały i informacje widoczne w GUI są danymi operatora; brak automatycznego dostępu do kont cudzych ani obchodzenia ograniczeń usług.

## Plan dojścia do wersji w pełni funkcjonalnej

1. **P0 Integracje i bezpieczeństwo:** obsługa sesji operatorskich OIDC + TLS, oddzielny worker i kolejka ze stanami recovery, uprawnienia RBAC, odświeżalne dowody/zgody. Testy OBS na rzeczywistym urządzeniu.
2. **P1 Platform adapters:** wykrywanie możliwości z oficjalnych API i autoryzowanych przeglądarek, adaptery najpierw do odczytu, następnie zapisy po przeglądzie regulaminu; weryfikowalne dowody i operacyjne receipts.
3. **P2 StreamOps:** orkiestracja OBS + RTMP, kontrola stanów per platforma, blokady prywatnych sesji i bezpieczne przełączanie scen, status oraz recovery po awarii połączenia.
4. **P3 Privacy & monitoring:** lokalny bezpieczny pipeline maskowania twarzy fail-closed, opt-in alerty publicznych profili, ograniczenie duplikatów, audyt kanałów powiadomień.
5. **P4 Commerce analytics:** import prawnie dostępnych metryk transakcji, walidacja danych, modele KPI, programowanie sesji, CRM wyłącznie za zgodą odbiorców.
6. **P5 Mobile release:** PWA/TWA lub natywny Android, prawidłowy model przechowywania kluczy, testy E2E na Samsung Galaxy S24 Ultra, audyt zewnętrzny, staging i kontrolowany release.

Żaden element planu nie jest oznaczany jako wykonany bez kompilacji/testów, potwierdzeń integracji i odpowiednich receipt.

Dokumenty techniczne: [`ARCHITECTURE.md`](ARCHITECTURE.md), [`ROADMAP.md`](ROADMAP.md).

### Android / Termux

Na Samsungu Galaxy S24 Ultra system można uruchomić jako lokalną usługę Python przez Termux, a panel otworzyć w przeglądarce na `http://127.0.0.1:8765` (po lokalnej instalacji zależności i ustawieniu hasła). Test uruchomienia na realnym S24 Ultra **nie został jeszcze wykonany**. Funkcja sterowania OBS wymaga OBS WebSocket na tym samym hoście co backend lub zaprojektowanego osobnego bezpiecznego kanału (obecny adapter nie łączy się z obcą maszyną).


## Wersja 0.2.0 — bezpieczniejsze zarządzanie OBS (P0: częściowo ukończone)

Zaimplementowano w kodzie:

- **Allowlistę serwerów nadawczych:** START odczytuje `GetStreamServiceSettings` i wymaga typu `rtmp_custom`, niepustego klucza transmisyjnego w OBS oraz dokładnie zatwierdzonego serwera. Brak listy = brak START. Serwer nie odczytuje ani nie zapisuje klucza transmisyjnego w dzienniku/odpowiedziach HTTP.
- **Obowiązkowe uwierzytelnianie OBS dla START:** operator musi ustawić lokalne `OBS_WS_PASSWORD`; serwer OBS musi faktycznie oferować handshake z uwierzytelnianiem.
- **Preflight:** przed START sprawdzany jest status wyjścia OBS; aktywnego wyjścia nie uruchamia się ponownie. W przypadku nieudanej kontroli wstępnej zwracany jest `FAILED` bez wysyłania polecenia START. Błąd po rozpoczęciu polecenia = `UNKNOWN`, bez automatycznej ponownej próby.
- **Trwały globalny single-flight:** transakcje SQLite `BEGIN IMMEDIATE` blokują równoległe zatwierdzenia. START po nierozstrzygniętej operacji `UNKNOWN` jest blokowany.
- **Uzgodnienie `UNKNOWN`:** operator może zatwierdzić odczyt stanu OBS poprzez `POST /api/obs/reconcile` z identyfikatorem operacji; historia pierwotnej niepewności pozostaje w bazie. Stan ACTIVE jest uznawany tylko dla zatwierdzonego celu i stabilnego wyjścia OBS.
- **Kontrola dryfu:** `POST /api/obs/check` porównuje ręcznie zainicjowany odczyt OBS z sesją. W razie rozbieżności przechodzi do `RECOVERY` i zapisuje zdarzenie audytowe. Powrót z `RECOVERY` odbywa się po potwierdzonym odczycie i kontroli serwera.
- **Zarządzanie zamiarami:** `POST /api/actions/{id}/cancel` pozwala anulować niewykonany zamiar bez wysyłania polecenia OBS.
- **Ochrona lokalnego HTTP:** zaufane hosty `localhost` / `127.0.0.1` (ograniczenie DNS rebinding); pozostaje Basic i anty-CSRF na loopback. Trwała baza SQLite ma tryb `0600` na systemach POSIX.
- **Dane wrażliwe:** `/api/obs/status` pokazuje wyłącznie zatwierdzone pola telemetryczne; status OBS jest odróżniany od faktycznego odbioru na platformie.

### Obowiązkowa konfiguracja rzeczywistego sterowania OBS

Skonfiguruj w OBS Studio **Tools → WebSocket Server Settings**: włącz serwer i uwierzytelnianie, zapisz hasło w menedżerze sekretów. W sekcji Streaming skonfiguruj własny serwer `Custom` RTMP/RTMPS, zgodnie z zasadami platformy. W przykładzie używamy niedziałającego adresu testowego — zastąp go **lokalnie** dokładnym adresem serwera ze zweryfikowanej konfiguracji OBS.

```bash
read -rsp "Lokalne hasło WebSocket OBS: " OBS_WS_PASSWORD; echo
export OBS_WS_PASSWORD
export OBS_WS_URL="ws://127.0.0.1:4455"
read -rp "Dokładny URL serwera RTMP(S) OBS: " ADULTCAM_OBS_ALLOWED_SERVERS
export ADULTCAM_OBS_ALLOWED_SERVERS
python -m adultcam
```

`ADULTCAM_OBS_ALLOWED_SERVERS` przyjmuje listę dokładnych URL rozdzielonych przecinkami. Preferuj `rtmps://`. Nie wprowadzaj hasła transmisji, stream key ani danych dostępu do kont do tej listy. **Nie udostępniaj serwera HTTP ani obs-websocket publicznie.** Zabezpiecz odrębnymi hasłami dostęp do obu usług.

Po uruchomieniu panelu utwórz sesję, zapisz oświadczenie, przełącz sesję w READY, przygotuj START, a następnie osobno potwierdź. Przy `UNKNOWN` skontroluj sytuację w OBS, ewentualnie przygotuj awaryjny STOP dla właściwej sesji i użyj przycisku uzgodnienia. W odpowiedziach `OBS_OUTPUT_ONLY` oznacza wyłącznie lokalny stan OBS, a `platform_delivery: UNVERIFIED` brak potwierdzenia platformy.

### Kontrola poza panelem — przykład bez zapisywania hasła w historii terminala

```bash
curl --user operator \
  -H "X-AdultCam-Request: 1" \
  -X POST http://127.0.0.1:8765/api/obs/check
```

`curl` poprosi o hasło operatora. Odczyt z `/api/obs/check` nie jest autonomicznym monitorowaniem ani powiadomieniem.

### Testy

```bash
python -m pytest -q
python -m compileall -q adultcam
```

Zestaw zawiera test prawdziwej komunikacji WebSocket z **lokalnym, sztucznym serwerem zgodnym z OBS v5**; to nie jest test prawdziwego OBS Studio ani połączenia z platformą. Dodatkowe testy obejmują brak wycieku stream key, ochronę Host, blokowanie niezatwierdzonych serwerów, idempotencję, restart, pojedyncze wykonywanie, uzgodnienie `UNKNOWN` i zmianę stanu `RECOVERY`.

### Ograniczenia blokujące wydanie produkcyjne

- Brak potwierdzonego nadawania/odbioru na rzeczywistej platformie i testu rzeczywistej instalacji OBS.
- Brak osobnych, zatwierdzonych adapterów platform, bezpiecznego multistreamingu i synchronizacji prywatnych pokoi.
- Brak działającej anonimizacji twarzy z trybem fail-closed i weryfikacji geoblokad.
- Brak niezależnej weryfikacji wieku/zgód; oświadczenie operatora nie jest takim dowodem.
- Brak zdalnego OIDC/mTLS, RBAC, ochrony przed wieloma operatorami, szyfrowanych kopii zapasowych i automatycznego monitoringu.
- Brak testu na Samsung Galaxy S24 Ultra. Obsługa OBS na innym komputerze wymaga osobnej, bezpiecznej architektury sieciowej — aktualny backend komunikuje się wyłącznie z lokalnym OBS.

**Uwaga:** funkcjonalny endpoint START/STOP nie oznacza gotowości do produkcyjnych transmisji. Przed każdą rzeczywistą transmisją operator musi niezależnie zweryfikować uczestników, zgody, miejsce publikacji, regulamin oraz ochronę prywatności.
