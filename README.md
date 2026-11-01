# Alice

Modeler per chitarra open source, controllato via web, pensato per pedaliere fatte in casa
(Raspberry Pi 5, mini-PC x86). Usa profili [NAM](https://github.com/sdatkinson/neural-amp-modeler)
e plugin LV2, con un'interfaccia a blocchi ispirata a Line 6 Helix.

> Stato: **prova di fattibilità**. Per ora esiste solo il motore audio (JACK + mod-host + NAM LV2),
> comandato da script. L'interfaccia web non c'è ancora.

## Architettura

- **engine**: container con JACK, [mod-host](https://github.com/moddevices/mod-host),
  [NAM LV2](https://github.com/mikeoliphant/neural-amp-modeler-lv2) e LSP plugins.
  mod-host si comanda via socket TCP (porta 5555, feedback 5556).
- **backend + UI web** stile Helix: da fare.

## Prova rapida (anche su PC/WSL2, senza scheda audio)

```sh
docker compose up -d --build
python3 scripts/make_test_nam.py data/models          # modelli NAM di test (pesi casuali)
docker exec alice-engine sox -n -r 48000 -c 1 -b 24 /data/di/test.wav synth 8 pluck E2
docker exec alice-engine python3 /opt/alice/scripts/alice_poc.py \
    --model /data/models/test-standard.nam --di /data/di/test.wav --out /data/renders/out.wav
```

Su Linux nativo / Raspberry Pi con scheda audio reale:

```sh
docker compose -f docker-compose.yml -f docker-compose.hw.yml up -d
```

## Licenza

GPLv3
