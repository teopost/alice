"""Catalogo dei blocchi disponibili.

Ogni modello è un plugin LV2 con una selezione di parametri (come i pochi knob
di un blocco Helix). Range, default ed enumerazioni vengono letti dai metadati
LV2 con lilv, così il catalogo resta corto.

Campi di un parametro: symbol, label, default e display opzionali:
  "db"  -> il valore LV2 è un guadagno lineare, mostrato in dB
  "pct" -> valore 0..1 mostrato in percentuale
"""
import logging

log = logging.getLogger("alice.catalog")

G = "http://guitarix.sourceforge.net/plugins/"
L = "http://lsp-plug.in/plugins/lv2/"
NAM = "http://github.com/mikeoliphant/neural-amp-modeler-lv2"

CATEGORIES = [
    {"id": "dynamics", "name": "Dynamics", "color": "#e8c33a"},
    {"id": "wah", "name": "Wah", "color": "#a35bd6"},
    {"id": "drive", "name": "Drive", "color": "#f0902a"},
    {"id": "amp", "name": "Amp", "color": "#e04040"},
    {"id": "cab", "name": "Cab / IR", "color": "#a33a3a"},
    {"id": "eq", "name": "EQ", "color": "#9aa0a6"},
    {"id": "modulation", "name": "Modulation", "color": "#3a8de0"},
    {"id": "delay", "name": "Delay", "color": "#3ac06a"},
    {"id": "reverb", "name": "Reverb", "color": "#e07a3a"},
]

FILE_KINDS = {
    "nam": {"dir": "models", "ext": [".nam"]},
    "ir": {"dir": "irs", "ext": [".wav"]},
    "di": {"dir": "di", "ext": [".wav"]},
}

