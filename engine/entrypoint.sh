#!/bin/sh
# Avvia JACK e mod-host. Driver audio:
#   dummy -> nessuna scheda audio (sviluppo su PC/WSL2, render offline)
#   alsa  -> scheda audio reale (Linux nativo, Raspberry Pi)
set -eu

case "$ALICE_AUDIO_DRIVER" in
  dummy)
    set -- -d dummy -r "$ALICE_SAMPLE_RATE" -p "$ALICE_BUFFER_SIZE" -C 2 -P 2
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

trap 'kill $HOST_PID $JACK_PID 2>/dev/null; wait' INT TERM
wait $HOST_PID
