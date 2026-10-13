# AdultCam Ω 0.5.0 — OIDC Bearer JWT i uprawnienia RBAC

## Zakres

Backend udostępnia opcjonalny tryb JWT Bearer dla API. W trybie `local`
(domyślny) pozostaje poprzednie HTTP Basic przez loopback. W trybie `oidc`
Basic jest wyłączony, a uprawnienia wynikają wyłącznie z **podpisanych**
przez dostawcę tożsamości claimów JWT.

System nie zawiera jeszcze interaktywnego logowania OAuth Authorization Code
z PKCE, rejestracji aplikacji u dostawcy OIDC ani produkcyjnego serwera HTTPS.
Backend pozostaje dostępny wyłącznie pod `127.0.0.1:8765`. Nie otwieraj
portu bezpośrednio w publicznym internecie lub sieci lokalnej.

## Wymagania dostawcy

Wybierz zaufany OIDC issuer, który wystawia **RS256 JWT access tokens**
z unikatowym `aud` dedykowanym API AdultCam oraz prywatnym claimem
`adultcam_roles` typu lista, zawierającym jedną lub kilka ról:
`viewer`, `operator`, `admin`. Role musi przypisywać zaufany IdP.
Nagłówki klienta, takie jak `X-AdultCam-Role`, nie mają znaczenia.

Weryfikowane są podpis (publiczny klucz JWKS), przypięty algorytm RS256,
issuer, audience, subject, iat i exp. JWKS musi być dostępny po HTTPS
z tej samej nazwy hosta i portu, co issuer. Timeout pobrania klucza
wynosi 3 s, cache JWKS 120 s. Klucze prywatne nie są potrzebne aplikacji.

## Konfiguracja (przykładowe, NIEISTNIEJĄCE domeny)

```bash
export ADULTCAM_AUTH_MODE=oidc
export ADULTCAM_OIDC_ISSUER='https://identity.example.test/'
export ADULTCAM_OIDC_AUDIENCE='adultcam-omega-api'
export ADULTCAM_OIDC_JWKS_URL='https://identity.example.test/.well-known/jwks.json'
python -m adultcam
```

Nie używaj danych z przykładu w produkcji. Wszystkie parametry pobierz
ze zweryfikowanej konfiguracji posiadanego IdP. Token musi pozostawać
lokalnie w `ADULTCAM_ACCESS_TOKEN`, nigdy w repozytorium, adresie URL
czy wiadomościach.

## Uprawnienia

| Operacja | viewer | operator | admin |
| --- | --- | --- | --- |
| Odczyt dashboard / strategii / monitoringu | TAK | TAK | TAK |
| Tworzenie sesji / profilów / zamiarów OBS | NIE | TAK | TAK |
| Zatwierdzony START/STOP, ręczne RECOVERY | NIE | TAK | TAK |
| Rejestr oświadczeń pełnoletności / zgód | NIE | NIE | TAK |
| Ręczna księga przychodów | NIE | NIE | TAK |

Oświadczenie operatora **nie jest niezależnym sprawdzeniem dokumentów**.
Wszystkie dotychczasowe zatwierdzenia transmisji, allowlisty, wyjście
`UNKNOWN`, blokady pojedynczych operacji i anti-CSRF pozostają aktywne.
Audyt zapisuje `operator_subject` w wybranych zdarzeniach wysokiego ryzyka.

```bash
curl --fail-with-body http://127.0.0.1:8765/api/auth/me \
  -H "Authorization: Bearer $ADULTCAM_ACCESS_TOKEN"
curl --fail-with-body http://127.0.0.1:8765/api/dashboard \
  -H "Authorization: Bearer $ADULTCAM_ACCESS_TOKEN"
```

Dla mutacji wymagany jest `X-AdultCam-Request: 1`, a dla jawnego
zatwierdzania OBS również `X-AdultCam-Confirm: I_APPROVE`.
Nigdy nie wysyłaj bearer tokenów w querystring.

## Samsung Galaxy S24 Ultra

Dostępny jest bezpieczny wariant połączenia SSH z przekierowaniem
portu 8765 do loopback hosta OBS — opisany w `ANDROID_REMOTE.md`.
Nie wyłączaj weryfikacji klucza hosta SSH; logowanie kluczem prywatnym
urządzenia. API OIDC można wtedy wywoływać z uprawnionego klienta HTTP.

**HTML panel nie ma interaktywnego OIDC login**, zatem w tym etapie
mobilna przeglądarka obsługuje tylko poprzedni tryb lokalny Basic przez SSH.

## Poza zakresem 0.5.0

Rzeczywisty IdP, login w przeglądarce, rotacja i unieważnianie sesji,
mTLS/HTTPS przed dostępem publicznym, osobne konta pracowników w UI,
test fizycznego telefonu, autoryzowane integracje z platformami,
receipts po stronie platformy i anonimizacja wideo.
