# Alice engine: JACK + mod-host (LV2 host) + NAM LV2 + LV2 effects
# Multi-arch: amd64 (sviluppo/PC) e arm64 (Raspberry Pi 5)

FROM debian:trixie-slim AS build

ARG MOD_HOST_REF=master
ARG NAM_LV2_REF=main

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential cmake git pkg-config ca-certificates python3 \
        libjack-jackd2-dev liblilv-dev lv2-dev libreadline-dev libfftw3-dev \
    && rm -rf /var/lib/apt/lists/*

# mod-host: host LV2 controllabile via socket
RUN git clone --depth 1 --branch ${MOD_HOST_REF} https://github.com/moddevices/mod-host.git /src/mod-host \
    && make -C /src/mod-host -j"$(nproc)" \
    && make -C /src/mod-host install DESTDIR=/out PREFIX=/usr

# Neural Amp Modeler LV2
RUN git clone --depth 1 --recursive --shallow-submodules --branch ${NAM_LV2_REF} \
        https://github.com/mikeoliphant/neural-amp-modeler-lv2.git /src/nam-lv2 \
    && cmake -S /src/nam-lv2 -B /src/nam-lv2/build -DCMAKE_BUILD_TYPE=Release -DUSE_NATIVE_ARCH=OFF \
    && cmake --build /src/nam-lv2/build -j"$(nproc)" \
    && mkdir -p /out/usr/lib/lv2 \
    && cp -r "$(find /src/nam-lv2/build -type d -name 'neural_amp_modeler.lv2' | head -1)" /out/usr/lib/lv2/

FROM debian:trixie-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        jackd2 jack-example-tools libjack-jackd2-0 liblilv-0-0 libreadline8t64 libfftw3-single3 libfftw3-double3 \
        lilv-utils lsp-plugins-lv2 \
        python3 python3-jack-client python3-soundfile python3-numpy \
        sox procps netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

COPY --from=build /out/ /

COPY entrypoint.sh /usr/local/bin/alice-engine
RUN chmod +x /usr/local/bin/alice-engine

ENV LV2_PATH=/usr/lib/lv2 \
    ALICE_AUDIO_DRIVER=dummy \
    ALICE_ALSA_DEVICE=hw:0 \
    ALICE_SAMPLE_RATE=48000 \
    ALICE_BUFFER_SIZE=128 \
    ALICE_PERIODS=2 \
    MOD_HOST_PORT=5555 \
    MOD_HOST_FEEDBACK_PORT=5556

VOLUME ["/data"]
EXPOSE 5555 5556

ENTRYPOINT ["/usr/local/bin/alice-engine"]
