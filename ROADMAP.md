# Roadmap AdultCam Ω — od lokalnego MVP do systemu operacyjnego

## Stan bazowy: 2026-10-13

`v0.1.0 / LOCAL_MVP` — backend FastAPI, SQLite, responsywny panel PL, statusy ręczne, walidacja operatora, sesje, kolejka akcji OBS, protokół OBS WS v5, lokalna księga, plan 10 h / 30 dni, logi zdarzeń i testy. Nie jest to potwierdzenie działania żadnej platformy dla dorosłych.

### P0 — zamknięcie bezpieczeństwa i obsługi OBS

**Do wykonania:** rzeczywisty test OBS 5.x (zawiera Start/Stop/Status), wyspecyfikowane zachowanie dla restartów, `UNKNOWN` i utraty sieci, test awaryjnego zatrzymania, analiza współbieżności, schema migrations, rozsądna retencja logów, opcjonalny login lokalny z blokowaniem prób. Rozdzielenie `operator_self_attestation` od dowodu faktycznej weryfikacji wykonawców.

**Definition of Done:** testy E2E na rzeczywistym OBS; brak nieautoryzowanego Start; brak podwójnej emisji przy ponownym zatwierdzeniu; status `SUCCEEDED` wyłącznie przy faktycznie potwierdzonym stanie transmisji.

### P1 — wykonawcza architektura platform

**Do wykonania:** katalog kanonicznych sieci, deduplikacja white-label, badania regulaminów i geoblokad, capability registry, autorzyzowane konektory platform public-read/API/browser, monitor statusu z kontrolą częstotliwości i dowodami, brak nieudokumentowanych wywołań.

**Definition of Done:** co najmniej dwa sprawdzone adaptery publicznych odczytów z kompletnymi testami ograniczeń; osobno zweryfikowany adapter do zmian konta, jeśli platforma umożliwia i użytkownik autoryzuje.

### P2 — multistream i prywatne sesje

**Do wykonania:** macierz kanałów RTMP/OBS, unikalne klucze wyłącznie w vault, routing scen, wykluczenia z transmisji prywatnej, atomiczne przejścia, zapasowa sieć/enkoder, detektor opóźnienia, safe-stop, reconciliation po restarcie.

**Definition of Done:** kontrolowany test z przynajmniej dwoma platformami dopuszczającymi multi-stream; prywatne przejście wyklucza niedozwolony kanał publiczny, ze zdarzeniem receipt.

### P3 — prywatność i moderacja

**Do wykonania:** maskowanie twarzy lokalnie z przejściem awaryjnym do pełnego zakrycia, neutralizacja tła i danych EXIF, znaki wodne i audit, legalne ograniczenia regionalne, reguły krajowe i uprawnienia w zespołach.

**Definition of Done:** real-device test dwóch twarzy, okluzji, utraty śledzenia, zmiany kamery, słabego światła, awarii procesu. Fail-closed sprawdzony na strumieniu wideo. Geoblokada nie prezentowana jako gwarancja anonimowości.

### P4 — OBSERVABILITY / CRM / FINANCE

**Do wykonania:** uprawnione importy transakcji, jednostki tokenów i kursy z datą dowodów, KPI per platforma, przychód/h, retencja, opt-in CRM, powiadomienia i blokady powtórzeń, testy eksperymentów, anonimowe raporty.

**Definition of Done:** metryki rekoncyliowane z autoryzowanymi raportami; wypłaty bez zgody/receipt nieoznaczane jako wykonane; nie ma niezamówionych wiadomości do odbiorców.

### P5 — OMEGA Control Plane / MCP

**Do wykonania:** OIDC/RBAC, token-scoped MCP z `read-only` default, narzędzia agentowe z jawnie ograniczonym zakresem, approval-gate według klas R0–R6, kolejka z leasingiem/idempotencją, durable receipts, mTLS w komunikacji, metryki zdrowia.

**Definition of Done:** testy polityk przeciw prompt injection i spoofingowi narzędzi; agent nie inicjuje transmisji ani wiadomości bez weryfikowalnej zgody operatora; każdy wykonany krok ma receipt.

### P6 — Android / mobile / release

**Do wykonania:** secure mobile operator UI/PWA lub natywna aplikacja, połączenie HTTPS/OIDC do kontrolera, biometria i bezpieczny sekret store, odporność na rozłączenia, QA na Samsung S24 Ultra, CI, SBOM, zależności, podpisywane wydania i rollback.

**Definition of Done:** testy na telefonie, skan bezpieczeństwa, zewnętrzny audyt, wdrożenie staging i dopiero potem produkcja.

## Bramy globalne

`OBJECTIVE → EVIDENCE → PLAN → ACTION_INTENT → POLICY_GATE → ADAPTER → RECEIPT → AUDIT → METRICS`

Nie łącz zewnętrznych platform i nie aktywuj płatnych automatyzacji bez zgody, wiarygodnych warunków regulaminowych i minimalizacji danych osobowych. Każdy milestone można zaakceptować tylko na podstawie testów i obserwacji działania, nie deklaracji agenta.


