#!/bin/sh
# Avvia JACK e mod-host. Driver audio:
#   dummy -> nessuna scheda audio (sviluppo su PC/WSL2, render offline)
#   alsa  -> scheda audio reale (Linux nativo, Raspberry Pi)
set -eu

case "$ALICE_AUDIO_DRIVER" in
  dummy)
    # -w: microsecondi tra un ciclo e l'altro; senza, il timer del driver dummy
    # gira più veloce del tempo reale (misurato +9% con buffer 128)
    WAIT_US=$(( ALICE_BUFFER_SIZE * 1000000 / ALICE_SAMPLE_RATE ))
    set -- -d dummy -r "$ALICE_SAMPLE_RATE" -p "$ALICE_BUFFER_SIZE" -w "$WAIT_US" -C 2 -P 2
    ;;
  alsa)
    set -- -R -d alsa -d "$ALICE_ALSA_DEVICE" -r "$ALICE_SAMPLE_RATE" \
           -p "$ALICE_BUFFER_SIZE" -n "$ALICE_PERIODS"
    ;;
  *)
    echo "ALICE_AUDIO_DRIVER non valido: $ALICE_AUDIO_DRIVER (dummy|alsa)" >&2
    exit 1
    ;;
esac

echo "[alice] avvio jackd ($ALICE_AUDIO_DRIVER, ${ALICE_SAMPLE_RATE} Hz, buffer $ALICE_BUFFER_SIZE)"
jackd --no-mlock "$@" &
JACK_PID=$!

# attende che JACK sia pronto
i=0
until jack_lsp >/dev/null 2>&1; do
  i=$((i + 1))
  [ "$i" -gt 50 ] && { echo "[alice] jackd non risponde" >&2; exit 1; }
  sleep 0.2
done

echo "[alice] avvio mod-host (porta $MOD_HOST_PORT, feedback $MOD_HOST_FEEDBACK_PORT)"
mod-host -n -p "$MOD_HOST_PORT" -f "$MOD_HOST_FEEDBACK_PORT" &
HOST_PID=$!

cd /opt/alice/backend
echo "[alice] avvio ponte audio col browser (porta $ALICE_BRIDGE_PORT)"
python3 -m alice.bridge &
BRIDGE_PID=$!
# l'Engine collega le porte del ponte alla catena: devono esistere prima
i=0
until jack_lsp 2>/dev/null | grep -q "^alice-bridge:src"; do
  i=$((i + 1))
  [ "$i" -gt 50 ] && { echo "[alice] il ponte audio non parte" >&2; break; }
  sleep 0.2
done

echo "[alice] avvio interfaccia web (porta $ALICE_HTTP_PORT)"
python3 -m uvicorn alice.app:app --host 0.0.0.0 --port "$ALICE_HTTP_PORT" &
WEB_PID=$!

PIDS="$WEB_PID $BRIDGE_PID $HOST_PID $JACK_PID"
trap 'kill $PIDS 2>/dev/null; wait' INT TERM
# se uno dei processi termina, esce: Docker riavvia il container
while kill -0 $JACK_PID && kill -0 $HOST_PID && kill -0 $BRIDGE_PID && kill -0 $WEB_PID; do sleep 1; done 2>/dev/null
echo "[alice] un processo è terminato, arresto" >&2
kill $PIDS 2>/dev/null
exit 1
