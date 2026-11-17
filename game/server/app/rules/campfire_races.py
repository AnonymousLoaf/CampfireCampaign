"""Campfire races: original Campfire Campaign races, plus validation for players' homebrew races.

The seven races below are original Campfire Campaign content, written for this project. They are not
SRD content and are not taken or adapted from any non-SRD publication; they are released under the
repository's license (GNU AGPL v3, see LICENSE at the repo root).

Every race works in both rules editions:
- 2014: the race's `ability_bonuses` (+3 total) are applied at creation.
- 2024: ability increases come from the background, so `ability_bonuses` are ignored; a trait may carry
  `text_2024` with the 2024-style usage wording (uses per Proficiency Bonus per Long Rest).

Mechanics the engine applies: speed, size, `resistances` (half damage), and `skills` (proficiencies added
at creation). Everything else in a trait is rules text the DM adjudicates (it is in the DM prompt).
"""
from __future__ import annotations

ABILITIES = ("STR", "DEX", "CON", "INT", "WIS", "CHA")

_ONCE_2014 = "You can use this once, regaining the use when you finish a short or long rest."
_ONCE_2024 = "You can use this a number of times equal to your Proficiency Bonus, regaining all uses on a Long Rest."


def _limited(text: str) -> dict:
    """A trait with a limited-use clause in each edition's style."""
    return {"text": f"{text} {_ONCE_2014}", "text_2024": f"{text} {_ONCE_2024}"}