MODELS = [
    # --- Dynamics
    {"id": "gate", "name": "Noise Gate", "category": "dynamics", "uri": L + "gate_mono",
     # soglia di default del plugin (-24 dB) troppo alta per una chitarra: chiude il segnale
     "params": [{"symbol": "gt", "label": "Threshold", "display": "db", "default": 0.00316},
                {"symbol": "gr", "label": "Reduction", "display": "db"},
                {"symbol": "at", "label": "Attack"},
                {"symbol": "rt", "label": "Release"}]},
    {"id": "comp", "name": "Compressor", "category": "dynamics", "uri": G + "gx_compressor#_compressor",
     "params": [{"symbol": "THRESHOLD", "label": "Threshold"}, {"symbol": "RATIO", "label": "Ratio"},
                {"symbol": "ATTACK", "label": "Attack"}, {"symbol": "RELEASE", "label": "Release"},
                {"symbol": "KNEE", "label": "Knee"}]},
    # --- Wah
    {"id": "wah", "name": "Wah", "category": "wah", "uri": G + "gxautowah#wah",
     "params": [{"symbol": "fslider1_", "label": "Position", "display": "pct"}]},
    # --- Drive
    {"id": "ts9", "name": "Tube Screamer", "category": "drive", "uri": G + "gxts9#ts9sim",
     "params": [{"symbol": "fslider2_", "label": "Drive", "display": "pct"},
                {"symbol": "fslider1_", "label": "Tone"}, {"symbol": "fslider0_", "label": "Level"}]},
    {"id": "ds1", "name": "DS-1 Distortion", "category": "drive", "uri": G + "gx_bossds1_#_bossds1_",
     "params": [{"symbol": "DRIVE", "label": "Dist", "display": "pct"},
                {"symbol": "TONE", "label": "Tone", "display": "pct"}, {"symbol": "LEVEL", "label": "Level"}]},
    {"id": "rat", "name": "Rat", "category": "drive", "uri": G + "gx_aclipper_#_aclipper_",
     "params": [{"symbol": "DRIVE", "label": "Distortion", "display": "pct"},
                {"symbol": "TONE", "label": "Filter", "display": "pct"}, {"symbol": "LEVEL", "label": "Level"}]},
    {"id": "muff", "name": "Big Muff", "category": "drive", "uri": G + "gx_bmp_#_bmp_",
     "params": [{"symbol": "SUSTAIN", "label": "Sustain", "display": "pct"},
                {"symbol": "TONE", "label": "Tone", "display": "pct"},
                {"symbol": "VOLUME", "label": "Volume", "display": "pct"}]},
    {"id": "fuzzface", "name": "Fuzz Face", "category": "drive", "uri": G + "gx_fuzzface_#_fuzzface_",
     "params": [{"symbol": "FUZZ", "label": "Fuzz", "display": "pct"},
                {"symbol": "LEVEL", "label": "Volume", "display": "pct"}]},
    {"id": "booster", "name": "Booster", "category": "drive", "uri": G + "gxbooster#booster",
     "params": [{"symbol": "fslider1_", "label": "Bass"}, {"symbol": "fslider0_", "label": "Treble"}]},
    # --- Amp
    {"id": "nam", "name": "NAM Amp", "category": "amp", "uri": NAM,
     "file": {"kind": "nam", "property": NAM + "#model", "label": "Modello NAM"},
     "params": [{"symbol": "input_level", "label": "Input"}, {"symbol": "output_level", "label": "Output"}]},
    # --- Cab
    {"id": "ir", "name": "IR Cab", "category": "cab", "uri": L + "impulse_responses_mono",
     "file": {"kind": "ir", "property": "http://lsp-plug.in//ports#ifn", "label": "File IR"},
     "params": [{"symbol": "g_out", "label": "Level", "display": "db"},
                {"symbol": "lcm", "label": "Low Cut"}, {"symbol": "lcf", "label": "Low Freq"},
                {"symbol": "hcm", "label": "High Cut"}, {"symbol": "hcf", "label": "High Freq"},
                {"symbol": "drywet", "label": "Mix"}]},
    {"id": "gxcab", "name": "Cab Sim", "category": "cab", "uri": G + "gx_cabinet#CABINET",
     "params": [{"symbol": "c_model", "label": "Model"}, {"symbol": "CBass", "label": "Bass"},
                {"symbol": "CTreble", "label": "Treble"}, {"symbol": "CLevel", "label": "Level"}]},
    # --- EQ
    {"id": "geq", "name": "Graphic EQ", "category": "eq", "uri": G + "gx_graphiceq_#_graphiceq_",
     "params": [{"symbol": f"G{i}", "label": f"Band {i}"} for i in range(1, 12)]},
    {"id": "tilt", "name": "Tilt Tone", "category": "eq", "uri": G + "gxtilttone#tilttone",
     "params": [{"symbol": "tone", "label": "Tilt", "display": "pct"},
                {"symbol": "body", "label": "Body", "display": "pct"},
                {"symbol": "drive", "label": "Drive", "display": "pct"},
                {"symbol": "level", "label": "Level", "display": "pct"}]},
    # --- Modulation
    {"id": "chorus", "name": "Chorus", "category": "modulation", "uri": L + "chorus_mono",
     "params": [{"symbol": "rate", "label": "Rate"}, {"symbol": "depth", "label": "Depth"},
                {"symbol": "voices", "label": "Voices"}, {"symbol": "drywet", "label": "Mix"}]},
    {"id": "flanger", "name": "Flanger", "category": "modulation", "uri": G + "gx_flanger#_flanger",
     "params": [{"symbol": "freq", "label": "Rate"}, {"symbol": "depth", "label": "Depth"},
                {"symbol": "feedback", "label": "Feedback"}, {"symbol": "dry_wet", "label": "Mix"}]},
    {"id": "phaser", "name": "Phaser", "category": "modulation", "uri": G + "gx_phaser#_phaser",
     "params": [{"symbol": "speed", "label": "Speed"}, {"symbol": "dry_wet", "label": "Mix"},
                {"symbol": "level", "label": "Level"}]},
    {"id": "tremolo", "name": "Tremolo", "category": "modulation", "uri": G + "gx_tremolo#_tremolo",
     "params": [{"symbol": "freq", "label": "Speed"}, {"symbol": "depth", "label": "Depth", "display": "pct"},
                {"symbol": "mode", "label": "Wave"}, {"symbol": "dry_wet", "label": "Mix"}]},
    # --- Delay
    {"id": "tubedelay", "name": "Tube Delay", "category": "delay", "uri": G + "gxtubedelay#tubedelay",
     "params": [{"symbol": "delay", "label": "Time"}, {"symbol": "feedback", "label": "Feedback"},
                {"symbol": "level", "label": "Mix", "display": "pct"},
                {"symbol": "drive", "label": "Drive", "display": "pct"}, {"symbol": "output", "label": "Output"}]},
    {"id": "digidelay", "name": "Digital Delay", "category": "delay", "uri": G + "gx_digital_delay_#_digital_delay_",
     "params": [{"symbol": "BPM", "label": "BPM"}, {"symbol": "NOTES", "label": "Note"},
                {"symbol": "FEEDBACK", "label": "Feedback"}, {"symbol": "LEVEL", "label": "Mix"},
                {"symbol": "MODE", "label": "Mode"}, {"symbol": "HOWPASS", "label": "High Cut"}]},
    # --- Reverb
    {"id": "room", "name": "Room", "category": "reverb", "uri": "urn:dragonfly:room",
     "params": [{"symbol": "decay", "label": "Decay"}, {"symbol": "size", "label": "Size"},
                {"symbol": "predelay", "label": "Predelay"}, {"symbol": "late_level", "label": "Late"},
                {"symbol": "early_level", "label": "Early"}, {"symbol": "dry_level", "label": "Dry"}]},
    {"id": "plate", "name": "Plate", "category": "reverb", "uri": "urn:dragonfly:plate",
     "params": [{"symbol": "decay", "label": "Decay"}, {"symbol": "predelay", "label": "Predelay"},
                {"symbol": "early_level", "label": "Wet"}, {"symbol": "dry_level", "label": "Dry"},
                {"symbol": "algorithm", "label": "Type"}]},
    {"id": "hall", "name": "Hall", "category": "reverb", "uri": "https://github.com/michaelwillis/dragonfly-reverb",
     "params": [{"symbol": "decay", "label": "Decay"}, {"symbol": "size", "label": "Size"},
                {"symbol": "delay", "label": "Predelay"}, {"symbol": "late_level", "label": "Late"},
                {"symbol": "early_level", "label": "Early"}, {"symbol": "dry_level", "label": "Dry"}]},
]