## Postęp P0 w wersji 0.2.0 (13.10.2026)

- **Zrobiono i sprawdzono lokalnymi testami:** atomowe zatwierdzanie/odmowa równoległej operacji, exact-match RTMP(S), weryfikacja OBS auth, preflight, brak automatycznego retry, `FAILED` vs `UNKNOWN`, trwałe `UNKNOWN` i uzgodnienie, awaryjny STOP, mechanizm anulowania operacji, ręczna kontrola dryfu, ochrona Host i sanitizacja JSON.
- **Test przewodowy:** in-process OBS v5 mock z prawdziwym lokalnym socketem WS (challenge/response), pełne Start/Status/Stop.
- **Nie zrobiono:** testów przeciw prawdziwemu OBS/RTMP, autoryzowanego API platformy, automatycznych health probes, testów awaryjnego zabezpieczenia wideo, mobilnego zdalnego OIDC/TLS, niezależnej weryfikacji wszystkich uczestników, polityk prywatnych pokoi.
- **Status P0:** PARTIAL — nie nazywać P0 zamkniętym przed real-device E2E, testami bezpieczeństwa i testem transmisji za zgodą na kontrolowanym kanale testowym.

### Następny wycinek implementacyjny 0.3.0

1. Kontrolowany test na instalacji OBS Studio v5 z lokalnym prywatnym serwerem RTMPS lub testowym ingestem — dołączenie potwierdzenia startu oraz odbioru w środowisku testowym, bez publicznej transmisji.
2. Zewnętrzny odczyt telemetrii z oficjalnego, zatwierdzonego API konkretnej platformy, z ograniczeniami ilości zapytań i podpisaną zgodą właściciela.
3. Wdrożenie automatycznego monitora awarii/heartbeat z limitem obciążenia, deduplikacją incydentów i bezpiecznym odzyskiwaniem.
4. Bezpieczny dostęp Android → lokalny komputer z OBS: OIDC + HTTPS/mTLS, odrębne role operatorów i unieważnialne poświadczenia.
5. Ochrona obrazu w stylu fail-closed z testem utraty śledzenia twarzy; wymusić działanie ochrony *przed* zezwoleniem na START.

## Postęp 0.3.0 — monitoring OBS i bezpieczny zdalny dostęp operatorski

- **Zrealizowano lokalnie:** ograniczony odczytowy monitor OBS, durable incydenty, idempotentne alarmy, `RECOVERY` przy wykrytej awarii, możliwość uruchomienia jednego workera z interwałem, API incydentów, wizualizacja w panelu, negatywny rejestr zewnętrznych integracji (`MANUAL_ONLY`), dokumentacja tunelu SSH Android → lokalny backend.
- **Testy:** `tests/test_monitor.py` oraz dotychczasowe regresje.
- **Nie zrealizowano:** real-device OBS/RTMPS E2E, niezależne potwierdzenie odbioru, konektory platform, OIDC/RBAC, powiadomienia zewnętrzne, mechanizm maskowania fail-closed, zabezpieczone środowisko produkcyjne.
- **Następna bramka 0.4.0:** przeprowadzić testy na prawdziwym OBS i prywatnym odbiorniku, wdrożyć kontrolowaną warstwę mobilnego OIDC/TLS, rozdzielić role, dodać autoryzowany adapter odczytowy jednej platformy dopiero po weryfikacji aktualnego API i regulaminów.

## Postęp 0.4.0 — kontrolowany odbiór i świadome RECOVERY (13.10.2026)

**Zaimplementowano i przetestowano lokalnie:**
- Regresję bezpieczeństwa `RECOVERY → LIVE_PUBLIC`: odczyt OBS nie uruchamia już automatycznego wznowienia.
- Potwierdzane przez człowieka przywrócenie sesji z weryfikacją stanu, celu, wcześniejszego START i audytem.
- Ograniczenie nieszyfrowanego RTMP do loopback; zdalny stream target tylko RTMPS.
- Rzeczywisty test przyjęcia syntetycznych klatek przez lokalny odbiornik FFmpeg oraz tryb testowy operatora OBS.
- Instrukcję dowodową prywatnego OBS RTMP oraz aktualizację UI i CI.

**Nie zrealizowano / niezweryfikowano:** rzeczywistej instalacji OBS,
uprawnionego odbiorcy na platformie, RTMPS E2E, zewnętrznego API,
OIDC/TLS/RBAC, fail-closed ochrony obrazu, testu Samsung S24 Ultra.
Wersja 0.4.0 nie zamyka globalnego P0 i nie jest produkcyjna.

**Następny priorytet 0.5.0:** weryfikowalny test prawdziwej instalacji OBS i odbiorcy RTMPS;
bezpieczna zdalna uwierzytelniona konsola wielooperatorska (OIDC/RBAC),
a następnie autoryzowany adapter odczytowy konkretnej platformy
po potwierdzeniu jej aktualnych zasad i uprawnień.
