# AdultCam Omega 0.9.0 — laboratoryjny status API i prywatność obrazu

## Odczyt statusu
Wdrożono adapter Twitch Helix Get Streams. Żądanie GET trafia tylko do oficjalnego endpointu, z poświadczeniami z lokalnego środowiska. Trzydziestosekundowy cache ogranicza liczbę wywołań. Wyniki LIVE/OFFLINE oznaczają status kanału, nie weryfikację odbioru klatek. Brak sterowania emisją. Twitch wymaga przestrzegania swoich Community Guidelines i ten adapter jest wyłącznie do zastosowań zgodnych z tym regulaminem.

Dokumentacja: https://dev.twitch.tv/docs/api/reference/#get-streams

Konfiguracja lokalna: ADULTCAM_TWITCH_CLIENT_ID, ADULTCAM_TWITCH_TOKEN, ADULTCAM_TWITCH_BROADCASTER_ID.
Endpoint w konsoli: GET /api/platforms/twitch/status.

## Ochrona RGB24
Moduł adultcam.privacy_pipeline przyjmuje binarne klatki RGB24. Bez zaufanej detekcji klatka jest w całości zaczerniana. Niepewność co do liczby twarzy i błędy detekcji skutkują zaczernieniem. Niekompletna klatka przerywa przetwarzanie. Wersja domyślna produkuje tylko czarny obraz; detektor można dostarczyć przez programowy interfejs rozszerzeń.

Test: python -m pytest -q tests/test_090_official_platform.py tests/test_090_platform_api.py tests/test_090_privacy_pipeline.py tests/test_090_privacy_transport.py

## Ograniczenia produkcyjne
Brak autoryzowanych integracji wykonawczych ze wskazanymi platformami, brak niezależnego dowodu emisji, brak produkcyjnego selektywnego maskowania twarzy i integracji toru wideo z OBS. Brak fizycznych testów na Samsungu S24 Ultra. Status: NOT_PRODUCTION_READY.


## Oficjalny adapter platformy — statystyki własnego konta Chaturbate

Oficjalna dokumentacja: https://chaturbate.com/statsapi/documentation/

Serwis udostępnia właścicielowi konta odczyt wybranych statystyk. Wymaga nazwy nadawcy i lokalnie przechowywanego 24-znakowego tokenu wygenerowanego przez konto. Odświeżanie danych jest po stronie dostawcy około co pięć minut.

Ustaw w środowisku serwera:
- `ADULTCAM_CHATURBATE_USERNAME`
- `ADULTCAM_CHATURBATE_STATS_TOKEN`

Uwierzytelniony endpoint AdultCam: `GET /api/platforms/chaturbate/status`.
Wynik: `ONLINE_REPORTED`, `OFFLINE_REPORTED` lub `UNVERIFIED`, z `platform_delivery=UNVERIFIED` i `broadcast_control=DISABLED`.

Ważne: dokumentacja platformy wymaga wysyłania tokenu jako parametru zapytania HTTPS. Nie loguj pełnego adresu API i nie przekazuj tokenu w konwersacji, publicznym URL ani repozytorium. Adapter nie pobiera salda, identyfikatorów widzów ani danych finansowych do odpowiedzi. Nie wykonuje żadnych operacji zmieniających konto.

Testowano na atrapach odpowiedzi HTTP, bez rzeczywistego konta. Nie ma dowodu faktycznego odbioru konkretnych klatek przez platformę ani live-testu połączenia.
