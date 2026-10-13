# AdultCam Ω 0.8.0 — trasy i prywatny laboratoryjny multistream

## Zweryfikowany zakres techniczny

- Jeden syntetyczny strumień FFmpeg jest kodowany i wysyłany jednocześnie do 2–8 niezależnych lokalnych odbiorników RTMP. Wszystkie adresy są generowane jako `127.0.0.1`. Odbiorniki zliczają odebrane klatki; obraz nie jest zapisywany na dysk.
- Trwałe plany tras w SQLite są powiązane z sesją, kontrolowane przez uprawnienia operatora i rejestrowane w audycie.
- Ocena planu PRIVATE jest blokowana, jeżeli pozostaje którakolwiek trasa PUBLIC.
- Potwierdzenia z własnych odbiorników, podpisane HMAC, są akceptowane jako lokalny dowód odebrania klatek przez zadeklarowanego odbiorcę maksymalnie przez 90 sekund.
- Zewnętrzne platformy pozostają `MANUAL_ONLY`. Żadna trasa nie wysyła polecenia START/STOP, nie otwiera ani nie zamyka pokoju prywatnego i nie zawiera kluczy transmisyjnych.

## Test rzeczywistego lokalnego transportu

Wymagany FFmpeg:

```bash
python -m adultcam.simulcast_lab --receivers 2 --duration 3
```

Oczekiwany wynik zawiera `result=LOCAL_SIMULCAST_VERIFIED`, co najmniej 3 klatki dla każdego z dwóch odbiorników, `broadcast_to_external_platforms=false` i `platform_delivery=UNVERIFIED`. To nie jest test OBS ani zewnętrznej platformy.

## Operator API

Wymagane uwierzytelnienie. Zmiany wymagają roli operator lub admin oraz `X-AdultCam-Request: 1`:

- `POST /api/routes` — body: `{session_id,route_key,platform,audience,capability,receiver_id}`.
- `GET /api/routes?session_id=1` — lista lokalnych tras.
- `DELETE /api/routes/{id}` — usunięcie planu, nie działania na platformie.
- `GET /api/routes/evaluate?session_id=1&audience=PRIVATE` — bezpieczna ocena bez skutków zewnętrznych.

Dozwolone wartości: `audience=PUBLIC|PRIVATE`, `capability=MANUAL_ONLY|OWNED_INGEST_TEST`. W `MANUAL_ONLY` ustaw `receiver_id=null`. W trybie własnego odbiornika ID musi znajdować się w `ADULTCAM_INGEST_RECEIVERS`, a `ADULTCAM_INGEST_HMAC_KEY` musi być ustawiony w menedżerze sekretów. Nie zapisuj klucza w repozytorium ani interfejsie.

Nawet wynik `decision=LAB_EVIDENCE_ONLY` zawiera `private_transition_authorized=false`, `external_actions_performed=0` i `platform_delivery=UNVERIFIED`. To nie jest zgoda na transmisję.

## Wymagane do produkcji

- Zgodne z regulaminami adaptery oficjalnych API platform i ich wiarygodne odpowiedzi.
- Rzeczywiste, zweryfikowane zatrzymanie wszystkich publicznych wyjść przed sesją PRIVATE, także po utracie sieci.
- Pełna anonimizacja materiału na każdym torze źródłowym przed OBS, testowana przy zaniku śledzenia.
- Testy z prawdziwym OBS, niezależnym odbiornikiem RTMPS i Samsungiem Galaxy S24 Ultra.
- Potwierdzenie pełnoletności, świadomej zgody uczestników i warunków prawnych.

**Status: laboratorium, nie produkcja.**