def _num(node):
    if node is None:
        return None
    try:
        return float(str(node))
    except ValueError:
        return None


def load_catalog():
    """Completa i modelli con porte audio e range dei parametri letti da lilv."""
    import lilv

    world = lilv.World()
    world.load_all()
    plugins = world.get_all_plugins()
    audio = world.new_uri(lilv.LILV_URI_AUDIO_PORT)
    control = world.new_uri(lilv.LILV_URI_CONTROL_PORT)
    inp = world.new_uri(lilv.LILV_URI_INPUT_PORT)
    lv2 = "http://lv2plug.in/ns/lv2core#"
    props = {k: world.new_uri(lv2 + k) for k in ("toggled", "enumeration", "integer")}
    props["log"] = world.new_uri("http://lv2plug.in/ns/ext/port-props#logarithmic")

    models = []
    for m in MODELS:
        p = plugins.get_by_uri(world.new_uri(m["uri"]))
        if p is None:
            log.warning("plugin non trovato, blocco '%s' escluso: %s", m["id"], m["uri"])
            continue
        ports = [p.get_port_by_index(i) for i in range(p.get_num_ports())]
        model = dict(m)
        model["inputs"] = [str(q.get_symbol()) for q in ports if q.is_a(audio) and q.is_a(inp)]
        model["outputs"] = [str(q.get_symbol()) for q in ports if q.is_a(audio) and not q.is_a(inp)]
        by_symbol = {str(q.get_symbol()): q for q in ports if q.is_a(control) and q.is_a(inp)}
        params = []
        for spec in m["params"]:
            q = by_symbol.get(spec["symbol"])
            if q is None:
                log.warning("%s: parametro %s non trovato", m["id"], spec["symbol"])
                continue
            d, mn, mx = (_num(x) for x in q.get_range())
            if "default" in spec:  # default di Alice al posto di quello del plugin
                d = float(spec["default"])
            par = {"symbol": spec["symbol"], "label": spec.get("label") or str(q.get_name()),
                   "min": mn, "max": mx, "default": d, "display": spec.get("display")}
            for k, uri in props.items():
                par[k] = bool(q.has_property(uri))
            if par["display"] == "db" and (mn is None or mn <= 0):
                par["min_db"] = -60.0  # 0 lineare = -inf dB: limita la manopola
            sps = q.get_scale_points()
            if sps is not None:
                options = sorted(({"value": _num(s.get_value()), "label": str(s.get_label())} for s in sps),
                                 key=lambda o: o["value"])
                if options:
                    par["options"] = options
            params.append(par)
        model["params"] = params
        models.append(model)
    log.info("catalogo: %d modelli", len(models))
    return {"categories": CATEGORIES, "models": models}

