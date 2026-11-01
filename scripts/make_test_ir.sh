#!/bin/sh
# Genera un IR di cassa approssimativo (impulso filtrato) per i test.
# Uso: make_test_ir.sh OUT.wav   (richiede sox; nel container è già presente)
set -eu
out=${1:-test-cab.wav}
sox -n -r 48000 -c 1 -b 24 -t wav - synth 1s square 1 trim 0 0.1 \
  | sox -t wav - -b 24 "$out" highpass 90 lowpass 4500 lowpass 6000 equalizer 120 1q +4 equalizer 2500 1.5q +5 gain -n -3
echo "$out"
