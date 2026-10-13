# Zdalny panel AdultCam Ω na Samsungu S24 Ultra — bez publicznego HTTP

Stan: **zalecana konfiguracja operatora, nie test wdrożeniowy na fizycznym telefonie**.

Backend oraz OBS Studio działają na tym samym zaufanym komputerze. `adultcam-omega` nadal nasłuchuje **wyłącznie 127.0.0.1:8765**, a obs-websocket wyłącznie na 127.0.0.1:4455. Nie konfiguruj przekierowania portów 8765 ani 4455 na routerze. Publiczny serwer HTTP/Basic bez TLS nie jest obsługiwany.

## Dostęp przez tunel SSH

1. Na komputerze skonfiguruj osobne konto SSH, uwierzytelnianie kluczem publicznym i ograniczenie dostępu (preferuj lokalną sieć lub bezpieczną sieć prywatną). Nie przechowuj hasła operatora w skryptach.
2. Uruchom OBS Studio (lokalny obs-websocket v5 z hasłem), a potem backend AdultCam na komputerze.
3. Na telefonie w Termux zainstaluj klienta OpenSSH oraz utwórz klucz SSH. Dodaj klucz publiczny telefonu do autoryzowanego konta na komputerze przez zaufany kanał.
4. W Termux uruchom tunel, zastępując `KONTO_NA_PC` oraz `ADRES_PC` **wyłącznie lokalnie** faktyczną konfiguracją:

   ```sh
   ssh -N -o ExitOnForwardFailure=yes -L 127.0.0.1:8765:127.0.0.1:8765 KONTO_NA_PC@ADRES_PC
   ```

5. Na telefonie otwórz `http://127.0.0.1:8765` — dostęp idzie przez zaszyfrowane połączenie SSH, podczas gdy przeglądarka łączy się wyłącznie z lokalnym interfejsem Termux. Zweryfikuj odcisk klucza hosta SSH przy pierwszym połączeniu i nie wyłączaj weryfikacji hosta.

**Ograniczenia:** hasło HTTP Basic pozostaje osobnym poświadczeniem. Tunel nie zapewnia rozdzielenia ról ani OIDC, a sama przeglądarka telefonu może zapamiętać poświadczenia. Nie udostępniaj tunelu w LAN (`-g`, `0.0.0.0`). Przetestuj utratę sieci, wygaszenie telefonu i utratę sesji SSH. Jeśli port 8765 jest już zajęty na telefonie, zmień tylko port nasłuchu lokalnego tunelu i wpisz właściwy lokalny URL w przeglądarce.

## Weryfikacja bezpieczeństwa

- Na komputerze `ss -ltn` ma pokazać port 8765 tylko na loopback.
- Na telefonie po przerwaniu tunelu strona ma być niedostępna.
- Test Host-header i test bez uwierzytelnienia mają zwracać błąd.
- Otwarty tunel ani sukces `GetStreamStatus` **nie potwierdzają odbioru transmisji na platformie**.
- Operacje START i STOP nadal wymagają dwustopniowego zatwierdzenia w panelu.

## Docelowa architektura produkcyjna

OIDC, odrębne role, lokalny HTTPS/mTLS, tokeny odwoływalne, audyt, brak ekspozycji OBS na publiczny internet i testy na prawdziwym urządzeniu. Do czasu ich wykonania tunel SSH to **wariant ograniczony i nadzorowany**, nie certyfikowany tryb produkcyjny.