CAMPFIRE_RACES: dict[str, dict] = {
    "campfire-felari": {
        "name": "Felari",
        "concept": "Sleek cat-folk wanderers: curious, light-footed, and always landing on their feet.",
        "size": "Medium", "speed": 30, "darkvision": 60,
        "languages": ["Common", "Felari"],
        "ability_bonuses": {"DEX": 2, "CHA": 1},
        "resistances": [], "skills": ["Stealth"],
        "traits": [
            {"name": "Soft-Pawed", "text": "You have proficiency in the Stealth skill."},
            {"name": "Righting Reflex", "text": "When you fall, you take no damage from the first 20 feet of the fall, "
                                                "and you land on your feet unless you're incapacitated."},
            {"name": "Pounce", **_limited("If you move at least 20 ft straight toward a creature and hit it with a melee "
                                          "attack on the same turn, it makes a STR save (DC 8 + your proficiency bonus + "
                                          "your DEX modifier) or is knocked prone.")},
        ],
    },
    "campfire-rootborn": {
        "name": "Rootborn",
        "concept": "Patient plant-folk who woke from old groves, bark-skinned and slow to anger.",
        "size": "Medium", "speed": 30, "darkvision": 0,
        "languages": ["Common", "Sylvan"],
        "ability_bonuses": {"CON": 2, "WIS": 1},
        "resistances": [], "skills": [],
        "traits": [
            {"name": "Deep Roots", "text": "While you stand on earth or stone, you have advantage on checks and saves "
                                           "against being shoved, pulled, or knocked prone."},
            {"name": "Sap Mending", **_limited("As a bonus action, spend one of your Hit Dice: roll it and regain that "
                                               "many HP plus your CON modifier.")},
            {"name": "Grove-Tongue", "text": "You can share simple ideas with plants and fungi, which answer in vague "
                                             "impressions (who passed, where water lies). With water and 4 hours of "
                                             "sunlight a day, you don't need to eat."},
        ],
    },
    "campfire-emberwrought": {
        "name": "Emberwrought",
        "concept": "Living constructs of iron and oak, woken by a spark of hearth-fire that still glows in their chest.",
        "size": "Medium", "speed": 30, "darkvision": 60,
        "languages": ["Common", "one language of your choice"],
        "ability_bonuses": {"STR": 2, "CON": 1},
        "resistances": ["poison"], "skills": [],
        "traits": [
            {"name": "Wrought Body", "text": "You have resistance to poison damage and advantage on saves against being "
                                             "poisoned. You don't need to eat, drink, or breathe."},
            {"name": "Banked Embers", "text": "Instead of sleeping, you rest dormant for 4 hours, aware of your "
                                              "surroundings; this counts as a long rest. Magic can't put you to sleep."},
            {"name": "Furnace Strike", **_limited("When you hit with a melee attack, the target takes extra fire damage "
                                                  "equal to 1d6 + your proficiency bonus.")},
        ],
    },
    "campfire-tideborn": {
        "name": "Tideborn",
        "concept": "Sea-folk of the cold deeps, with gill-slits, webbed hands, and the pull of the tide in their grip.",
        "size": "Medium", "speed": 30, "darkvision": 60,
        "languages": ["Common", "Aquan"],
        "ability_bonuses": {"WIS": 2, "STR": 1},
        "resistances": ["cold"], "skills": [],
        "traits": [
            {"name": "Gill-Breather", "text": "You can breathe air and water, and you have a swimming speed equal to "
                                              "your walking speed."},
            {"name": "Cold Depths", "text": "You have resistance to cold damage."},
            {"name": "Undertow", **_limited("When you hit a Large or smaller creature with a melee attack, you can pull "
                                            "it up to 10 ft toward you or push it up to 10 ft away.")},
        ],
    },
    "campfire-galeborn": {
        "name": "Galeborn",
        "concept": "Hollow-boned bird-folk with feathered arms who ride cliff winds and watch from high places.",
        "size": "Medium", "speed": 30, "darkvision": 0,
        "languages": ["Common", "Auran"],
        "ability_bonuses": {"DEX": 2, "WIS": 1},
        "resistances": [], "skills": ["Perception"],
        "traits": [
            {"name": "Glide", "text": "When you fall and aren't incapacitated or wearing medium or heavy armor, you "
                                      "descend up to 60 ft per round, take no falling damage, and can move 2 ft "
                                      "sideways for every 1 ft you descend."},
            {"name": "Updraft", **_limited("As a bonus action, gain a flying speed equal to your walking speed until "
                                           "the end of your turn; if you're still in the air then, you fall (and can "
                                           "Glide). Not usable in medium or heavy armor.")},
            {"name": "Hawk-Eyed", "text": "You have proficiency in the Perception skill, and dim light doesn't impose "
                                          "disadvantage on your sight-based Perception checks."},
        ],
    },
    "campfire-todling": {
        "name": "Todling",
        "concept": "Small fox-folk tricksters with quick tongues, quicker feet, and a tail for every story.",
        "size": "Small", "speed": 30, "darkvision": 60,
        "languages": ["Common", "one language of your choice"],
        "ability_bonuses": {"CHA": 2, "DEX": 1},
        "resistances": [], "skills": ["Deception"],
        "traits": [
            {"name": "Fox Feint", **_limited("When a creature you can see attacks you, you can use your reaction to "
                                             "give that attack roll disadvantage.")},
            {"name": "Silver Tongue", "text": "You have proficiency in the Deception skill, and you can mimic simple "
                                              "sounds and voices you've heard (a listener sees through it with an "
                                              "Insight check against your Deception)."},
            {"name": "Underfoot", "text": "You can move through the space of any creature at least one size larger "
                                          "than you."},
        ],
    },
    "campfire-lumari": {
        "name": "Lumari",
        "concept": "Star-touched folk with freckles that glow at night, born where falling stars came to rest.",
        "size": "Medium", "speed": 30, "darkvision": 60,
        "languages": ["Common", "Celestial"],
        "ability_bonuses": {"INT": 2, "CHA": 1},
        "resistances": ["radiant"], "skills": [],
        "traits": [
            {"name": "Starlit Skin", "text": "You have resistance to radiant damage. As a bonus action, you can make "
                                             "your skin shed dim light in a 10 ft radius, or stop."},
            {"name": "Starfall Flare", **_limited("As an action, each creature of your choice within 10 ft makes a CON "
                                                  "save (DC 8 + your proficiency bonus + your CON modifier), taking 2d6 "
                                                  "radiant damage on a failure or half on a success (3d6 at 6th level).")},
            {"name": "Night Compass", "text": "You always know which way is north. While you can see the night sky, you "
                                              "know the hour and can't become lost by nonmagical means."},
        ],
    },
}


def darkvision_trait(ft: int) -> dict | None:
    if not ft:
        return None
    return {"name": f"Darkvision ({ft} ft.)",
            "description": f"You see in dim light within {ft} ft as if it were bright light, and in darkness as if it "
                           f"were dim light (shades of gray only)."}


def trait_list(rec: dict, ruleset: str) -> list[dict]:
    """[{name, description}] for a Campfire race or a homebrew race snapshot, darkvision first."""
    out = []
    dv = darkvision_trait(int(rec.get("darkvision") or 0))
    if dv:
        out.append(dv)
    for t in rec.get("traits") or []:
        text = (t.get("text_2024") if ruleset == "2024" else None) or t.get("text") or ""
        out.append({"name": t.get("name", "Trait"), "description": text})
    return out


