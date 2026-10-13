# AdultCam Ω 0.3.0 — bramka wdrożeniowa

| Wymaganie | Stan i dowód |
|---|---|
| Lokalny backend z autoryzacją | Załączony kod i testy API |
| OBS WebSocket v5 | Test z symulatorem WebSocket; real OBS **NIEZWERYFIKOWANY** |
| Idempotencja oraz ręczne zatwierdzenie START | Testy automatyczne |
| Monitor lokalnego OBS | Funkcje `monitor_once`, `/api/monitor/check`, `/api/monitor/status`, osobny worker |
| Deduplikacja incydentów | SQLite + testy pierwszego/ponownego alarmu |
| Fail-closed dla stanu sesji | `LIVE_PUBLIC` → `RECOVERY`; powrót wymaga oddzielnego audytu operatora |
| Bezpieczny panel mobilny | Instrukcja dostępu tunelem SSH; test S24 Ultra **NIEWYKONANY** |
| Zewnętrzne platformy | `MANUAL_ONLY`, brak podłączonych API |
| Zewnętrzny odbiór RTMPS | **NIEZWERYFIKOWANY** |
| Anonimizacja obrazu | **NIEZAIMPLEMENTOWANA** |
| Test bezpieczeństwa produkcyjnego | **NIEWYKONANY** |

## Test kontrolowany na rzeczywistym OBS (do wykonania)

1. W odizolowanym środowisku skonfiguruj OBS WebSocket v5 z hasłem i zatwierdzony, prywatny ingest RTMPS (bez transmisji publicznej).
2. Przed START sprawdź poprawność celu oraz dostępności testowego odbiornika.
3. Zatwierdź START, niezależnie sprawdź OBS i potwierdzenie odbioru na prywatnym ingest.
4. Zasymuluj przerwanie transportu po wysłaniu START, sprawdź `UNKNOWN` i blokadę ponownego START.
5. Uruchom oddzielny monitor, odłącz OBS; musi powstać pojedynczy incydent, a stan sesji musi przejść do `RECOVERY`.
6. Sprawdź, że monitor nie wywołuje START/STOP i nie przywraca LIVE samoczynnie.
7. Po ręcznej inspekcji i potwierdzeniu celu wykonaj manualny audyt OBS.
8. Sprawdź działanie przy zerwaniu tunelu SSH z telefonem i wygaśnięciu ekranu.
9. Zweryfikuj wszystkie zgody, regulaminy i poufność artefaktów. Nie rozpoczynaj transmisji publicznej przed uzyskaniem wymaganych dowodów.
