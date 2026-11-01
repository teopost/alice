// AudioWorklet del ponte audio.
// - cattura un canale dell'ingresso e lo invia al thread principale (che lo manda al server)
// - riproduce l'audio elaborato ricevuto dal server, con un buffer anti-scatti adattivo

class AliceBridge extends AudioWorkletProcessor {
  constructor() {
    super();
    this.channel = 0;
    this.gain = 1;                // guadagno d'ingresso (lineare)
    this.sendBuf = new Float32Array(256);
    this.sendN = 0;
    this.target = 512;            // campioni da accumulare prima di riprodurre
    this.ring = new Float32Array(48000 * 2);
    this.r = 0;                   // contatori assoluti
    this.w = 0;
    this.playing = false;
    this.underruns = 0;
    this.inPeak = 0;
    this.outPeak = 0;
    this.statsCounter = 0;
    this.port.onmessage = (e) => {
      const m = e.data;
      if (m instanceof Float32Array) return this.push(m);
      if (m.type === "config") {
        if (m.channel !== undefined) this.channel = m.channel;
        if (m.target !== undefined) this.target = m.target;
        if (m.gain !== undefined) this.gain = m.gain;
      }
    };
  }

  fill() {
    return this.w - this.r;
  }

  push(data) {
    const size = this.ring.length;
    for (let i = 0; i < data.length; i++) this.ring[(this.w + i) % size] = data[i];
    this.w += data.length;
    if (this.fill() > size) this.r = this.w - size;
    // troppa latenza accumulata (es. dopo un rallentamento): torna al livello obiettivo
    if (this.fill() > this.target * 2 + 1024) this.r = this.w - this.target;
  }

  process(inputs, outputs) {
    // --- cattura
    const input = inputs[0];
    if (input && input.length) {
      const ch = input[Math.min(this.channel, input.length - 1)];
      // accumula 2 quanti (256 campioni, ~5 ms) per messaggio: meno carico sul server
      for (let i = 0; i < ch.length; i++) {
        const v = ch[i] * this.gain;
        const a = Math.abs(v);
        if (a > this.inPeak) this.inPeak = a;
        this.sendBuf[this.sendN++] = v;
        if (this.sendN === this.sendBuf.length) {
          this.port.postMessage(this.sendBuf, [this.sendBuf.buffer]);
          this.sendBuf = new Float32Array(256);
          this.sendN = 0;
        }
      }
    }

    // --- riproduzione
    const out = outputs[0];
    const n = out[0].length;
    if (!this.playing && this.fill() >= this.target) this.playing = true;
    if (this.playing && this.fill() < n) {
      this.playing = false;
      this.underruns++;
    }
    const left = out[0];
    if (this.playing) {
      const size = this.ring.length;
      for (let i = 0; i < n; i++) {
        const v = this.ring[(this.r + i) % size];
        left[i] = v;
        const a = Math.abs(v);
        if (a > this.outPeak) this.outPeak = a;
      }
      this.r += n;
    } else {
      left.fill(0);
    }
    for (let c = 1; c < out.length; c++) out[c].set(left);

    // --- statistiche ~10 volte al secondo
    if (++this.statsCounter >= 37) {
      this.statsCounter = 0;
      this.port.postMessage({ type: "stats", inPeak: this.inPeak, outPeak: this.outPeak,
                              fill: this.fill(), underruns: this.underruns });
      this.inPeak = 0;
      this.outPeak = 0;
    }
    return true;
  }
}

registerProcessor("alice-bridge", AliceBridge);