def option(index: str, rec: dict, ruleset: str, group: str, source: str) -> dict:
    """A creator race option in the same shape as the SRD ones (plus group/source/trait_details)."""
    traits = trait_list(rec, ruleset)
    return {
        "index": index, "name": rec["name"], "speed": rec.get("speed", 30), "size": rec.get("size", "Medium"),
        "ability_bonuses": dict(rec.get("ability_bonuses") or {}) if ruleset == "2014" else {},
        "traits": [t["name"] for t in traits], "trait_details": traits,
        "languages": list(rec.get("languages") or []),
        "subraces": [], "ability_choices": None, "ancestries": None,
        "group": group, "source": source, "concept": rec.get("concept", ""),
    }


def campfire_options(ruleset: str) -> list[dict]:
    return [option(idx, rec, ruleset, "campfire", "Campfire Campaign") for idx, rec in CAMPFIRE_RACES.items()]


# ── homebrew races (custom content kind "race") ──────────────────────────────

HOMEBREW_DATA_MAX = 8000  # JSON chars; 8 traits × 600 chars needs more than the default 4000


def clean_homebrew_race(data: dict) -> dict:
    """Validate a homebrew race's `data`; returns the normalised dict or raises ValueError with a friendly message."""
    data = data or {}
    try:
        speed = int(data.get("speed", 30) if data.get("speed") not in (None, "") else 30)
    except (TypeError, ValueError):
        raise ValueError("speed must be a whole number of feet")
    if not 20 <= speed <= 40 or speed % 5:
        raise ValueError("speed must be 20-40 ft, in steps of 5")
    size = str(data.get("size") or "Medium").strip().title()
    if size not in ("Small", "Medium"):
        raise ValueError("size must be Small or Medium")
    try:
        dv = int(data.get("darkvision") or 0)
    except (TypeError, ValueError):
        raise ValueError("darkvision must be 0, 60, or 120 ft")
    if dv not in (0, 60, 120):
        raise ValueError("darkvision must be 0, 60, or 120 ft")
    raw_b = data.get("ability_bonuses") or {}
    if not isinstance(raw_b, dict):
        raise ValueError("ability bonuses must map abilities (STR, DEX…) to +1 or +2")
    bonuses: dict[str, int] = {}
    for k, v in raw_b.items():
        key = str(k).strip().upper()
        if key not in ABILITIES:
            raise ValueError(f"{k} isn't an ability (use STR, DEX, CON, INT, WIS, CHA)")
        try:
            n = int(v)
        except (TypeError, ValueError):
            raise ValueError(f"the {key} bonus must be +1 or +2")
        if n == 0:
            continue
        if n not in (1, 2):
            raise ValueError(f"the {key} bonus must be +1 or +2")
        bonuses[key] = n
    if sum(bonuses.values()) > 3:
        raise ValueError("ability bonuses can total at most +3 (e.g. +2/+1 or +1/+1/+1)")
    langs = data.get("languages")
    if langs is None:
        langs = ["Common"]
    if isinstance(langs, str):
        langs = [x for x in langs.split(",")]
    if not isinstance(langs, list):
        raise ValueError("languages must be a list")
    langs = [str(x).strip()[:40] for x in langs if str(x).strip()]
    if len(langs) > 6:
        raise ValueError("list at most 6 languages")
    traits_in = data.get("traits") or []
    if not isinstance(traits_in, list):
        raise ValueError("traits must be a list of {name, text}")
    traits = []
    for t in traits_in:
        if not isinstance(t, dict):
            raise ValueError("each trait needs a name and text")
        name = str(t.get("name") or "").strip()
        text = str(t.get("text") or "").strip()
        if not name and not text:
            continue
        if not name:
            raise ValueError("every trait needs a name")
        if len(name) > 60:
            raise ValueError(f"trait name {name[:20]}… is too long (60 characters max)")
        if len(text) > 600:
            raise ValueError(f"the {name} trait text is too long (600 characters max)")
        traits.append({"name": name, "text": text})
    if len(traits) > 8:
        raise ValueError("a race can have at most 8 traits")
    return {"speed": speed, "size": size, "darkvision": dv, "ability_bonuses": bonuses, "languages": langs,
            "traits": traits}
