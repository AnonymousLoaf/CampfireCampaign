"""Spoken narration with Kokoro (free, runs on the host PC; on its NVIDIA GPU when CUDA is available).

After each DM narration the text is split into narrator lines and quoted dialogue, each quote is attributed to
whoever is named next to it ("…," Vane says), and every speaker gets a stable voice recipe: a blend of two
Kokoro voices, a speed and a pitch. Ancestry nudges the recipe (dwarves deeper, halflings higher). The result is
one MP3 per narration, made once on the server and shared by everyone at the table.

Optional: without the model files (game/server/data/tts) or the kokoro_onnx package, nothing happens and
browsers fall back to their own built-in voices.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import threading

import numpy as np

from ..config import DATA_DIR

log = logging.getLogger(__name__)

TTS_DIR = DATA_DIR / "tts"
AUDIO_DIR = DATA_DIR / "voice"
MODEL = "kokoro-v1.0.fp16.onnx"
VOICES = "voices-v1.0.bin"
SR = 24000

NARRATOR = {"mix": [["bm_george", 1.0]], "speed": 1.0, "pitch": 0.0}
STRANGER = {"mix": [["am_onyx", 0.7], ["bm_lewis", 0.3]], "speed": 0.98, "pitch": -0.5}
FEMALE = ["af_heart", "af_bella", "af_nicole", "af_sarah", "af_sky", "af_nova", "af_river", "af_aoede", "af_kore",
          "af_jessica", "bf_emma", "bf_isabella", "bf_alice", "bf_lily"]
MALE = ["am_adam", "am_michael", "am_fenrir", "am_eric", "am_liam", "am_onyx", "am_echo", "am_puck",
        "bm_george", "bm_lewis", "bm_daniel", "bm_fable"]
# words in a character's description → a pitch nudge in semitones, and a speed nudge
# Creatures sound like what they are: (words, voices to draw from, pitch in semitones, speed, texture effect).
# The first that matches wins; the pitch and speed replace the random ones (with a little variation kept).
CREATURES = [
    (r"\b(dragons?|wyrms?|wyverns?|drakes?)\b", ["am_onyx", "bm_george", "am_fenrir", "bm_lewis"], -5.0, 0.82, "boom"),
    (r"\b(giants?|ogres?|trolls?|ettins?|golems?|titans?|treants?|ents?)\b", ["am_onyx", "am_fenrir", "bm_lewis"], -4.0, 0.84, None),
    (r"\b(demons?|devils?|fiends?|balors?|pit fiend)\b", ["am_onyx", "bm_lewis", "am_fenrir"], -4.5, 0.86, "rasp"),
    (r"\b(orcs?|orks?|half-orcs?|bugbears?|hobgoblins?|gnolls?|minotaurs?|worgs?)\b", ["am_fenrir", "am_onyx", "bm_lewis", "am_eric"], -2.5, 0.94, "rasp"),
    (r"\b(liches?|wraiths?|ghosts?|spectres?|specters?|skeletons?|zombies?|vampires?|banshees?|undead|revenants?)\b",
     ["bm_lewis", "am_echo", "bf_isabella", "bm_daniel"], -2.0, 0.85, "hollow"),
    (r"\b(goblins?|kobolds?|imps?|gremlins?|quasits?|mephits?|boggles?)\b", ["am_puck", "af_sky", "am_echo", "af_nicole"], 4.0, 1.12, "rasp"),
    (r"\b(pixies?|sprites?|fair(?:y|ies)|faeries?|fae|will-o'?-wisps?)\b", ["af_sky", "af_nicole", "af_aoede", "af_jessica"], 5.0, 1.12, None),
]
FLAVOUR = [(r"\b(dwarf|dwarven|goliath|giant|ogre|orc|half-orc|minotaur|troll|bear|worg)\b", -3.0, -0.04),
           (r"\b(old|elder|ancient|crone|aged|grandmother|grandfather)\b", -1.0, -0.1),
           (r"\b(halfling|gnome|gnomish|kobold|goblin|pixie|sprite|child|boy|girl|kid)\b", 3.0, 0.06),
           (r"\b(nervous|frantic|excited|scared)\b", 0.5, 0.08)]
TITLES = {"the", "captain", "magister", "high", "prelate", "lord", "lady", "sir", "dame", "master", "mistress",
          "brother", "sister", "father", "mother", "old", "young", "king", "queen", "prince", "princess"}

_engine = None
_engine_lock = threading.Lock()
_engine_failed = False


def available() -> bool:
    if _engine_failed or not (TTS_DIR / MODEL).exists() or not (TTS_DIR / VOICES).exists():
        return False
    try:
        import kokoro_onnx  # noqa: F401
    except ImportError:
        return False
    return True


def _get_engine():
    """Kokoro on the GPU when CUDA works, else the CPU (loaded once, on first use)."""
    global _engine, _engine_failed
    if _engine is not None:
        return _engine
    import onnxruntime as ort
    from kokoro_onnx import Kokoro
    providers = ["CPUExecutionProvider"]
    try:
        if hasattr(ort, "preload_dlls"):
            ort.preload_dlls()  # CUDA/cuDNN from the nvidia-* pip packages
        if "CUDAExecutionProvider" in ort.get_available_providers():
            providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
    except Exception:  # noqa: BLE001
        pass
    try:
        sess = ort.InferenceSession(str(TTS_DIR / MODEL), providers=providers)
    except Exception:  # noqa: BLE001 — a GPU that won't take it: the CPU always works
        sess = ort.InferenceSession(str(TTS_DIR / MODEL), providers=["CPUExecutionProvider"])
    _engine = Kokoro.from_session(sess, str(TTS_DIR / VOICES))
    log.info("kokoro voices ready on %s", sess.get_providers()[0])
    return _engine


# ── who speaks ───────────────────────────────────────────────────────────────

def _clean(text: str) -> str:
    t = re.sub(r"[*_#>`]", "", text or "")
    return t.replace("“", '"').replace("”", '"')


def name_index(names: list[str]) -> dict[str, str]:
    """token → full name for every speaker we know ("vane" → "Captain Ilsa Vane"); full names match too."""
    idx: dict[str, str] = {}
    for full in names:
        full = (full or "").strip()
        if not full:
            continue
        idx[full.lower()] = full
        for tok in re.findall(r"[A-Za-z][A-Za-z'\-]+", full):
            if len(tok) >= 3 and tok.lower() not in TITLES:
                idx.setdefault(tok.lower(), full)
    return idx


def _find_name(text: str, idx: dict[str, str], last: bool) -> str | None:
    hits = []
    for key, full in idx.items():
        for m in re.finditer(r"\b" + re.escape(key) + r"\b", text, re.I):
            hits.append((m.start(), -len(key), full))
    if not hits:
        return None
    hits.sort()
    return hits[-1][2] if last else hits[0][2]


FEMALE_WORDS = (
    "she her hers herself woman women lady ladies queen princess duchess baroness countess empress mother mom mum "
    "sister daughter girl wife widow bride aunt niece grandmother granny matron dame madam madame mistress maiden "
    "maid nun abbess priestess stewardess waitress hostess actress heiress sorceress enchantress witch hag crone "
    "goddess huntress seamstress governess lass fishwife alewife barmaid milkmaid matriarch"
).split()
MALE_WORDS = (
    "he him his himself man men lord king prince duke baron count earl emperor father dad son brother boy husband "
    "widower groom uncle nephew grandfather grandpa sir mister master monk abbot friar priest steward waiter host "
    "actor heir sorcerer enchanter wizard warlock god huntsman lad fisherman alderman nobleman gentleman squire "
    "knight patriarch bishop innkeeper's"
).split()
_F = re.compile(r"\b(" + "|".join(map(re.escape, FEMALE_WORDS)) + r")\b")
_M = re.compile(r"\b(" + "|".join(map(re.escape, MALE_WORDS)) + r")\b")
SPEECH = (r"(?:says|said|asks|asked|whispers|whispered|shouts|shouted|calls|called|mutters|muttered|replies|"
          r"rumbles|rumbled|roars|roared|snarls|snarled|screeches|screeched|cackles|cackled|grunts|grunted|"
          r"shrieks|shrieked|moans|moaned|intones|intoned|booms|boomed|giggles|giggled|chuckles|chuckled|"
          r"sneers|sneered|sighs|sighed|gasps|gasped|drawls|drawled|spits|spat|wheezes|wheezed|squeaks|squeaked|"
          r"replied|snaps|snapped|growls|growled|hisses|hissed|answers|answered|adds|added|laughs|laughed|sobs|"
          r"sobbed|murmurs|murmured|barks|barked|cries|cried|yells|yelled|croaks|croaked|purrs|purred|rasps|rasped)")


def _gender(about: str) -> str | None:
    """'she', 'he' or None from the words used about someone (pronouns and gendered roles: steward/stewardess)."""
    a = about.lower()
    she, he = len(_F.findall(a)), len(_M.findall(a))
    return "she" if she > he else "he" if he > she else None


def role_speaker(text: str) -> str | None:
    """An unnamed speaker by role: '…," the steward says' / 'the old woman whispers' → 'the steward'."""
    t = text.lower()
    m = re.search(r"\b(?:the|a|an)\s+((?:[a-z'\-]+\s+){0,2}[a-z'\-]+)\s+" + SPEECH + r"\b", t) or \
        re.search(SPEECH + r"\s+(?:the|a|an)\s+((?:[a-z'\-]+\s+){0,2}[a-z'\-]+)", t)
    if not m:
        return None
    role = re.sub(r"\b(softly|quietly|loudly|again|then|now|finally)\b", "", m.group(1)).strip()
    return f"the {role}" if role and role not in ("voice", "one", "other", "same") else None


def _by_pronoun(earlier: str, pronoun: str, idx: dict[str, str], about: dict[str, str]) -> str | None:
    """'…,' she says: the most recently named person in the paragraph that the pronoun fits."""
    seen: list[tuple[int, str]] = []
    for key, full in idx.items():
        for m in re.finditer(r"\b" + re.escape(key) + r"\b", earlier, re.I):
            seen.append((m.start(), full))
    seen.sort()
    fits = [f for _, f in seen if _gender(about.get(f, "")) == pronoun]
    if fits:
        return fits[-1]
    unknown = [f for _, f in seen if _gender(about.get(f, "")) is None]
    return unknown[-1] if unknown else None


def segments(text: str, names: list[str], about: dict[str, str] | None = None) -> list[tuple[str, str | None]]:
    """[(text, speaker or None for the narrator)] in reading order."""
    about = about or {}
    idx = name_index(names)
    out: list[tuple[str, str | None]] = []
    for para in [p for p in re.split(r"\n\s*\n", _clean(text)) if p.strip()]:
        pos = 0
        last_speaker: str | None = None
        for m in re.finditer(r'"([^"]{2,})"', para):
            before = para[pos:m.start()]
            if before.strip():
                out.append((before.strip(), None))
            # attribution: the clause after the quote first ('…," Vane says'), then the one before it
            after = re.split(r"(?<=[.!?])\s", para[m.end():m.end() + 90], maxsplit=1)[0]
            pieces = [p for p in re.split(r"(?<=[.!?])\s", para[max(0, m.start() - 160):m.start()]) if p.strip()]
            lead = pieces[-1] if pieces else ""
            # '…," Vane says' names the speaker; in the sentence before a quote, whoever acts first speaks
            # ("Vane walks backward to grin at Teft. 'Stay close…'")
            who = _find_name(after, idx, last=False) or role_speaker(after) or _find_name(lead, idx, last=False)
            if not who and last_speaker and len(before.strip()) < 40:
                who = last_speaker  # a second quote straight after the first: the same person goes on
            pron = re.search(r"\b(he|she)\b", after, re.I)
            if not who and pron:
                who = _by_pronoun(para[:m.start()], pron.group(1).lower(), idx, about) or last_speaker
            if not who:
                who = role_speaker(lead)
            speaker = who or "?"
            last_speaker = who or last_speaker
            out.append((m.group(1).strip(), speaker))
            pos = m.end()
        rest = para[pos:]
        if rest.strip():
            out.append((rest.strip(), None))
    merged: list[tuple[str, str | None]] = []
    for t, s in out:
        if merged and merged[-1][1] == s:
            merged[-1] = (merged[-1][0] + " " + t, s)
        else:
            merged.append((t, s))
    return [(t, s) for t, s in merged if re.search(r"[A-Za-z0-9]", t)]


# ── voice recipes ────────────────────────────────────────────────────────────

def recipe_for(name: str, about: str = "") -> dict:
    """A stable voice for a speaker: a blend of two voices of the likely gender, plus speed and pitch."""
    h = int(hashlib.sha1(name.lower().encode()).hexdigest(), 16)
    a = about.lower()
    g = _gender(f"{name} {about}")
    pool = FEMALE if g == "she" else MALE if g == "he" else (FEMALE if h % 2 else MALE)
    v1 = pool[h % len(pool)]
    v2 = pool[(h >> 8) % len(pool)]
    if v2 == v1:
        v2 = pool[(h >> 8 + 1) % len(pool)]
    w = 0.6 + ((h >> 16) % 30) / 100  # 0.60–0.89 of the first voice
    speed = 0.9 + ((h >> 24) % 22) / 100  # 0.90–1.11
    pitch = ((h >> 32) % 41) / 10 - 2.0  # −2.0…+2.0 semitones
    creature = next((c for c in CREATURES if re.search(c[0], f"{name} {a}".lower())), None)
    if creature:
        _, cpool, cpitch, cspeed, fx = creature
        v1, v2 = cpool[h % len(cpool)], cpool[(h >> 8) % len(cpool)]
        if v2 == v1:
            v2 = cpool[(h % len(cpool) + 1) % len(cpool)]
        pitch = cpitch + (pitch / 4)  # mostly the creature's pitch, a touch of the individual
        speed = cspeed + (speed - 1) / 3
        r = {"mix": [[v1, round(w, 2)], [v2, round(1 - w, 2)]], "speed": round(max(0.7, min(1.3, speed)), 2),
             "pitch": round(max(-6.0, min(6.0, pitch)), 1)}
        if fx:
            r["fx"] = fx
        return r
    for pat, dp, ds in FLAVOUR:
        if re.search(pat, a):
            pitch += dp
            speed += ds
    return {"mix": [[v1, round(w, 2)], [v2, round(1 - w, 2)]], "speed": round(max(0.75, min(1.3, speed)), 2),
            "pitch": round(max(-5.0, min(5.0, pitch)), 1)}


def _style(k, mix: list) -> np.ndarray:
    total = sum(w for _, w in mix) or 1.0
    return sum(k.get_voice_style(v) * (w / total) for v, w in mix)


def _shift(samples: np.ndarray, factor: float) -> np.ndarray:
    """Resample so the audio plays `factor` times faster: pitch rises by that factor, length shrinks by it."""
    if abs(factor - 1) < 1e-3 or len(samples) < 2:
        return samples
    n = max(1, int(len(samples) / factor))
    x = np.linspace(0, len(samples) - 1, n)
    return np.interp(x, np.arange(len(samples)), samples).astype(np.float32)


def texture(samples: np.ndarray, fx: str | None) -> np.ndarray:
    """A voice's grain, added after speech is made: rasp (an orc's gravel, a goblin's screech), boom (a dragon's
    weight) or hollow (an undead echo)."""
    if not fx or len(samples) < 64:
        return samples
    x = samples.astype(np.float32)
    peak = float(np.max(np.abs(x))) or 1.0
    if fx == "rasp":
        # soft saturation for grit, plus a fast flutter in loudness (vocal fry)
        drive = np.tanh(x / peak * 4.0) * peak
        t = np.arange(len(x)) / SR
        flutter = 1.0 - 0.18 * (0.5 + 0.5 * np.sin(2 * np.pi * 38 * t))
        rng = np.random.default_rng(len(x))
        grit = rng.normal(0, 0.012, len(x)).astype(np.float32) * np.abs(x) / peak
        out = (0.55 * x + 0.45 * drive) * flutter + grit
    elif fx == "boom":
        # weight: a little drive and a low, slow rumble under the voice
        drive = np.tanh(x / peak * 2.0) * peak
        k_ = int(SR * 0.0025)
        body = np.convolve(drive, np.ones(k_) / k_, mode="same")  # the low end, boosted
        out = 0.6 * drive + 0.7 * body
    elif fx == "hollow":
        # a short, dim echo: the voice from inside a tomb
        out = x.copy()
        for delay, gain in ((0.045, 0.45), (0.11, 0.3), (0.19, 0.18)):
            d = int(SR * delay)
            out[d:] += gain * x[:-d]
    else:
        return samples
    return (out / (float(np.max(np.abs(out))) or 1.0) * peak).astype(np.float32)


def speak(k, text: str, recipe: dict) -> np.ndarray:
    """Kokoro speech for one line in a recipe. Pitch without changing speed: synthesise slower by the pitch
    factor, then resample back up; then the recipe's texture, if any."""
    f = 2 ** (float(recipe.get("pitch", 0)) / 12)
    speed = float(recipe.get("speed", 1.0)) / f
    samples, _ = k.create(text, voice=_style(k, recipe["mix"]), speed=max(0.5, min(2.0, speed)), lang="en-us")
    return texture(_shift(np.asarray(samples, dtype=np.float32), f), recipe.get("fx"))


