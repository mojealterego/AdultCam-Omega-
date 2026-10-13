# AdultCam Ω 0.5.0 — bramka testu prawdziwego OBS i prywatnego RTMP

Komenda jest **tylko odczytem** WebSocket OBS v5 na loopback. Nie wysyła
`StartStream`, `StopStream` ani żądania na żadną zewnętrzną platformę.
Nie uruchamiaj testu z prawdziwymi osobami ani danymi identyfikującymi.

1. Na hoście z OBS Studio utwórz scenę o nazwie
   `ADULTCAM_SYNTHETIC_TEST`. Umieść w niej **wyłącznie** sztuczną planszę
   testową / paski kolorów. Sprawdź ręcznie także ukryte źródła.
2. W OBS Streaming → Custom: serwer
   `rtmp://127.0.0.1:19350/live`, klucz testowy `omega-test`.
   Używaj testowego klucza; nie wstawiaj sekretów żadnej platformy.
3. Włącz OBS WebSocket v5 z uwierzytelnianiem, ustaw hasło w lokalnym
   `OBS_WS_PASSWORD` i wykonaj:

   ```bash
   python -m adultcam.obs_acceptance --check --port 19350
   ```

4. Jeśli pojawi się `READY_FOR_MANUAL_TEST`, uruchom w osobnym terminalu
   lokalny odbiornik FFmpeg:

   ```bash
   python -m adultcam.rtmp_probe --listen-obs --confirm-test-only --port 19350 --duration 10 --timeout 45
   ```

5. Ręcznie kliknij Start Streaming w OBS, a po próbce ręcznie Stop Streaming.
   Zweryfikuj stan STOPPED w OBS. Zapisz wynik JSON z odbiornika.
   `RECEIVER_VIDEO_FRAMES` i co najmniej 3 klatki potwierdzają transport
   do **tego lokalnego odbiornika**, nie odbiór na platformie.

Preflight odrzuca: aktywne wyjście, stan reconnect, niezgodną scenę,
niezgodny serwer lub prawdziwy klucz zamiast literalnego `omega-test`.
Wyjątki OBS są maskowane i nie trafiają do raportu.

Bramka nie weryfikuje faktycznej zawartości sceny, praw użytkowników
ani tożsamości nadawcy. Obecny kod nie przeprowadził testu na fizycznym OBS.
Do zatwierdzenia produkcyjnego pozostają niezależne RTMPS E2E,
receipts platformy, ochrona obrazu fail-closed i audyt.
