# AdultCam Ω — architektura i kontrakt wykonawczy (v0.1.0)

## Granice wykonania

Warstwy logiczne:

```text
Operator (przeglądarka na localhost)
       │ HTTP Basic + custom CSRF header + same-Origin
       ▼
FastAPI — input contract + operator actions
       ├── Domain policy (age/consent self-attestation, state guards)
       ├── SQLite (sessions, action intents, events, ledger, profile status)
       ├── SHOWRUNNER (10 h, 30 dni: szablon)
       └── OBS WebSocket v5 (only local, explicit approval)
                 │
                 ▼
           OBS Studio, host local
```

## Operacje zewnętrzne

1. API tworzy `ActionIntent` z idempotency_key i `risk_class=R4`.
2. `action_policy` weryfikuje stan sesji i aktualne oświadczenie operatora dla START.
3. Użytkownik osobno zatwierdza akcję poprzez dedykowany interfejs (typed confirmation).
4. Backend zapisuje `EXECUTING` i wysyła *jedno* żądanie `StartStream` albo `StopStream` do OBS WebSocket v5.
5. Drugie, odczytowe żądanie `GetStreamStatus` weryfikuje obserwowalny skutek.
6. Dopiero po zgodnym odczycie oznacza `SUCCEEDED` i aktualizuje stan lokalny.
7. Błąd po wysłaniu operacji = `UNKNOWN`, bez bezwarunkowego retry. Należy sprawdzić stan OBS.

## Kategorie operacji

- `R0`: odczyt publicznej dokumentacji — dopuszczalny z wiarygodnego źródła.
- `R1`: odczyt danych uwierzytelnionych — wymaga autoryzowanej integracji.
- `R2`: odwracalna zmiana wewnętrznego stanu planu — dostępna operatorowi.
- `R3`: komunikacja z odbiorcami — niezaimplementowana (brak opt-in i adaptera).
- `R4`: kontrola transmisji — wymagane jawne zatwierdzenie i pozytywny wynik adaptera.
- `R5`: operacje finansowe / bezpieczeństwo kont — tylko manualnie; ręczny zapis księgowy to nie wykonanie płatności.
- `R6`: niedozwolone operacje — blokowane.

## Model danych

- `profiles`: widoczna publiczna nazwa, platforma, wpisany URL, *ręcznie* zadeklarowany status.
- `sessions`: wewnętrzny stan programu, który nie jest dowodem rzeczywistego nadawania poza potwierdzonym OBS.
- `attestations`: audytowana deklaracja operatora, z ważnością 24 godzin.
- `action_intents`: identyfikator logiczny, operacja, idempotencja, status i receipt.
- `events`: API nie udostępnia edycji/usuwania; zapis przy zmianie stanu.
- `ledger`: kwoty w najmniejszych jednostkach waluty, bez przeliczania kursów i prowizji.

## Model zagrożeń i ograniczenia

- **Eksfiltracja hasła**: hasła nie zapisuje się w repo ani lokalnej bazie. Basic Auth jest dozwolone wyłącznie na loopback. Dla dostępu sieciowego wymagane HTTPS/OIDC, RBAC, rate limiting i odrębny model sesji.
- **Nieautoryzowana transmisja**: osobne zatwierdzanie, blokada globalna drugiego startu, wymagane oświadczenie dla startu, aktualizacja stanu dopiero po OBS. Autentyczność zgód musi zostać niezależnie potwierdzona operacyjnie.
- **Błąd transmisji**: w razie nieznanego wyniku backend nie deklaruje sukcesu ani nie wysyła automatycznie kolejnego Start. Emergency Stop można przygotować także przy `READY`.
- **Podszywanie się / dane cudze**: system nie służy do podszywania się pod osoby, naruszania dostępu, archiwizowania prywatnych występów bez zgody.
- **Błędne metryki**: wpisy w księdze oznaczone jako ręczne, bez deklaracji opłacenia; prognozy są szablonami bez fikcyjnych wyników.
- **Utrata danych**: SQLite na urządzeniu wymaga kopii zapasowej; backup/restore/retention production-grade niezaimplementowane.
- **Równoczesność**: pojedynczy węzeł/worker. Wersja wielowęzłowa wymaga durable execution i dystrybuowanych blokad; SQLite nie zastępuje tego kontraktu.

## Zasady dla przyszłych adapterów platformowych

Każdy adapter musi deklarować: źródło, stan zdolności (`CONNECTED_API`, `BROWSER_AUTHORIZED`, `PUBLIC_WEB_ONLY`, `MANUAL_ONLY`, `NEEDS_VERIFICATION`, `BLOCKED`), ważność dowodów, zestaw operacji, model autoryzacji, politykę retry i strukturę wyniku. Nie można podnieść stanu z `MANUAL_ONLY` bez weryfikacji uprawnień, regulaminu i testu end-to-end.


## Rozszerzenie wersji 0.2.0 — granice prawdy o transmisji

`stream_control.StreamPolicy` kontroluje dokładny docelowy adres RTMP(S) wybrany w OBS i nie ujawnia stream key. `stream_control.run_obs_action` odróżnia błąd preflight bez wysłanej operacji (`FAILED`) od nieznanego wyniku po wysłaniu komendy (`UNKNOWN`).

`app.approve` rezerwuje pojedynczy slot za pomocą transakcji SQLite, po czym wykonuje jedno wywołanie mutujące OBS. `obs_reconciliations` zapisuje wtórny fakt o obecnym statusie lokalnego wyjścia OBS, nie nadpisując pierwotnego `UNKNOWN`. Rozliczanie operacji nigdy nie jest dowodem faktycznego odbioru sygnału w serwisie zewnętrznym.

`POST /api/obs/check` realizuje ręczny detector dryfu: `LIVE_PUBLIC -> RECOVERY`, gdy lokalny OBS nie nadaje, ponawia łączenie albo adres wysyłania przestaje odpowiadać polityce. Odzyskanie wymaga kolejnej weryfikacji lokalnego wyjścia i zatwierdzonego adresu. Monitor automatyczny i sprawdzenie platformowe pozostają niezrealizowane.

**Model zagrożeń:** nieznany odbiorca transmisji (deny by default), HTTP DNS rebinding (TrustedHost), CSRF, równoległe wywołania, awarie odpowiedzi i restart procesu, ujawnienie stream key w JSON i bazie, stan `LIVE_PUBLIC` bez dowodu OBS, niedozwolone zmiany scen/multistreamingu. Dodatkowo produkcyjny system będzie wymagać sprzętowych testów bezpieczeństwa, ochrony twarzy, analizy praw i regulaminów, połączenia zdalnego z OIDC/TLS, separacji ról i kopii zapasowych.

## 0.3.0 — safety monitor

`monitor_worker` → `monitor_once` → `GetStreamStatus` [+ `GetStreamServiceSettings` przy outputActive] → `SQLite incidents/monitor_state` → `GET /api/monitor/status` → panel. Monitor nie wysyła poleceń zapisu do OBS. Snapshoty sesji i `EXECUTING` są sprawdzane przed i po odczycie zewnętrznym; rozbieżności = `DEFERRED`. Alarm przenosi `LIVE_PUBLIC` do `RECOVERY`, powrót tylko przez ręczny audyt OBS. Brak możliwości potwierdzania odbioru na platformie.

Tunel operatorski SSH zachowuje ograniczenia loopback serwera HTTP i OBS; nie stanowi pełnego produkcyjnego modelu OIDC/mTLS.