def to_mp3(samples: np.ndarray) -> bytes:
    import lameenc
    pcm = (np.clip(samples, -1, 1) * 32767).astype("<i2").tobytes()
    enc = lameenc.Encoder()
    enc.set_bit_rate(64)
    enc.set_in_sample_rate(SR)
    enc.set_channels(1)
    enc.set_quality(2)
    return bytes(enc.encode(pcm) + enc.flush())


def render(parts: list[tuple[str, dict]]) -> bytes:
    """MP3 of the lines, each in its own voice, with a breath between speakers."""
    with _engine_lock:
        k = _get_engine()
        gap = np.zeros(int(SR * 0.28), dtype=np.float32)
        audio: list[np.ndarray] = []
        for text, recipe in parts:
            if audio:
                audio.append(gap)
            audio.append(speak(k, text, recipe))
    return to_mp3(np.concatenate(audio) if audio else np.zeros(1, dtype=np.float32))


# ── per game ─────────────────────────────────────────────────────────────────

def speakers_and_about(ctx) -> tuple[list[str], dict[str, str]]:
    """Every name that might speak, with what we know of them (for gender and ancestry hints)."""
    about: dict[str, str] = {}
    for n in ctx.state.get("npcs") or []:
        if n.get("name"):
            about[n["name"]] = " ".join(str(n.get(k) or "") for k in ("role", "notes"))
    for sm in [ctx.state.get("scene_map") or {}] + list(ctx.state.get("side_maps") or []):
        for n in sm.get("npcs") or []:
            about.setdefault(n["name"], "")
    for _, s in ctx.party():
        race = (s.get("race") or "").replace("-", " ")
        about[s["name"]] = f"{race} {s.get('class', '')} {s.get('backstory', '')[:200]}"
    return list(about), about


