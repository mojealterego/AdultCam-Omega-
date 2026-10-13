# AdultCam Ω 0.4.0 — prywatny test odbioru RTMP i bezpieczne RECOVERY

## Granice testu

Test nie łączy się z platformami dla dorosłych, nie publikuje do internetu,
nie wykonuje nagrania na dysk i nie pobiera kluczy transmisji z kont.
Odbiornik FFmpeg nasłuchuje wyłącznie na `127.0.0.1`. Odbiór klatek
potwierdza transport do **tego lokalnego odbiornika**, nie do platformy.

Wszystkie osoby widoczne na ewentualnej transmisji muszą być zweryfikowanymi,
świadomie wyrażającymi zgodę osobami pełnoletnimi. Zalecany test to wyłącznie
plansza kolorów / syntetyczny obraz OBS, bez udziału prawdziwych osób.

## 1. Samodzielny test rzeczywistego protokołu (bez OBS)

Wymagany FFmpeg dostępny w `PATH`. Wykonaj:

```bash
python -m adultcam.rtmp_probe --self-test --port 0 --duration 2 --timeout 20
```

Polecenie uruchamia rzeczywisty lokalny odbiornik RTMP, wysyła do niego
syntetyczne klatki i sprawdza ilość odebranych klatek w procesie odbiorczym.
Oczekiwane: `verification=RECEIVER_VIDEO_FRAMES`, `video_frames>=3`,
`platform_delivery=UNVERIFIED`, `obs_tested=false`; kod zakończenia `0`.
Kod `2` oznacza brak wiarygodnego potwierdzenia transmisji.

## 2. Test z prawdziwym OBS Studio (wymaga komputera i operatora)

Na **tym samym komputerze**, na którym działa OBS:

1. Dodaj do OBS scenę z wyłącznie syntetycznym źródłem testowym.
2. W OBS Streaming / Custom ustaw serwer `rtmp://127.0.0.1:19350/live`
   i testowy klucz `omega-test`. To nie jest zewnętrzny serwer.
3. W osobnym terminalu uruchom odbiornik:

   ```bash
   python -m adultcam.rtmp_probe --listen-obs --confirm-test-only --port 19350 --duration 5 --timeout 45
   ```

4. Ręcznie uruchom testową transmisję w OBS, a następnie ją zatrzymaj.
5. Sprawdź wynik JSON. Oczekiwane: `verification=RECEIVER_VIDEO_FRAMES`
   i `video_frames>=3`. Wynik pozostaje `platform_delivery=UNVERIFIED`.
6. Aby testować przez Control Tower, na komputerze z OBS ustaw lokalną
   listę dozwolonych serwerów na `rtmp://127.0.0.1:19350/live`, włącz
   uwierzytelniony OBS WebSocket i wykonaj pełne
   `READY → zatwierdzony START → test odbioru → zatwierdzony STOP`.

**Uwaga:** opcja `--listen-obs` nie wykrywa tożsamości nadawcy. Klatki mogą
pochodzić od dowolnego lokalnego klienta RTMP. Testy OBS są uznane za
przeprowadzone dopiero po ręcznym potwierdzeniu konfiguracji i zapisaniu
rzeczywistego materiału dowodowego operatora. W tym środowisku testu z
prawdziwym OBS jeszcze nie wykonano.

## 3. Recovery — już bez automatycznego przywracania LIVE

`POST /api/obs/check` może przenieść `LIVE_PUBLIC → RECOVERY`, ale nie
przywraca stanu `LIVE_PUBLIC` automatycznie po wykryciu aktywnego wyjścia.

Operator w lokalnym panelu używa osobnego przycisku
**ZATWIERDŹ WYJŚCIE Z RECOVERY**. W API:

```http
POST /api/obs/recovery/approve
Content-Type: application/json
X-AdultCam-Request: 1
X-AdultCam-Confirm: I_APPROVE

{"session_id":1}
```

Wymaga autoryzacji operatora. Kontroler sprawdza stan sesji, aktualne
oświadczenie, brak nierozstrzygniętych operacji, wcześniejszy zatwierdzony
START, stabilną aktywność wyjścia i dokładny zatwierdzony adres docelowy.
Endpoint wykonuje tylko odczyty OBS; nie wysyła `StartStream`.

## 4. Dodatkowe ograniczenia

- Połączenia zdalne do docelowych serwerów nadawczych wymagają `rtmps://`.
  Zwykły `rtmp://` jest dozwolony wyłącznie do `127.0.0.1` / `localhost`.
- Obsługa RTMPS i rzeczywiste odbieranie obrazu u operatora wymagają
  testów na docelowym systemie przed jakimkolwiek wydaniem produkcyjnym.
- Panel HTTP Basic jest dostępny tylko przez loopback (ewentualnie tunel SSH).
- Wciąż nie ma OIDC/RBAC, prawdziwych adapterów platform, awaryjnej anonimizacji
  obrazu ani potwierdzenia dostarczenia do usług zewnętrznych.
