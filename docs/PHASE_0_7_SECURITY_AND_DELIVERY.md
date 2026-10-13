# AdultCam Ω 0.7.0 — odbiór, źródła dowodów i ochrona obrazu

## Weryfikowalne zakresy

1. **OBS (lokalne sterowanie):** status `outputActive` jest stanem OBS, nie dowodem odbioru na platformie.
2. **Własny odbiornik RTMPS:** zapis podpisanej próbki `OWNED_INGEST_RECEIVED` wymaga świeżego potwierdzenia liczby klatek, HMAC, zarejestrowanego `receiver_id` i unikalnego `nonce`.
3. **Platformy zewnętrzne:** pozostają `MANUAL_ONLY`, `platform_delivery=UNVERIFIED`. Dopiero oficjalny, uwierzytelniony odczyt ze wskazanej platformy może być podstawą osobnego adaptera `PLATFORM_CONFIRMED`; taka integracja **nie jest wykonana**.
4. **Ochrona:** dostępny jest prawdziwy filtr RGB24 (`privacy_frames`) wymuszający czarny obraz przy braku detekcji. Maskowanie prostokątów umożliwia testy algorytmiczne, lecz brak wiarygodnej detekcji i śledzenia twarzy. To **nie jest potwierdzona produkcyjna ochrona twarzy**.

## Parametry lokalnego serwera — podpisywane potwierdzenia

W bezpiecznym menedżerze sekretów ustaw `ADULTCAM_INGEST_HMAC_KEY` (losowy sekret co najmniej 32 bajty) oraz `ADULTCAM_INGEST_RECEIVERS` (lista identyfikatorów odbiorników, po przecinku). Nie dodawaj tych wartości do GitHub, URL, ekranu, logów ani pliku `.env` w repozytorium. Sekret odbiornika nie może być tym samym kluczem co JWT/OIDC, stream key czy hasło OBS.

Własny odbiornik wysyła POST `/api/ingest/receipts` z nagłówkiem `X-AdultCam-Ingest-Signature` (HMAC-SHA256, małe hex). Kanoniczny JSON do podpisu: `json.dumps(body, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')`. Dokładnie siedem pól:

```json
{
  "receiver_id": "my-private-ingest",
  "session_id": 1,
  "nonce": "auniquecryptorandomnonce00001",
  "received_frames": 15,
  "observed_at": "2026-10-14T00:00:00+00:00",
  "transport": "RTMPS",
  "scope": "OWNED_INGEST"
}
```

Znacznik czasu musi mieścić się w oknie ±90 sekund, nonce musi być unikatowy dla odbiornika. Odrzucone są m.in. brak/niepoprawny podpis, nadmiarowe pola, nieprawidłowy format danych, nieznany odbiornik, stare próbki i ponowne wysłanie nonce. Poprawna odpowiedź **nadal zawiera `platform_delivery: UNVERIFIED`**.

API jest przeznaczone dla odbiornika, nie dla przeglądarki. Wdrożenie przez sieć musi mieć zweryfikowany TLS i reguły ograniczające nadawców; obecny serwer FastAPI pozostaje wyłącznie na loopback. Nie wystawiaj go bezpośrednio do internetu.

Aby sprawdzić lokalnie realny odbiór syntetycznych klatek po TLS:

```bash
python -m adultcam.rtmps_probe
python -m pytest -q tests/test_070_real_receipt.py
```

Test nie uruchamia OBS i nie kontaktuje się z platformą dla dorosłych. Do realnego testu OBS użyj procedury `docs/OBS_REAL_DEVICE_GATE_0_5.md` i dostarcz dowód odbioru osobno.

## Bramka sceny bezpieczeństwa OBS

Opcjonalna zmienna `ADULTCAM_PRIVACY_SCENE` ustala dokładną nazwę programowej sceny OBS. Ustawienie wymaga tej sceny przed `StartStream` oraz przy każdym odczycie monitora. Przy niezgodności START jest blokowany, a monitor zgłasza `PRIVACY_SCENE_DRIFT` i przełącza sesję do RECOVERY, jeśli trwał LIVE.

**Ważne:** weryfikacja nazwy sceny nie dowodzi, że scena jest faktycznie zabezpieczona. Monitor jest odczytowy, a reakcja RECOVERY nie zatrzymuje automatycznie emisji. Nie traktuj tego jako zabezpieczenia przed wyciekiem wizerunku. Dla realnych źródeł niezbędny jest sprawdzony pipeline anonimizacji **przed OBS** i sprzętowe testy skrajnych sytuacji.

## Kontrolowany filtr zaciemniający (bez analizy twarzy)

Filtr testowy bierze `RGB24` przez stdin, wypuszcza **wyłącznie pełne zaczernione klatki** przez stdout i zatrzymuje pracę w razie niekompletnej klatki.

```bash
python -m adultcam.privacy_frames --width 640 --height 360
```

Przeznaczenie: awaryjne źródło obrazu/blackout, nie gotowy selektywny masker twarzy. Nie przekazuj do niego nieuprawnionego nagrania. Docelowy proces nadawczy musi w razie zakończenia filtra zatrzymać źródło wideo — nie przełączać automatycznie na niechroniony obraz.

## Nieukończone wymagania produkcyjne

- Pełny test fizycznego OBS Studio z odbiornikiem i odpowiednią liczbą klatek.
- Niezależne potwierdzenie odbioru bezpośrednio z API platformy.
- Gotowy tracker twarzy, ochrona przy zaniku śledzenia, zmianie kamery i dwóch osobach.
- Wymuszenie działania ochrony na każdym fizycznym torze wideo, odbiór fail-closed przy awarii procesu.
- Zweryfikowany zewnętrzny HTTPS/OIDC i test mobilny Samsung S24 Ultra.
- Formalny audyt reguł serwisów oraz zgód i pełnoletności uczestników.

**Wydanie 0.7.0 jest kolejnym etapem laboratoryjnym, nie wydaniem produkcyjnym.**
