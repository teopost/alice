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
    {"id": "pitch", "name": "Pitch", "color": "#d94f9c"},
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
    {"id": "lspcomp", "name": "Studio Compressor", "category": "dynamics", "uri": L + "compressor_mono",
     "params": [{"symbol": "al", "label": "Threshold", "display": "db"}, {"symbol": "cr", "label": "Ratio"},
                {"symbol": "at", "label": "Attack"}, {"symbol": "rt", "label": "Release"},
                {"symbol": "mk", "label": "Makeup", "display": "db"}, {"symbol": "cdw", "label": "Mix"}]},
    {"id": "limiter", "name": "Limiter", "category": "dynamics", "uri": L + "limiter_mono",
     "params": [{"symbol": "th", "label": "Threshold", "display": "db"},
                {"symbol": "g_in", "label": "Input", "display": "db"}, {"symbol": "rt", "label": "Release"}]},
    {"id": "expander", "name": "Expander", "category": "dynamics", "uri": G + "gx_expander#_expander",
     "params": [{"symbol": "THRESHOLD", "label": "Threshold"}, {"symbol": "RATIO", "label": "Ratio"},
                {"symbol": "ATTACK", "label": "Attack"}, {"symbol": "RELEASE", "label": "Release"}]},
    # --- Wah
    {"id": "wah", "name": "Wah", "category": "wah", "uri": G + "gxautowah#wah",
     "params": [{"symbol": "fslider1_", "label": "Position", "display": "pct"}]},
    {"id": "crybaby", "name": "Cry Baby", "category": "wah", "uri": G + "gx_gcb_95_#_gcb_95_",
     "params": [{"symbol": "HOTPOTZ", "label": "Position", "display": "pct"}, {"symbol": "VOLUME", "label": "Level"}]},
    {"id": "colwah", "name": "Vintage Wah", "category": "wah", "uri": G + "gx_colwah_#_colwah_",
     "params": [{"symbol": "WAH", "label": "Position", "display": "pct"}, {"symbol": "MODEL", "label": "Model"},
                {"symbol": "MODE", "label": "Mode"}, {"symbol": "WET_DRY", "label": "Mix"}]},
    {"id": "autowah", "name": "Auto Wah", "category": "wah", "uri": G + "gxautowah#autowah", "params": []},
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
    {"id": "fuzzfm", "name": "Fuzz Face Fuller", "category": "drive", "uri": G + "gx_fuzzfacefm_#_fuzzfacefm_",
     "params": [{"symbol": "FUZZ", "label": "Fuzz", "display": "pct"}, {"symbol": "DRIVE", "label": "Drive", "display": "pct"},
                {"symbol": "INPUT", "label": "Input", "display": "pct"}, {"symbol": "LEVEL", "label": "Level", "display": "pct"}]},
    {"id": "fuzz", "name": "Fuzz", "category": "drive", "uri": G + "gx_fuzz_#fuzz_",
     "params": [{"symbol": "DRIVE", "label": "Drive"}, {"symbol": "TONE", "label": "Tone", "display": "pct"},
                {"symbol": "INPUT", "label": "Input"}, {"symbol": "OUTPUT", "label": "Level"}]},
    {"id": "fuzzmaster", "name": "Fuzz Master", "category": "drive", "uri": G + "gx_fumaster_#_fumaster_",
     "params": [{"symbol": "TONE", "label": "Tone", "display": "pct"}, {"symbol": "VOLUME", "label": "Volume", "display": "pct"},
                {"symbol": "WET_DRY", "label": "Mix"}]},
    {"id": "tonebender", "name": "Tone Bender", "category": "drive", "uri": G + "gx_cstb_#_cstb_",
     "params": [{"symbol": "ATTACK", "label": "Attack", "display": "pct"}, {"symbol": "LEVEL", "label": "Level", "display": "pct"},
                {"symbol": "WET_DRY", "label": "Mix"}]},
    {"id": "hornet", "name": "Hornet Fuzz", "category": "drive", "uri": G + "gx_hornet_#_hornet_",
     "params": [{"symbol": "FUZZ", "label": "Fuzz", "display": "pct"}, {"symbol": "SUSTAIN", "label": "Sustain", "display": "pct"},
                {"symbol": "VOLUME", "label": "Volume", "display": "pct"}]},
    {"id": "muff2", "name": "Muff Fuzz", "category": "drive", "uri": G + "gx_muff_#_muff_",
     "params": [{"symbol": "TONE", "label": "Tone", "display": "pct"}, {"symbol": "VOLUME", "label": "Volume", "display": "pct"}]},
    {"id": "hogsfoot", "name": "Hog's Foot", "category": "drive", "uri": G + "gx_hogsfoot_#_hogsfoot_",
     "params": [{"symbol": "VOLUME", "label": "Volume", "display": "pct"}, {"symbol": "WET_DRY", "label": "Mix"}]},
    {"id": "mxrdist", "name": "Distortion+", "category": "drive", "uri": G + "gx_mxrdist_#_mxrdist_",
     "params": [{"symbol": "DRIVE", "label": "Distortion", "display": "pct"}, {"symbol": "VOLUME", "label": "Output", "display": "pct"}]},
    {"id": "sustainer", "name": "Sustainer", "category": "drive", "uri": G + "gx_susta_#_susta_",
     "params": [{"symbol": "SUSTAIN", "label": "Sustain", "display": "pct"}, {"symbol": "VOLUME", "label": "Volume", "display": "pct"}]},
    {"id": "rangemaster", "name": "Treble Booster", "category": "drive", "uri": G + "gx_rangem_#_rangem_",
     "params": [{"symbol": "BOOST", "label": "Boost", "display": "pct"}, {"symbol": "WET_DRY", "label": "Mix"}]},
    {"id": "scream", "name": "Screaming Bird", "category": "drive", "uri": G + "gx_scream_#_scream_",
     "params": [{"symbol": "SCREAM", "label": "Scream", "display": "pct"}]},
    {"id": "mole", "name": "Bass Booster", "category": "drive", "uri": G + "gx_mole_#_mole_",
     "params": [{"symbol": "BOOST", "label": "Boost", "display": "pct"}, {"symbol": "WET_DRY", "label": "Mix"}]},
    # --- Amp
    {"id": "nam", "name": "NAM Amp", "category": "amp", "uri": NAM,
     "file": {"kind": "nam", "property": NAM + "#model", "label": "Modello NAM"},
     "params": [{"symbol": "input_level", "label": "Input"}, {"symbol": "output_level", "label": "Output"}]},
    {"id": "gxamp", "name": "Guitarix Amp", "category": "amp", "uri": G + "gx_amp#GUITARIX",
     "params": [{"symbol": "model", "label": "Tube"}, {"symbol": "t_model", "label": "Tonestack"},
                {"symbol": "PreGain", "label": "Pre Gain"}, {"symbol": "Drive", "label": "Drive"},
                {"symbol": "Distortion", "label": "Distortion"}, {"symbol": "Bass", "label": "Bass"},
                {"symbol": "Middle", "label": "Middle"}, {"symbol": "Treble", "label": "Treble"},
                {"symbol": "Presence", "label": "Presence"}, {"symbol": "MasterGain", "label": "Master"}]},
    {"id": "jcm800", "name": "JCM 800 Pre", "category": "amp", "uri": G + "gx_jcm800pre_#_jcm800pre_",
     "params": [{"symbol": "P6v", "label": "Pre Amp"}, {"symbol": "Bass", "label": "Bass"},
                {"symbol": "Middle", "label": "Middle"}, {"symbol": "Treble", "label": "Treble"},
                {"symbol": "WET_DRY", "label": "Presence"}, {"symbol": "GAIN", "label": "Master"}]},
    {"id": "metalhead", "name": "Metal Head", "category": "amp", "uri": G + "gxmetal_head#metal_head",
     "params": [{"symbol": "DRIVE", "label": "Drive", "display": "pct"}, {"symbol": "TONE", "label": "Tone", "display": "pct"},
                {"symbol": "PREGAIN", "label": "Pre Gain"}, {"symbol": "GAIN1", "label": "Master"}]},
    {"id": "chump", "name": "Chump", "category": "amp", "uri": G + "gx_redeye#chump",
     "params": [{"symbol": "Gain", "label": "Gain", "display": "pct"}, {"symbol": "Tone", "label": "Tone", "display": "pct"},
                {"symbol": "Volume", "label": "Volume", "display": "pct"}]},
    {"id": "bigchump", "name": "Big Chump", "category": "amp", "uri": G + "gx_redeye#bigchump",
     "params": [{"symbol": "Gain", "label": "Gain", "display": "pct"}, {"symbol": "Tone", "label": "Tone", "display": "pct"},
                {"symbol": "Volume", "label": "Volume", "display": "pct"}]},
    {"id": "vibrochump", "name": "Vibro Chump", "category": "amp", "uri": G + "gx_redeye#vibrochump",
     "params": [{"symbol": "Gain", "label": "Gain", "display": "pct"}, {"symbol": "Tone", "label": "Tone", "display": "pct"},
                {"symbol": "Volume", "label": "Volume", "display": "pct"}, {"symbol": "Speed", "label": "Speed"},
                {"symbol": "Intensity", "label": "Intensity"}]},
    {"id": "studiopre", "name": "Studio Preamp", "category": "amp", "uri": G + "gx_studiopre#studiopre",
     "params": [{"symbol": "volume", "label": "Gain", "display": "pct"}, {"symbol": "bass", "label": "Bass", "display": "pct"},
                {"symbol": "middle", "label": "Middle", "display": "pct"}, {"symbol": "treble", "label": "Treble", "display": "pct"},
                {"symbol": "master", "label": "Master", "display": "pct"}, {"symbol": "bright", "label": "Bright"}]},
    {"id": "alembic", "name": "Alembic Preamp", "category": "amp", "uri": G + "gx_alembic#alembic",
     "params": [{"symbol": "input", "label": "Input", "display": "pct"}, {"symbol": "bass", "label": "Bass", "display": "pct"},
                {"symbol": "middle", "label": "Middle", "display": "pct"}, {"symbol": "treble", "label": "Treble", "display": "pct"},
                {"symbol": "volume", "label": "Volume", "display": "pct"}]},
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
    {"id": "filter", "name": "Filter", "category": "eq", "uri": L + "filter_mono",
     "params": [{"symbol": "ft", "label": "Type"}, {"symbol": "f", "label": "Frequency"},
                {"symbol": "s", "label": "Slope"}, {"symbol": "q", "label": "Q"},
                {"symbol": "g", "label": "Gain", "display": "db"}]},
    {"id": "brightener", "name": "Brightener", "category": "eq", "uri": G + "gx_hfb_#_hfb_",
     "params": [{"symbol": "INTENSITY", "label": "Intensity", "display": "pct"}, {"symbol": "VOLUME", "label": "Volume", "display": "pct"}]},
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
    {"id": "gxchorus", "name": "Stereo Chorus", "category": "modulation", "uri": G + "gx_chorus_stereo#_chorus_stereo",
     "params": [{"symbol": "freq", "label": "Rate"}, {"symbol": "depth", "label": "Depth"},
                {"symbol": "delay", "label": "Delay"}, {"symbol": "level", "label": "Mix", "display": "pct"}]},
    {"id": "lspflanger", "name": "Studio Flanger", "category": "modulation", "uri": L + "flanger_mono",
     "params": [{"symbol": "rate", "label": "Rate"}, {"symbol": "depth", "label": "Depth"},
                {"symbol": "dmin", "label": "Min Depth"}, {"symbol": "fgain", "label": "Feedback"},
                {"symbol": "fb_on", "label": "Feedback On"}, {"symbol": "drywet", "label": "Mix"}]},
    {"id": "tubevibrato", "name": "Tube Vibrato", "category": "modulation", "uri": G + "gxtubevibrato#tubevibrato",
     "params": [{"symbol": "speed", "label": "Speed"}, {"symbol": "depth", "label": "Depth", "display": "pct"},
                {"symbol": "drive", "label": "Drive", "display": "pct"}, {"symbol": "output", "label": "Level", "display": "pct"}]},
    {"id": "tubetremolo", "name": "Tube Tremolo", "category": "modulation", "uri": G + "gxtubetremelo#tubetremelo",
     "params": [{"symbol": "speed", "label": "Speed"}, {"symbol": "depth", "label": "Depth", "display": "pct"},
                {"symbol": "drive", "label": "Drive", "display": "pct"}, {"symbol": "output", "label": "Level"}]},
    {"id": "swtremolo", "name": "Step Tremolo", "category": "modulation", "uri": G + "gx_switched_tremolo_#_switched_tremolo_",
     "params": [{"symbol": "DEPTH", "label": "Depth", "display": "pct"}, {"symbol": "SWITCHFREQ", "label": "Switch"},
                {"symbol": "STEPS", "label": "Steps"}, {"symbol": "WET_DRY", "label": "Mix"}]},
    {"id": "tape", "name": "Tape Wow", "category": "modulation", "uri": G + "gxtape#tape",
     "params": [{"symbol": "drive", "label": "Saturation", "display": "pct"}, {"symbol": "wowdepth", "label": "Wow"},
                {"symbol": "flutdepth", "label": "Flutter"}, {"symbol": "hiss", "label": "Hiss", "default": 0.05},
                {"symbol": "gain", "label": "Level", "display": "pct"}]},
    # --- Delay
    {"id": "tubedelay", "name": "Tube Delay", "category": "delay", "uri": G + "gxtubedelay#tubedelay",
     "params": [{"symbol": "delay", "label": "Time"}, {"symbol": "feedback", "label": "Feedback"},
                {"symbol": "level", "label": "Mix", "display": "pct"},
                {"symbol": "drive", "label": "Drive", "display": "pct"}, {"symbol": "output", "label": "Output"}]},
    {"id": "digidelay", "name": "Digital Delay", "category": "delay", "uri": G + "gx_digital_delay_#_digital_delay_",
     "params": [{"symbol": "BPM", "label": "BPM"}, {"symbol": "NOTES", "label": "Note"},
                {"symbol": "FEEDBACK", "label": "Feedback"}, {"symbol": "LEVEL", "label": "Mix"},
                {"symbol": "MODE", "label": "Mode"}, {"symbol": "HOWPASS", "label": "High Cut"}]},
    {"id": "echocat", "name": "Echo Cat", "category": "delay", "uri": G + "gxechocat#echocat",
     "params": [{"symbol": "bpm", "label": "BPM"}, {"symbol": "sustain", "label": "Sustain", "display": "pct"},
                {"symbol": "swell", "label": "Swell", "display": "pct"}, {"symbol": "head1", "label": "Head 1", "default": 1},
                {"symbol": "head2", "label": "Head 2"}, {"symbol": "head3", "label": "Head 3"},
                {"symbol": "input", "label": "Input", "display": "pct"}, {"symbol": "output", "label": "Output"}]},
    {"id": "echo", "name": "Echo", "category": "delay", "uri": G + "gx_echo_stereo#_echo_stereo",
     "params": [{"symbol": "timt_l", "label": "Time"}, {"symbol": "level_l", "label": "Level"},
                {"symbol": "lfo", "label": "LFO"}]},
    {"id": "duckdelay", "name": "Ducking Delay", "category": "delay", "uri": G + "gx_duck_delay_#_duck_delay_",
     "params": [{"symbol": "TIME", "label": "Time"}, {"symbol": "FEEDBACK", "label": "Feedback", "display": "pct"},
                {"symbol": "AMOUNT", "label": "Amount"}, {"symbol": "ATTACK", "label": "Attack"},
                {"symbol": "RELESE", "label": "Release"}]},
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
    {"id": "zita", "name": "Zita Rev1", "category": "reverb", "uri": G + "gx_zita_rev1_stereo#_zita_rev1_stereo",
     "params": [{"symbol": "MID_RT60", "label": "Decay"}, {"symbol": "LOW_RT60", "label": "Low Decay"},
                {"symbol": "HF_DAMPING", "label": "Damping"}, {"symbol": "IN_DELAY", "label": "Predelay"},
                {"symbol": "DRY_WET_MIX", "label": "Mix", "default": -0.5}, {"symbol": "level", "label": "Level"}]},
    {"id": "shimmer", "name": "Shimmer", "category": "reverb", "uri": G + "gx_shimmizita_#_shimmizita_",
     "params": [{"symbol": "T60M", "label": "Decay"}, {"symbol": "SHIFT", "label": "Shift"},
                {"symbol": "PSDRYWET", "label": "Shimmer", "display": "pct"}, {"symbol": "DEPTH", "label": "Depth", "display": "pct"},
                {"symbol": "SPEED", "label": "Speed"}, {"symbol": "DRYWET", "label": "Mix", "display": "pct"}]},
    {"id": "roomsim", "name": "Room Simulator", "category": "reverb", "uri": G + "gx_room_simulator_#_room_simulator_",
     "params": [{"symbol": "RT", "label": "Decay", "display": "pct"}, {"symbol": "ROOMSIZE", "label": "Size"},
                {"symbol": "PREDELAYMS", "label": "Predelay"}, {"symbol": "DRYWET", "label": "Mix", "display": "pct"}]},
    {"id": "gxreverb", "name": "Spring Verb", "category": "reverb", "uri": G + "gx_reverb_stereo#_reverb_stereo",
     "params": [{"symbol": "roomsize", "label": "Size", "display": "pct"}, {"symbol": "damp", "label": "Damp", "display": "pct"},
                {"symbol": "lfo", "label": "LFO"}, {"symbol": "dry_wet", "label": "Mix"}]},
    # --- Pitch
    {"id": "octaver", "name": "Octaver", "category": "pitch", "uri": G + "gx_oc_2_#_oc_2_",
     "params": [{"symbol": "OCTAVE1", "label": "Oct -1", "display": "pct"}, {"symbol": "OCTAVE2", "label": "Oct -2", "display": "pct"},
                {"symbol": "DIRECT", "label": "Dry", "display": "pct"}]},
    {"id": "detune", "name": "Detune", "category": "pitch", "uri": G + "gx_detune_#_detune_",
     "params": [{"symbol": "DETUNE", "label": "Semitones"}, {"symbol": "OCTAVE", "label": "Octave"},
                {"symbol": "WET", "label": "Wet"}, {"symbol": "DRY", "label": "Dry"}]},
]

