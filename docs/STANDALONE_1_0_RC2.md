# AdultCam Ω 1.0.0rc2 — samodzielne laboratorium bez kont zewnętrznych

## Uruchomienie bez kont platform

Wymagania: Python 3.11+, własne hasło operatora co najmniej 16 znaków.

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[test]'
read -rsp 'Hasło lokalne: ' ADULTCAM_ADMIN_PASSWORD; echo
export ADULTCAM_ADMIN_PASSWORD
adultcam-omega-lab
```

Panel: http://127.0.0.1:8765. Nie wystawiaj portu 8765 do internetu. Tryb OFFLINE_LAB blokuje tworzenie i zatwierdzanie poleceń START OBS, również kiedy wcześniej utworzony zamiar pochodzi z zapisanej bazy. Zewnętrzne adaptery odczytu statusów są wyłączone niezależnie od obecności tokenów w środowisku. Tryb OFFLINE_LAB nie może pracować jako production. Ręcznie wpisane profile, harmonogramy i księga są nadal dostępne. Awaryjne STOP może działać na lokalnym OBS.

## Przyszłe konta bez sekretów

Widok Przyszłe konta i API:

- GET /api/platform-registry — statyczny katalog obsługi planowanej, bez sieci.
- GET /api/platform-connections — lokalna lista pozycji.
- POST /api/platform-connections — tworzy wpis z platform_id oraz account_label.
- POST /api/platform-connections/{id}/prepare — zapisuje AWAITING_AUTHORIZATION. NIE loguje do platformy, nie żąda OAuth i nie oznacza CONNECTED.
- POST /api/platform-connections/{id}/disable — wyłącza wpis tylko lokalnie; nie odwołuje uprawnień na żadnej platformie.

Wymagane uprawnienia operatora i CSRF przy modyfikacji. Statusy przechowywane w SQLite i audytowane. Żadne hasło, token, stream key, URL z tokenem czy dokument tożsamości nie są akceptowane ani przechowywane. Nowych połączeń zewnętrznych nie można aktywować bez osobnego, zweryfikowanego procesu integracyjnego.

Po założeniu legalnych kont wdrożenie adapterów powinno objąć aktualne regulaminy i API, OAuth/zakresy uprawnień, sekret store niezależny od tej bazy, niezależne potwierdzenie odczytu i skutków działań oraz rzeczywiste testy bezpieczeństwa.

## Granica ukończenia

Samodzielny tryb laboratoryjny może działać bez kont. Ogólna wersja 1.0.0 GA pozostaje BLOCKED: nie ma pozytywnych testów rzeczywistego OBS, sprzętowego fail-closed obrazu, potwierdzonego odbioru na zewnętrznych platformach, bezpiecznych przejść PRIVATE i odbioru na Samsungu S24 Ultra. Warunki: docs/RELEASE_1_0_ACCEPTANCE.md.
