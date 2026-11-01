# Alice

Modeler per chitarra open source, controllato via web, pensato per pedaliere fatte in casa
(Raspberry Pi 5, mini-PC x86). Usa profili [NAM](https://github.com/sdatkinson/neural-amp-modeler)
e plugin LV2, con un'interfaccia a blocchi ispirata a Line 6 Helix.

> Stato: **prima versione in sviluppo**. Funzionano il motore audio, l'interfaccia web con
> percorso in serie, i profili NAM, gli IR, i preset e la prova d'ascolto. In arrivo: blocchi in
> parallelo nell'interfaccia (il motore li gestisce già), footswitch/MIDI, snapshot.

## Avvio rapido (anche su PC/WSL2, senza scheda audio)

```sh
docker compose up -d --build
```

Poi apri **http://localhost:8090** (da un altro dispositivo: `http://<ip-del-computer>:8090`).

**Suonare con la chitarra dal PC (ponte audio)**: nella barra "Suona dal vivo" scegli l'ingresso
della scheda audio (es. HX Stomp) e il canale della chitarra, poi premi **Attiva** e consenti
l'accesso al microfono. Il browser cattura la chitarra, la invia al motore via WebSocket e
riproduce il suono elaborato. Ritardo tipico 40–80 ms: va bene per provare i suoni, non per
suonare dal vivo. Il browser concede l'ingresso audio solo da `http://localhost` o in https.
Su Linux nativo / Raspberry Pi la scheda audio si collega direttamente al motore (pochi ms).

In alternativa, senza chitarra: carica un file DI (chitarra registrata pulita, `.wav`)
nella barra in basso e premi **Ascolta**: il backend lo fa passare nella catena e il browser
riproduce il risultato. I profili NAM si caricano dal blocco Amp (gratuiti su
[TONE3000](https://www.tone3000.com)), gli IR dal blocco IR Cab.

File di test (modelli NAM con pesi casuali, IR approssimativo, DI sintetico):

```sh
python3 scripts/make_test_nam.py data/models
docker exec alice sh /opt/alice/scripts/make_test_ir.sh /data/irs/test-cab.wav
docker exec alice sox -n -r 48000 -c 1 -b 24 /data/di/test.wav synth 8 pluck E2
```

Su Linux nativo / Raspberry Pi con scheda audio reale (imposta `ALICE_ALSA_DEVICE` in
`docker-compose.hw.yml`, vedi `aplay -l`):

```sh
docker compose -f docker-compose.yml -f docker-compose.hw.yml up -d
```

## Installazione su Linux con scheda audio (es. HX Stomp)

È l'uso previsto: la scheda audio è collegata al computer che fa girare Alice e il
browser serve solo da controllo (anche da tablet o telefono). Ritardo di pochi millisecondi.

1. **Prerequisiti**: Docker con il plugin compose; utente nel gruppo `audio`
   (`sudo usermod -aG audio $USER`, poi rientra). Per il tempo reale conviene il governor
   della CPU su `performance` e, se disponibile, un kernel `lowlatency` o `PREEMPT_RT`.
2. **Trova la scheda audio**:
   ```sh
   aplay -l          # es. "card 1: Stomp [HX Stomp], device 0"
   ```
   e imposta `ALICE_ALSA_DEVICE` in `docker-compose.hw.yml` (es. `hw:Stomp` o `hw:1`).
3. **Canali**: la catena prende l'audio da `ALICE_INPUTS` (default `system:capture_1`) e lo
   manda a `ALICE_OUTPUTS` (default `system:playback_1,system:playback_2`). Con una scheda a più
   canali, come la HX Stomp, imposta il canale a cui arriva la chitarra, es.
   `ALICE_INPUTS: system:capture_1`. Per vedere le porte: `docker exec alice jack_lsp`.
4. **Avvio**:
   ```sh
   docker compose -f docker-compose.yml -f docker-compose.hw.yml up -d --build
   docker logs -f alice      # deve comparire "avvio jackd (alsa, ...)" e "Alice pronta"
   ```
5. Apri `http://<ip-del-pc>:8090`. Se senti crepitii (xrun nella barra in alto), alza
   `ALICE_BUFFER_SIZE` a 256.

Con la HX Stomp conviene un preset vuoto, così ad Alice arriva la chitarra pulita.

## Architettura

Un solo container con:

- **JACK** (driver `dummy` per lo sviluppo, `alsa` con la scheda audio reale);
- **[mod-host](https://github.com/moddevices/mod-host)**, host LV2 comandato via socket;
- plugin LV2: **[NAM](https://github.com/mikeoliphant/neural-amp-modeler-lv2)**, LSP (gate, IR,
  chorus), Guitarix (drive, delay, modulazioni), Dragonfly (riverberi);
- **backend** Python/FastAPI (`backend/alice`): stato della pedaliera, routing, file, preset,
  WebSocket con carico DSP;
- **ponte audio** (`backend/alice/bridge.py`, porta 8091): processo separato che scambia l'audio
  col browser; separato dal server web perché la sua callback JACK non deve aspettare il GIL;
- **interfaccia web** (`web/`): JavaScript puro senza dipendenze esterne, funziona offline.

Una pedaliera è una catena di elementi; ogni elemento è un blocco o uno *split* con più rami in
parallelo (`backend/alice/engine.py`). Il backend calcola le differenze e invia a mod-host solo i
comandi necessari. Il catalogo dei blocchi è in `backend/alice/catalog.py`: per aggiungere un
effetto basta indicare l'URI LV2 e i parametri da mostrare.

### API principali

| Metodo | Percorso | Descrizione |
|---|---|---|
| GET | `/api/catalog` | categorie e modelli di blocco |
| GET, PUT | `/api/board` | pedaliera corrente |
| PATCH | `/api/blocks/{id}` | parametri, on/off, file di un blocco |
| GET, PUT, DELETE | `/api/files/{tipo}[/{nome}]` | file utente: `nam`, `ir`, `di` (PUT: corpo = contenuto) |
| GET, PUT, DELETE | `/api/presets[/{nome}]` | preset; POST `/api/presets/{nome}/load` per richiamarlo |
| POST | `/api/render?di=nome.wav` | fa passare un DI nella catena, restituisce il WAV |
| WS | `/ws` | stato (DSP, xrun) e modifiche fatte da altri dispositivi |
| WS | porta **8091** | ponte audio (processo `alice.bridge`): blocchi float32 mono a 48 kHz in entrambe le direzioni |

`scripts/alice_poc.py` (prova di fattibilità) parla direttamente con mod-host: mod-host accetta un
solo client, quindi funziona solo con il backend fermo.

## Licenza

GPLv3