def recipe(ctx, name: str | None, about: dict[str, str], narration: str) -> dict:
    """The saved recipe for a speaker, or a new one (saved so they always sound the same)."""
    if name is None:
        return NARRATOR
    if name == "?":
        return STRANGER
    voices = ctx.state.setdefault("voices", {})
    key = name.lower()
    if key not in voices:
        if name.startswith("the ") and name not in about:  # an unnamed speaker known by role: "the steward"
            voices[key] = recipe_for(name, name)
        else:
            near = " ".join(s for s in re.split(r"(?<=[.!?])\s", narration) if name.split()[-1] in s)
            voices[key] = recipe_for(name, f"{about.get(name, '')} {near}")
    return voices[key]


async def voice_narration(game_id: str, log_id: int) -> None:
    """Voice one narration in the background and attach the audio to its log entry."""
    if not available():
        return
    from ..db import SessionLocal
    from ..models import LogEntry
    from .flow import changed
    from .state import load, lock_for

    async with lock_for(game_id):
        db = SessionLocal()
        try:
            ctx = load(db, game_id)
            if not ctx.settings.get("voices", True):
                return
            entry = db.get(LogEntry, log_id)
            if not entry or entry.kind != "narration" or not entry.text.strip():
                return
            names, about = speakers_and_about(ctx)
            segs = segments(entry.text, names, about)
            parts = [(t, recipe(ctx, s, about, entry.text)) for t, s in segs]
            ctx.save()  # new recipes
            db.commit()
        finally:
            db.close()
    if not parts:
        return
    try:
        mp3 = await asyncio.to_thread(render, parts)
    except Exception as e:  # noqa: BLE001 — speech is a nice-to-have
        global _engine_failed
        log.warning("voicing narration %s failed: %s", log_id, e)
        if _engine is None:
            _engine_failed = True
        return
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    name = f"{game_id}-{log_id}.mp3"
    (AUDIO_DIR / name).write_bytes(mp3)
    db = SessionLocal()
    try:
        entry = db.get(LogEntry, log_id)
        if entry:
            entry.data = {**(entry.data or {}), "audio": f"/api/files/voice/{name}",
                          "speakers": sorted({s for _, s in segs if s and s != "?"})}
            db.commit()
    finally:
        db.close()
    await changed(game_id, [])


def suggest(text: str) -> dict:
    """A fresh random recipe for whoever speaks in `text` (Settings → Surprise me): the gender comes from how they
    are described outside the quotes ('the steward says' → male), the rest is random."""
    import secrets
    outside = re.sub(r'"[^"]*"', " ", _clean(text))
    who = role_speaker(outside) or ""
    return recipe_for(secrets.token_hex(6), f"{who} {outside}")