# Descrizioni brevi mostrate nella libreria dei blocchi
DESCRIPTIONS = {
    "gate": "Elimina il fruscio quando non suoni",
    "comp": "Compressore classico per livellare la dinamica",
    "lspcomp": "Compressore da studio, trasparente e preciso",
    "limiter": "Tiene il segnale sotto una soglia, senza picchi",
    "expander": "Riduce rumore e coda tra una nota e l'altra",
    "wah": "Wah a pedale: muovi Position",
    "crybaby": "Il wah più famoso, voce aggressiva",
    "colwah": "Wah vintage con più modelli e modalità",
    "autowah": "Wah automatico che segue la dinamica",
    "ts9": "Overdrive medio e cremoso, spinge l'ampli",
    "ds1": "Distorsione arancione anni '80, tagliente",
    "rat": "Distorsione grintosa con filtro",
    "muff": "Fuzz denso con sustain infinito",
    "fuzzface": "Fuzz al germanio anni '60, morbido",
    "booster": "Booster pulito con bassi e alti",
    "fuzzfm": "Fuzz Face con controlli di drive e input",
    "fuzz": "Fuzz versatile con tono regolabile",
    "fuzzmaster": "Fuzz vintage spesso e saturo",
    "tonebender": "Fuzz britannico ruvido anni '60",
    "hornet": "Fuzz ronzante con sustain",
    "muff2": "Variante del Muff, più compatta",
    "hogsfoot": "Booster di bassi per un suono enorme",
    "mxrdist": "Distorsione semplice e diretta anni '70",
    "sustainer": "Compressore-fuzz per note lunghissime",
    "rangemaster": "Treble booster classico per ampli valvolari",
    "scream": "Booster di alti acuto e penetrante",
    "mole": "Booster di bassi per corpo e calore",
    "nam": "Ampli, pedale o rig catturato con Neural Amp Modeler",
    "gxamp": "Ampli completo con valvole e tonestack selezionabili",
    "jcm800": "Preamp britannico rock anni '80",
    "metalhead": "Testata ad alto guadagno per metal",
    "chump": "Piccolo combo valvolare con carattere",
    "bigchump": "Combo valvolare più grande e pieno",
    "vibrochump": "Combo valvolare con vibrato integrato",
    "studiopre": "Preamp pulito da studio con Bright",
    "alembic": "Preamp hi-fi pulito e brillante",
    "ir": "Cassa da file di risposta all'impulso (IR)",
    "gxcab": "Cassa simulata con modelli integrati",
    "geq": "Equalizzatore grafico a 11 bande",
    "tilt": "Bilancia scuro/brillante con un solo controllo",
    "filter": "Filtro passa-alto, passa-basso o a campana",
    "brightener": "Aggiunge brillantezza e definizione",
    "chorus": "Chorus da studio per suoni ampi",
    "flanger": "Flanger classico a getto",
    "phaser": "Phaser vintage ondeggiante",
    "tremolo": "Tremolo con forma d'onda selezionabile",
    "gxchorus": "Chorus stereo morbido",
    "lspflanger": "Flanger da studio con feedback",
    "tubevibrato": "Vibrato valvolare come negli ampli vintage",
    "tubetremolo": "Tremolo valvolare caldo",
    "swtremolo": "Tremolo a gradini ritmico",
    "tape": "Nastro con wow, flutter e saturazione",
    "tubedelay": "Delay valvolare caldo con drive",
    "digidelay": "Delay digitale a tempo (BPM)",
    "echocat": "Eco a nastro a tre testine",
    "echo": "Eco semplice con modulazione",
    "duckdelay": "Delay che si abbassa mentre suoni",
    "room": "Riverbero di stanza naturale",
    "plate": "Riverbero a piastra da studio",
    "hall": "Riverbero di sala ampio",
    "zita": "Riverbero di alta qualità, molto naturale",
    "shimmer": "Riverbero etereo con ottava sopra",
    "roomsim": "Simulatore di ambiente semplice",
    "gxreverb": "Riverbero a molla stile ampli",
    "octaver": "Aggiunge una e due ottave sotto",
    "detune": "Intonazione spostata per raddoppi e armonie",
}


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
        model["desc"] = DESCRIPTIONS.get(m["id"], "")
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

