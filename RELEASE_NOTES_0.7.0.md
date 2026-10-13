# AdultCam Ω 0.7.0 — signed local ingest receipts and privacy interlock

- Autoryzowane podpisem HMAC-SHA256 potwierdzenia **własnego odbiornika RTMPS**. Kontrola zegara, whitelisty odbiorników, replay protection (unikalny nonce), transakcyjny zapis i audyt. Potwierdzenia nie są oznaczane jako odbiór na platformie.
- Odczyt historii potwierdzeń z oddzielnym interfejsem uwierzytelnionym operatora.
- Opcjonalny interlock sceny OBS `ADULTCAM_PRIVACY_SCENE` blokujący START przy niedopasowaniu i wykrywający drift podczas monitoringu.
- Wydzielony proces zaciemniający RGB24 z bezpiecznym, czarnym wyjściem, również przy braku danych z detektora; testy redakcji fragmentów klatek.
- Test rzeczywistego lokalnego TLS/RTMPS + signed receipt; regresje replay, podrabiania podpisu, braku detekcji, odmowy START oraz kontroli dryfu sceny.

**Granice:** brak oficjalnego API zewnętrznych platform; brak rzeczywistego OBS E2E; brak produkcyjnego trackera twarzy i dowiedzionego całego toru wideo. System pozostaje eksperymentalny, `platform_delivery = UNVERIFIED`.

Pełne instrukcje: [docs/PHASE_0_7_SECURITY_AND_DELIVERY.md](docs/PHASE_0_7_SECURITY_AND_DELIVERY.md).
