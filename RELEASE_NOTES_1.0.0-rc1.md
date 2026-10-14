# AdultCam Ω 1.0.0rc1 — kandydat do odbioru technicznego

Przygotowana bramka wydania z weryfikacją podpisu niezależnego audytora (Ed25519), kompletności dziewięciu zestawów dowodów, hashy SHA-256, dat oraz wymogiem rzeczywistej konfiguracji HTTPS/OIDC.

Dodano testy odrzucenia: brak potwierdzenia, nieznany klucz, zmiana dowodów, niewłaściwy wynik, przeterminowanie i dowiązanie symboliczne. Dodatkowa kontrola przy starcie backendu w trybie ADULTCAM_RELEASE_MODE=production.

Stan faktyczny: na realnym sprzęcie operatora nie przeprowadzono niezależnie obserwowanego testu OBS Studio, nie potwierdzono odbioru na zewnętrznej platformie, nie przeprowadzono produkcyjnej walidacji ochrony twarzy przed OBS ani testu fizycznego Samsung S24 Ultra. Testy laboratoryjne nie są substytutem tych dowodów.

Werdykt: NOT_PRODUCTION_READY. Nie wydano wersji GA 1.0.0. Istnieje wyłącznie wersja 1.0.0rc1 do oceny i testów. Kryteria: docs/RELEASE_1_0_ACCEPTANCE.md.
