# AdultCam Ω 0.6 — zdalne logowanie OIDC / PKCE i role

## Warunki uruchomienia

Wersja 0.6.0 zawiera przeglądarkowy Authorization Code + PKCE S256,
jednorazowy parametr state przypisany do cookie loginu, sprawdzany nonce
podpisanego RS256 ID tokenu, odrębną weryfikację RS256 JWT access token
z właściwym issuer, API audience i listą IdP claims adultcam_roles.
Sub musi być identyczny w obu tokenach.

Backend zachowuje wyłącznie hash losowego tokenu sesji (SQLite).
Cookie sesji ma HttpOnly, Secure, SameSite Strict i trwa 15 minut.
Żaden access/refresh token IdP nie jest zapisywany do JS/browser storage
ani bazy danych. Przechowywana jest tożsamość i rola.
Zapis wymaga Origin dokładnie równemu public HTTPS origin,
X-AdultCam-CSRF oraz X-AdultCam-Request: 1. Wrażliwe operacje OBS
wymagają również odrębnego zatwierdzenia. Admin może unieważniać sesje.

## Konfiguracja IdP (same adresy są tylko przykładami)

Zarejestruj publicznego klienta OIDC z flow Authorization Code i PKCE S256,
redirect URI https://twoja-domena/auth/callback, scope openid,
access token RS256 (audience API) z adultcam_roles i id_token RS256
(audience client ID), z poprawnym nonce i zgodnym subject.

Zmienne środowiskowe do ustawienia w bezpiecznej konfiguracji hosta:

- ADULTCAM_AUTH_MODE=oidc
- ADULTCAM_OIDC_ISSUER=https://identity.example.test/
- ADULTCAM_OIDC_AUDIENCE=adultcam-omega-api
- ADULTCAM_OIDC_JWKS_URL=https://identity.example.test/keys
- ADULTCAM_OIDC_AUTHORIZATION_URL=https://identity.example.test/authorize
- ADULTCAM_OIDC_TOKEN_URL=https://identity.example.test/token
- ADULTCAM_OIDC_CLIENT_ID=adultcam-operator-ui
- ADULTCAM_PUBLIC_ORIGIN=https://control.example.test
- ADULTCAM_PUBLIC_DOMAIN=control.example.test

Zastąp przykładowe domeny rzeczywistymi, własnymi adresami HTTPS.
Wszystkie URL IdP muszą być na tym samym host/porcie co issuer.
Nie zapisuj tokenów, kluczy nadawania ani hasła OBS w repozytorium.

## Dostęp zdalny

Na serwerze OBS uruchom AdultCam API wyłącznie na 127.0.0.1:8765.
W Caddy wdroż deploy/Caddyfile, z publiczną domeną HTTPS/DNS.
Reverse proxy nadpisuje wewnętrzny Host na localhost, natomiast
aplikacja weryfikuje Origin przeglądarki wg ADULTCAM_PUBLIC_ORIGIN.
Porty OBS 4455, API 8765 i testowy 19350 pozostają NIEPUBLICZNE.
Publiczny może być tylko kontrolowany HTTPS na 443/80.
Panel działa jako strona WWW na telefonach, ale Samsung S24 Ultra
nie był jeszcze przetestowany na rzeczywistym urządzeniu.

## Uprawnienia i administracja

- viewer: odczyt bez księgi przychodów;
- operator: operacje sesji i zatwierdzanie OBS;
- admin: plus księga, oświadczenia, lista sesji i unieważnianie.

GET /api/auth/sessions zwraca jedynie subject, role, expires_at.
POST /api/auth/sessions/revoke przyjmuje JSON {"subject":"id-z-IdP"}
i wymaga roli admin oraz poprawnego CSRF/Origin w przeglądarce.
POST /auth/logout unieważnia sesję bieżącego operatora.

## Ograniczenia przed wydaniem produkcyjnym

Wymagana jest weryfikacja prawdziwego IdP, publicznego HTTPS,
mobilnego połączenia z niezależnej sieci, rate limitów ingress,
stanu OBS/RTMPS na rzeczywistym urządzeniu, zatwierdzeń
pełnoletności i świadomej zgody uczestników oraz audytu
bezpieczeństwa. Nie uruchamiano prawdziwej platformy zewnętrznej.
