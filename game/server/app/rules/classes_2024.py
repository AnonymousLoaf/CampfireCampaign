"""The 2024 rules (SRD 5.2): classes, backgrounds, feats, species, weapon mastery and spell effects, levels 1-10.

Same schema as classes.py (the 2014 rules). Feature descriptions are short paraphrases of SRD 5.2 (CC-BY-4.0).
Code-facing feature names are shared with 2014 so the engine can key off them; where the 2024 display
name differs, the feature carries a "label" (e.g. {"name": "Ki", "label": "Monk's Focus"}).

Item keys use the 2014 equipment indices the game's item system understands; ITEM_ALIASES_2024 maps them to
the 2024 dataset's indices where those differ.

Feature `uses` specs: an int, "CHA", "CHA+1", "LEVEL", "LOH" (5 × level), "PROF", "WIS", or a level table
{level: value} — use the value for the highest key ≤ the character's level.
"""
from __future__ import annotations

import copy
import json
from functools import lru_cache

from .classes import (ABILITIES, ALL_SKILLS, EXPLORER_GEAR, FULL_CASTER_SLOTS, PACT_SLOTS, PRIEST_GEAR,
                      SCHOLAR_GEAR, SPELL_EFFECTS, F)

MAX_LEVEL_2024 = 10

# 2024 half casters (paladin, ranger) cast from level 1.
HALF_CASTER_SLOTS_2024 = {
    1: {"1": 2}, 2: {"1": 2}, 3: {"1": 3}, 4: {"1": 3}, 5: {"1": 4, "2": 2}, 6: {"1": 4, "2": 2},
    7: {"1": 4, "2": 3}, 8: {"1": 4, "2": 3}, 9: {"1": 4, "2": 3, "3": 2}, 10: {"1": 4, "2": 3, "3": 2},
}
FULL_CASTER_SLOTS_2024 = FULL_CASTER_SLOTS
PACT_SLOTS_2024 = PACT_SLOTS

_T = lambda *vals: {i + 1: v for i, v in enumerate(vals)}  # noqa: E731  (level table from a list)

DUNGEONEER_GEAR = [("backpack", 1), ("crowbar", 1), ("hammer", 1), ("piton", 10), ("torch", 10), ("tinderbox", 1),
                   ("rations-1-day", 10), ("waterskin", 1), ("rope-hempen-50-feet", 1)]
BURGLAR_GEAR = [("backpack", 1), ("ball-bearings-bag-of-1000", 1), ("string-10-feet", 1), ("bell", 1), ("candle", 5),
                ("crowbar", 1), ("hammer", 1), ("piton", 10), ("lantern-hooded", 1), ("oil-flask", 2),
                ("rations-1-day", 5), ("tinderbox", 1), ("waterskin", 1), ("rope-hempen-50-feet", 1)]
ENTERTAINER_GEAR = [("backpack", 1), ("bedroll", 1), ("clothes-costume", 2), ("candle", 5), ("rations-1-day", 5),
                    ("waterskin", 1), ("disguise-kit", 1)]

ASI = F("Ability Score Improvement", "Take the Ability Score Improvement feat (+2 to one ability or +1 to two, max 20) or another feat you qualify for.")
SUBCLASS = lambda name: F(f"Subclass: {name}", f"You gain the {name} subclass features for this level.")  # noqa: E731

FIGHTING_STYLES_2024 = {
    "Archery": "+2 to attack rolls with ranged weapons.",
    "Defense": "+1 AC while wearing Light, Medium or Heavy armor.",
    "Great Weapon Fighting": "Treat 1s and 2s on damage dice as 3s with two-handed or versatile melee weapons held in two hands.",
    "Two-Weapon Fighting": "Add your ability modifier to the damage of the extra Light-weapon attack.",
}


def gold_option(gp: int) -> dict:
    return {"id": "gold", "label": f"{gp} gp instead of equipment", "items": [], "gold_cp": gp * 100}


CLASSES_2024: dict[str, dict] = {
    "barbarian": {
        "index": "barbarian", "name": "Barbarian", "hit_die": 12, "saves": ["STR", "CON"], "primary": ["STR", "CON"],
        "description": "A fierce warrior of primal rage who shrugs off blows that would fell others.",
        "skill_choices": {"count": 2, "options": ["Animal Handling", "Athletics", "Intimidation", "Nature", "Perception", "Survival"]},
        "armor": ["Light", "Medium", "Shields"], "weapons": ["Simple", "Martial"],
        "weapon_cats": {"simple", "martial"}, "weapon_extra": set(),
        "weapon_mastery": {1: 2, 4: 3, 10: 4},
        "equipment_options": [
            {"id": "reaver", "label": "Greataxe, four handaxes, explorer's pack, 15 gp",
             "items": [("greataxe", 1, True), ("handaxe", 4, False)], "gold_cp": 1500},
            gold_option(75),
        ],
        "gear": EXPLORER_GEAR,
        "subclass_level": 3, "subclasses": [{"index": "berserker", "name": "Path of the Berserker",
                                              "description": "Frenzy: reckless attacks while raging deal extra damage."}],
        "features": {
            1: [F("Rage", "Bonus action: +2 damage with Strength attacks (+3 at 9th), resistance to bludgeoning, piercing and slashing, advantage on Strength checks and saves. Regain one use on a short rest.",
                  {"max": _T(2, 2, 3, 3, 3, 4, 4, 4, 4, 4), "per": "long"}),
                F("Unarmored Defense", "Without armor, AC = 10 + DEX + CON (a shield still counts)."),
                F("Weapon Mastery", "Use the mastery properties of 2 kinds of weapons (3 at 4th, 4 at 10th).")],
            2: [F("Danger Sense", "Advantage on Dexterity saving throws unless incapacitated."),
                F("Reckless Attack", "Advantage on Strength attacks this turn; attacks against you have advantage until your next turn.")],
            3: [F("Primal Knowledge", "Gain a skill proficiency; while raging, some Strength checks can use your rage."),
                F("Frenzy", "If you use Reckless Attack while raging, the first target you hit each turn takes extra d6s equal to your Rage Damage bonus.")],
            4: [ASI],
            5: [F("Extra Attack", "Attack twice when you take the Attack action."),
                F("Fast Movement", "+10 ft speed while not wearing heavy armor.")],
            6: [F("Mindless Rage", "While raging you're immune to being charmed or frightened.")],
            7: [F("Feral Instinct", "Advantage on Initiative rolls."),
                F("Instinctive Pounce", "When you enter your rage, move up to half your speed.")],
            8: [ASI],
            9: [F("Brutal Strike", "Forgo advantage on a reckless Strength attack: on a hit deal +1d10 and push, slow or knock the target off balance."),
                F("Brutal Critical", "Roll one additional weapon damage die on a critical melee hit (kept for parity with 2014).")],
            10: [F("Retaliation", "When a creature within 5 ft damages you, make a melee attack against it as a reaction.")],
        },
        "spellcasting": None,
    },
    "bard": {
        "index": "bard", "name": "Bard", "hit_die": 8, "saves": ["DEX", "CHA"], "primary": ["CHA", "DEX"],
        "description": "An inspiring magician whose words and music weave magic and lift allies.",
        "skill_choices": {"count": 3, "options": ALL_SKILLS},
        "armor": ["Light"], "weapons": ["Simple"], "weapon_cats": {"simple"}, "weapon_extra": set(),
        "equipment_options": [
            {"id": "minstrel", "label": "Leather armor, two daggers, a lute, entertainer's pack, 19 gp",
             "items": [("leather-armor", 1, True), ("dagger", 2, True), ("lute", 1, False)], "gold_cp": 1900},
            gold_option(90),
        ],
        "gear": ENTERTAINER_GEAR,
        "subclass_level": 3, "subclasses": [{"index": "lore", "name": "College of Lore",
                                              "description": "Bonus proficiencies, Cutting Words and Magical Discoveries."}],
        "features": {
            1: [F("Bardic Inspiration", "Bonus action: give an ally within 60 ft an Inspiration die (d6, d8 at 5th, d10 at 10th) to add to a failed d20 test.",
                  {"max": "CHA", "per": "long"}),
                F("Spellcasting", "You prepare bard spells and cast them with Charisma.")],
            2: [F("Expertise", "Double proficiency in two of your skills."),
                F("Jack of All Trades", "Add half your proficiency bonus to checks you aren't proficient in.")],
            3: [F("Bonus Proficiencies", "Gain proficiency in three skills of your choice."),
                F("Cutting Words", "Reaction: spend Bardic Inspiration to subtract the die from an enemy's attack, check or damage.")],
            4: [ASI],
            5: [F("Font of Inspiration", "Bardic Inspiration recovers on a short rest; spend a spell slot to regain a use.")],
            6: [F("Magical Discoveries", "Learn two spells from the cleric, druid or wizard lists; they're always prepared.")],
            7: [F("Countercharm", "Reaction: let a creature within 30 ft reroll a failed save against charm or fright, with advantage.")],
            8: [ASI],
            9: [F("Expertise (more)", "Double proficiency for two more skills.")],
            10: [F("Magical Secrets", "Your prepared spells can come from the bard, cleric, druid and wizard lists.")],
        },
        "spellcasting": {"ability": "CHA", "type": "full", "list": "Bard", "known": False, "prepares": True,
                         "cantrips_known": _T(2, 2, 2, 3, 3, 3, 3, 3, 3, 4),
                         "prepared": _T(4, 5, 6, 7, 9, 10, 11, 12, 14, 15)},
    },
    "cleric": {
        "index": "cleric", "name": "Cleric", "hit_die": 8, "saves": ["WIS", "CHA"], "primary": ["WIS", "CON"],
        "description": "A priestly champion who wields divine magic in service of a higher power.",
        "skill_choices": {"count": 2, "options": ["History", "Insight", "Medicine", "Persuasion", "Religion"]},
        "armor": ["Light", "Medium", "Shields"], "weapons": ["Simple"], "weapon_cats": {"simple"}, "weapon_extra": set(),
        "equipment_options": [
            {"id": "warpriest", "label": "Chain shirt, shield, mace, holy symbol, priest's pack, 7 gp",
             "items": [("chain-shirt", 1, True), ("shield", 1, True), ("mace", 1, True), ("amulet", 1, False)],
             "gold_cp": 700},
            gold_option(110),
        ],
        "gear": PRIEST_GEAR,
        "subclass_level": 3, "subclasses": [{"index": "life", "name": "Life Domain",
                                              "description": "Disciple of Life, Preserve Life and healing domain spells."}],
        "features": {
            1: [F("Divine Order", "Protector (martial weapons and heavy armor) or Thaumaturge (an extra cantrip and +WIS to Arcana/Religion)."),
                F("Spellcasting", "You prepare cleric spells and cast them with Wisdom.")],
            2: [F("Channel Divinity", "Divine Spark (heal or harm 1d8 + WIS, 2d8 at 7th) or Turn Undead. Regain one use on a short rest.",
                  {"max": {2: 2, 6: 3}, "per": "long"})],
            3: [F("Disciple of Life", "Your healing spells restore an extra 2 + the spell slot's level hit points."),
                F("Preserve Life", "Channel Divinity: heal 5 × your cleric level HP split among allies within 30 ft (up to half their max).")],
            4: [ASI],
            5: [F("Sear Undead", "When you Turn Undead, each undead that fails takes radiant damage (WIS modifier d8s).")],
            6: [F("Blessed Healer", "When you cast a healing spell on someone else, you regain 2 + the slot's level hit points.")],
            7: [F("Divine Strike", "Blessed Strikes: once per turn, a weapon hit deals an extra 1d8 radiant or necrotic damage.",
                  None)],
            8: [ASI],
            9: [],
            10: [F("Divine Intervention", "Cast any cleric spell of level 5 or lower without a slot or components.",
                   {"max": 1, "per": "long"})],
        },
        "spellcasting": {"ability": "WIS", "type": "full", "list": "Cleric", "known": False, "prepares": True,
                         "cantrips_known": _T(3, 3, 3, 4, 4, 4, 4, 4, 4, 5),
                         "prepared": _T(4, 5, 6, 7, 9, 10, 11, 12, 14, 15),
                         "always": {3: ["aid", "bless", "cure-wounds", "lesser-restoration"],
                                    5: ["mass-healing-word", "revivify"], 7: ["aura-of-life", "death-ward"],
                                    9: ["greater-restoration", "mass-cure-wounds"]}},
    },
    "druid": {
        "index": "druid", "name": "Druid", "hit_die": 8, "saves": ["INT", "WIS"], "primary": ["WIS", "CON"],
        "description": "A priest of the Old Faith who wields the powers of nature.",
        "skill_choices": {"count": 2, "options": ["Arcana", "Animal Handling", "Insight", "Medicine", "Nature", "Perception", "Religion", "Survival"]},
        "armor": ["Light", "Shields"], "weapons": ["Simple"], "weapon_cats": {"simple"}, "weapon_extra": set(),
        "equipment_options": [
            {"id": "warden", "label": "Leather armor, shield, sickle, druidic focus, explorer's pack, herbalism kit, 9 gp",
             "items": [("leather-armor", 1, True), ("shield", 1, True), ("sickle", 1, True), ("quarterstaff", 1, False),
                       ("herbalism-kit", 1, False)], "gold_cp": 900},
            gold_option(50),
        ],
        "gear": EXPLORER_GEAR,
        "subclass_level": 3, "subclasses": [{"index": "land", "name": "Circle of the Land",
                                              "description": "Circle spells, Land's Aid and Natural Recovery."}],
        "features": {
            1: [F("Druidic", "You know Druidic and always have Speak with Animals prepared."),
                F("Primal Order", "Magician (an extra cantrip, +WIS to Arcana/Nature) or Warden (martial weapons and medium armor)."),
                F("Spellcasting", "You prepare druid spells and cast them with Wisdom.")],
            2: [F("Wild Shape", "Bonus action: transform into a beast you've seen (CR 1/4, 1/2 at 4th, 1 at 8th). Describe it to the DM. Regain one use on a short rest.",
                  {"max": _T(0, 2, 2, 2, 2, 3, 3, 3, 3, 3), "per": "long"}),
                F("Wild Companion", "Expend a Wild Shape use or a slot to cast Find Familiar.")],
            3: [F("Land's Aid", "Wild Shape use: 10-ft sphere within 60 ft; enemies take 2d6 necrotic (CON save half), one ally heals 2d6."),
                F("Circle of the Land Spells", "Your land type grants extra always-prepared spells.")],
            4: [ASI],
            5: [F("Wild Resurgence", "Trade a spell slot for a Wild Shape use, or a Wild Shape use for a level 1 slot (once per long rest).")],
            6: [F("Natural Recovery", "Once per long rest, recover spell slots after a short rest.", {"max": 1, "per": "long"})],
            7: [F("Elemental Fury", "Potent Spellcasting (+WIS to cantrip damage) or Primal Strike (+1d8 elemental damage once per turn).")],
            8: [ASI],
            9: [],
            10: [F("Nature's Ward", "Immune to the poisoned condition; resistance to one damage type tied to your land.")],
        },
        "spellcasting": {"ability": "WIS", "type": "full", "list": "Druid", "known": False, "prepares": True,
                         "cantrips_known": _T(2, 2, 2, 3, 3, 3, 3, 3, 3, 4),
                         "prepared": _T(4, 5, 6, 7, 9, 10, 11, 12, 14, 15)},
    },
    "fighter": {
        "index": "fighter", "name": "Fighter", "hit_die": 10, "saves": ["STR", "CON"], "primary": ["STR", "DEX"],
        "description": "A master of weapons and armour who wins fights through skill, grit and stamina.",
        "skill_choices": {"count": 2, "options": ["Acrobatics", "Animal Handling", "Athletics", "History", "Insight",
                                                   "Intimidation", "Persuasion", "Perception", "Survival"]},
        "armor": ["Light", "Medium", "Heavy", "Shields"], "weapons": ["Simple", "Martial"],
        "weapon_cats": {"simple", "martial"}, "weapon_extra": set(),
        "fighting_style_level": 1, "weapon_mastery": {1: 3, 4: 4, 10: 5},
        "equipment_options": [
            {"id": "defender", "label": "Chain mail, greatsword, flail, eight javelins, dungeoneer's pack, 4 gp",
             "items": [("chain-mail", 1, True), ("greatsword", 1, True), ("flail", 1, False), ("javelin", 8, False)],
             "gold_cp": 400},
            {"id": "archer", "label": "Studded leather, scimitar, shortsword, longbow, 20 arrows, quiver, dungeoneer's pack, 11 gp",
             "items": [("studded-leather-armor", 1, True), ("scimitar", 1, True), ("shortsword", 1, True),
                       ("longbow", 1, False), ("arrow", 20, False), ("quiver", 1, False)], "gold_cp": 1100},
            gold_option(155),
        ],
        "gear": DUNGEONEER_GEAR,
        "subclass_level": 3, "subclasses": [{"index": "champion", "name": "Champion",
                                              "description": "Improved Critical and Remarkable Athlete."}],
        "features": {
            1: [F("Fighting Style", "You gain a Fighting Style feat."),
                F("Second Wind", "Bonus action: regain 1d10 + fighter level hit points. Regain one use on a short rest.",
                  {"max": _T(2, 2, 2, 3, 3, 3, 3, 3, 3, 4), "per": "long"}),
                F("Weapon Mastery", "Use the mastery properties of 3 kinds of weapons (4 at 4th, 5 at 10th).")],
            2: [F("Action Surge", "On your turn, take one additional action (not the Magic action).", {"max": 1, "per": "short"}),
                F("Tactical Mind", "Spend a Second Wind use to add 1d10 to a failed ability check.")],
            3: [F("Improved Critical", "Your weapon and unarmed attacks score a critical hit on a roll of 19 or 20."),
                F("Remarkable Athlete", "Advantage on Initiative and Athletics checks; move half your speed after a critical hit.")],
            4: [ASI],
            5: [F("Extra Attack", "Attack twice when you take the Attack action."),
                F("Tactical Shift", "When you use Second Wind, move up to half your speed without provoking opportunity attacks.")],
            6: [ASI],
            7: [F("Additional Fighting Style", "You gain another Fighting Style feat.")],
            8: [ASI],
            9: [F("Indomitable", "Reroll a failed saving throw with a bonus equal to your fighter level.", {"max": 1, "per": "long"}),
                F("Tactical Master", "Swap a weapon's mastery for Push, Sap or Slow on an attack.")],
            10: [F("Heroic Warrior", "At the start of each of your turns in combat, gain Heroic Inspiration if you lack it.")],
        },
        "spellcasting": None,
    },
    "monk": {
        "index": "monk", "name": "Monk", "hit_die": 8, "saves": ["STR", "DEX"], "primary": ["DEX", "WIS"],
        "description": "A master of martial arts who channels focus to strike with speed and precision.",
        "skill_choices": {"count": 2, "options": ["Acrobatics", "Athletics", "History", "Insight", "Religion", "Stealth"]},
        "armor": [], "weapons": ["Simple", "Martial (Light)"], "weapon_cats": {"simple"},
        "weapon_extra": {"shortsword", "scimitar", "crossbow-hand"},
        "equipment_options": [
            {"id": "spear", "label": "Spear, five daggers, explorer's pack, 11 gp",
             "items": [("spear", 1, True), ("dagger", 5, False)], "gold_cp": 1100},
            gold_option(50),
        ],
        "gear": EXPLORER_GEAR,
        "subclass_level": 3, "subclasses": [{"index": "open-hand", "name": "Warrior of the Open Hand",
                                              "description": "Open Hand Technique: Flurry of Blows hits can topple, push or deny reactions."}],
        "features": {
            1: [F("Martial Arts", "Use DEX for unarmed strikes and monk weapons; Martial Arts die d6 (d8 at 5th); bonus-action unarmed strike."),
                F("Unarmored Defense", "Without armor or shield, AC = 10 + DEX + WIS.")],
            2: [{**F("Ki", "Focus Points equal to your monk level fuel Flurry of Blows, Patient Defense and Step of the Wind. Recover on a short rest.",
                     {"max": "LEVEL", "per": "short"}), "label": "Monk's Focus"},
                F("Unarmored Movement", "+10 ft speed without armor or shield (+15 at 6th)."),
                F("Uncanny Metabolism", "When you roll Initiative, regain all Focus Points and heal Martial Arts die + level.", {"max": 1, "per": "long"})],
            3: [F("Deflect Attacks", "Reaction: reduce damage from an attack by 1d10 + DEX + level; redirect it for 1 Focus Point."),
                F("Open Hand Technique", "Flurry of Blows hits can knock prone, push 15 ft or deny reactions.")],
            4: [ASI, F("Slow Fall", "Reaction: reduce falling damage by 5 × your monk level.")],
            5: [F("Extra Attack", "Attack twice when you take the Attack action."),
                F("Stunning Strike", "Once per turn on a hit, spend 1 Focus Point: CON save or stunned until your next turn.")],
            6: [F("Empowered Strikes", "Unarmed strikes can deal force damage."),
                F("Wholeness of Body", "Bonus action: heal Martial Arts die + WIS modifier.", {"max": "WIS", "per": "long"}),
                F("Unarmored Movement (+15 ft)", "Your unarmored speed bonus becomes +15 ft.")],
            7: [F("Evasion", "On a DEX save for half damage, you take none on a success and half on a failure.")],
            8: [ASI],
            9: [F("Acrobatic Movement", "Move along vertical surfaces and across liquids on your turn.")],
            10: [F("Heightened Focus", "Flurry of Blows makes three strikes; Patient Defense and Step of the Wind improve."),
                 F("Self-Restoration", "End charmed, frightened or poisoned on yourself at the end of each turn."),
                 F("Unarmored Movement (+20 ft)", "Your unarmored speed bonus becomes +20 ft.")],
        },
        "spellcasting": None,
    },
    "paladin": {
        "index": "paladin", "name": "Paladin", "hit_die": 10, "saves": ["WIS", "CHA"], "primary": ["STR", "CHA"],
        "description": "A holy warrior bound to a sacred oath.",
        "skill_choices": {"count": 2, "options": ["Athletics", "Insight", "Intimidation", "Medicine", "Persuasion", "Religion"]},
        "armor": ["Light", "Medium", "Heavy", "Shields"], "weapons": ["Simple", "Martial"],
        "weapon_cats": {"simple", "martial"}, "weapon_extra": set(),
        "fighting_style_level": 2, "weapon_mastery": {1: 2},
        "equipment_options": [
            {"id": "knight", "label": "Chain mail, shield, longsword, six javelins, holy symbol, priest's pack, 9 gp",
             "items": [("chain-mail", 1, True), ("shield", 1, True), ("longsword", 1, True), ("javelin", 6, False),
                       ("emblem", 1, False)], "gold_cp": 900},
            gold_option(150),
        ],
        "gear": PRIEST_GEAR,
        "subclass_level": 3, "subclasses": [{"index": "devotion", "name": "Oath of Devotion",
                                              "description": "Sacred Weapon, Aura of Devotion and oath spells."}],
        "features": {
            1: [F("Lay on Hands", "Bonus action: heal from a pool of 5 × your paladin level hit points.", {"max": "LOH", "per": "long"}),
                F("Spellcasting", "You prepare paladin spells and cast them with Charisma."),
                F("Weapon Mastery", "Use the mastery properties of 2 kinds of weapons.")],
            2: [F("Fighting Style", "You gain a Fighting Style feat (or Blessed Warrior: two cleric cantrips)."),
                {**F("Divine Smite", "You always have Divine Smite prepared and can cast it once without a slot per long rest: on a melee hit, +2d8 radiant (+1d8 per slot level above 1st, +1d8 vs fiends and undead)."),
                 "label": "Paladin's Smite"}],
            3: [F("Channel Divinity", "Divine Sense, or Sacred Weapon (+CHA to attack rolls for 10 minutes). Regain one use on a short rest.",
                  {"max": {3: 2}, "per": "long"})],
            4: [ASI],
            5: [F("Extra Attack", "Attack twice when you take the Attack action."),
                F("Faithful Steed", "You always have Find Steed prepared and can cast it once without a slot.")],
            6: [F("Aura of Protection", "You and allies within 10 ft add your CHA modifier (min +1) to saving throws while you're conscious.")],
            7: [F("Aura of Devotion", "You and allies in your aura are immune to being charmed.")],
            8: [ASI],
            9: [F("Abjure Foes", "Channel Divinity: frighten up to CHA modifier creatures within 60 ft (WIS save).")],
            10: [F("Aura of Courage", "You and allies in your aura are immune to being frightened.")],
        },
        "spellcasting": {"ability": "CHA", "type": "half", "list": "Paladin", "known": False, "prepares": True,
                         "cantrips_known": {}, "prepared": _T(2, 3, 4, 5, 6, 6, 7, 7, 9, 9),
                         "always": {2: ["divine-smite"], 3: ["protection-from-evil-and-good", "shield-of-faith"],
                                    5: ["aid", "zone-of-truth"], 9: ["beacon-of-hope", "dispel-magic"]}},
    },
    "ranger": {
        "index": "ranger", "name": "Ranger", "hit_die": 10, "saves": ["STR", "DEX"], "primary": ["DEX", "WIS"],
        "description": "A warrior of the wilds who hunts the monsters that threaten civilisation.",
        "skill_choices": {"count": 3, "options": ["Animal Handling", "Athletics", "Insight", "Investigation", "Nature", "Perception", "Stealth", "Survival"]},
        "armor": ["Light", "Medium", "Shields"], "weapons": ["Simple", "Martial"],
        "weapon_cats": {"simple", "martial"}, "weapon_extra": set(),
        "fighting_style_level": 2, "weapon_mastery": {1: 2},
        "equipment_options": [
            {"id": "stalker", "label": "Studded leather, scimitar, shortsword, longbow, 20 arrows, quiver, druidic focus, explorer's pack, 7 gp",
             "items": [("studded-leather-armor", 1, True), ("scimitar", 1, True), ("shortsword", 1, True), ("longbow", 1, True),
                       ("arrow", 20, False), ("quiver", 1, False), ("sprig-of-mistletoe", 1, False)], "gold_cp": 700},
            gold_option(150),
        ],
        "gear": EXPLORER_GEAR,
        "subclass_level": 3, "subclasses": [{"index": "hunter", "name": "Hunter",
                                              "description": "Hunter's Prey (Colossus Slayer) and Defensive Tactics."}],
        "features": {
            1: [F("Spellcasting", "You prepare ranger spells and cast them with Wisdom."),
                F("Favored Enemy", "You always have Hunter's Mark prepared and can cast it without a slot a few times per long rest.",
                  {"max": _T(2, 2, 2, 2, 3, 3, 3, 3, 4, 4), "per": "long"}),
                F("Weapon Mastery", "Use the mastery properties of 2 kinds of weapons.")],
            2: [F("Deft Explorer", "Expertise in one skill and two extra languages."),
                F("Fighting Style", "You gain a Fighting Style feat (or Druidic Warrior: two druid cantrips).")],
            3: [F("Hunter's Lore", "While a creature is marked by your Hunter's Mark, you know its immunities, resistances and vulnerabilities."),
                F("Colossus Slayer", "Hunter's Prey: once per turn, +1d8 damage to a creature below its hit point maximum.")],
            4: [ASI],
            5: [F("Extra Attack", "Attack twice when you take the Attack action.")],
            6: [F("Roving", "+10 ft speed while not in heavy armor; climb and swim speeds equal your speed.")],
            7: [F("Defensive Tactics", "Escape the Horde or Multiattack Defense (opportunity attacks against you have disadvantage).")],
            8: [ASI],
            9: [F("Expertise", "Expertise in two skills.")],
            10: [F("Tireless", "Magic action: gain temporary HP (1d8 + WIS) a few times per long rest; short rests remove exhaustion.",
                   {"max": "WIS", "per": "long"})],
        },
        "spellcasting": {"ability": "WIS", "type": "half", "list": "Ranger", "known": False, "prepares": True,
                         "cantrips_known": {}, "prepared": _T(2, 3, 4, 5, 6, 6, 7, 7, 9, 9),
                         "always": {1: ["hunter-s-mark"]}},
    },
    "rogue": {
        "index": "rogue", "name": "Rogue", "hit_die": 8, "saves": ["DEX", "INT"], "primary": ["DEX", "CON"],
        "description": "A scoundrel who uses stealth and trickery to find the weak spot and strike it.",
        "skill_choices": {"count": 4, "options": ["Acrobatics", "Athletics", "Deception", "Insight", "Intimidation",
                                                   "Investigation", "Perception", "Persuasion", "Sleight of Hand", "Stealth"]},
        "armor": ["Light"], "weapons": ["Simple", "Martial (Finesse or Light)"],
        "weapon_cats": {"simple"}, "weapon_extra": {"crossbow-hand", "rapier", "scimitar", "shortsword", "whip"},
        "expertise_at_l1": 2, "weapon_mastery": {1: 2},
        "equipment_options": [
            {"id": "cutpurse", "label": "Leather armor, two daggers, shortsword, shortbow, 20 arrows, quiver, thieves' tools, burglar's pack, 8 gp",
             "items": [("leather-armor", 1, True), ("dagger", 2, False), ("shortsword", 1, True), ("shortbow", 1, True),
                       ("arrow", 20, False), ("quiver", 1, False), ("thieves-tools", 1, False)], "gold_cp": 800},
            gold_option(100),
        ],
        "gear": BURGLAR_GEAR,
        "subclass_level": 3, "subclasses": [{"index": "thief", "name": "Thief", "description": "Fast Hands, Second-Story Work and Supreme Sneak."}],
        "features": {
            1: [F("Expertise", "Double proficiency in two of your skills."),
                F("Sneak Attack", "Once per turn, extra damage (1d6 per two rogue levels, rounded up) to a Finesse or ranged attack with advantage, or when an ally is next to the target."),
                F("Thieves' Cant", "A secret mix of dialect, jargon and code."),
                F("Weapon Mastery", "Use the mastery properties of 2 kinds of weapons.")],
            2: [F("Cunning Action", "Bonus action on each turn: Dash, Disengage or Hide.")],
            3: [F("Steady Aim", "Bonus action: advantage on your next attack this turn if you haven't moved."),
                F("Fast Hands", "Bonus action: Sleight of Hand, use thieves' tools or use an object."),
                F("Second-Story Work", "Climb at full speed; jump farther using DEX.")],
            4: [ASI],
            5: [F("Cunning Strike", "Trade Sneak Attack dice for effects: poison, trip or withdraw."),
                F("Uncanny Dodge", "When an attacker you can see hits you, halve the damage (once per round).")],
            6: [F("Expertise (more)", "Double proficiency for two more skills.")],
            7: [F("Evasion", "On a DEX save for half damage, you take none on a success and half on a failure."),
                F("Reliable Talent", "Treat a d20 roll of 9 or lower as 10 on checks with a skill you're proficient in.")],
            8: [ASI],
            9: [F("Supreme Sneak", "Cunning Strike option: attack while hidden without revealing yourself.")],
            10: [ASI],
        },
        "spellcasting": None,
    },
    "sorcerer": {
        "index": "sorcerer", "name": "Sorcerer", "hit_die": 6, "saves": ["CON", "CHA"], "primary": ["CHA", "CON"],
        "description": "A spellcaster with innate magic in the blood.",
        "skill_choices": {"count": 2, "options": ["Arcana", "Deception", "Insight", "Intimidation", "Persuasion", "Religion"]},
        "armor": [], "weapons": ["Simple"], "weapon_cats": {"simple"}, "weapon_extra": set(),
        "equipment_options": [
            {"id": "mystic", "label": "Spear, two daggers, arcane focus (crystal), dungeoneer's pack, 28 gp",
             "items": [("spear", 1, True), ("dagger", 2, False), ("crystal", 1, False)], "gold_cp": 2800},
            gold_option(50),
        ],
        "gear": DUNGEONEER_GEAR,
        "subclass_level": 3, "subclasses": [{"index": "draconic", "name": "Draconic Sorcery",
                                              "description": "Draconic Resilience, draconic spells and Elemental Affinity."}],
        "features": {
            1: [F("Innate Sorcery", "Bonus action for 1 minute: +1 spell save DC and advantage on sorcerer spell attacks.",
                  {"max": 2, "per": "long"}),
                F("Spellcasting", "You prepare sorcerer spells and cast them with Charisma.")],
            2: [F("Font of Magic", "Sorcery points equal to your level; convert them to and from spell slots.", {"max": "LEVEL", "per": "long"}),
                F("Metamagic", "Two Metamagic options to twist your spells (narrated with the DM).")],
            3: [F("Draconic Resilience", "+1 HP per sorcerer level (from 3rd); without armor, AC = 10 + DEX + CHA.")],
            4: [ASI],
            5: [F("Sorcerous Restoration", "On a short rest, regain sorcery points up to half your level.", {"max": 1, "per": "long"})],
            6: [F("Elemental Affinity", "Resistance to your draconic damage type; add CHA to one damage roll of spells of that type.")],
            7: [F("Sorcery Incarnate", "Spend 2 sorcery points to use Innate Sorcery; use two Metamagic options on one spell while it's active.")],
            8: [ASI],
            9: [],
            10: [F("Metamagic (more)", "Learn two more Metamagic options.")],
        },
        "spellcasting": {"ability": "CHA", "type": "full", "list": "Sorcerer", "known": False, "prepares": True,
                         "cantrips_known": _T(4, 4, 4, 5, 5, 5, 5, 5, 5, 6),
                         "prepared": _T(2, 4, 6, 7, 9, 10, 11, 12, 14, 15),
                         "always": {3: ["alter-self", "chromatic-orb", "command", "dragon-s-breath"],
                                    5: ["fear", "fly"], 7: ["arcane-eye", "charm-monster"],
                                    9: ["legend-lore", "summon-dragon"]}},
    },
    "warlock": {
        "index": "warlock", "name": "Warlock", "hit_die": 8, "saves": ["WIS", "CHA"], "primary": ["CHA", "CON"],
        "description": "A wielder of magic granted by a pact with an otherworldly patron.",
        "skill_choices": {"count": 2, "options": ["Arcana", "Deception", "History", "Intimidation", "Investigation", "Nature", "Religion"]},
        "armor": ["Light"], "weapons": ["Simple"], "weapon_cats": {"simple"}, "weapon_extra": set(),
        "equipment_options": [
            {"id": "occultist", "label": "Leather armor, sickle, two daggers, arcane focus (orb), book, scholar's pack, 15 gp",
             "items": [("leather-armor", 1, True), ("sickle", 1, True), ("dagger", 2, False), ("orb", 1, False)],
             "gold_cp": 1500},
            gold_option(100),
        ],
        "gear": SCHOLAR_GEAR,
        "subclass_level": 3, "subclasses": [{"index": "fiend", "name": "Fiend Patron",
                                              "description": "Dark One's Blessing, fiend spells and Dark One's Own Luck."}],
        "features": {
            1: [F("Eldritch Invocations", "Gain occult boons (1 at 1st, 3 at 2nd, 5 at 5th, 6 at 7th, 7 at 9th) — narrated except Agonizing Blast."),
                F("Pact Magic", "Few spell slots, always cast at the highest level, recovered on a short rest.")],
            2: [F("Magical Cunning", "Once per long rest, a 1-minute rite recovers half your pact slots.", {"max": 1, "per": "long"}),
                {**F("Agonizing Blast", "Add your CHA modifier to Eldritch Blast damage."), "label": "Invocation: Agonizing Blast"}],
            3: [F("Dark One's Blessing", "When you reduce an enemy to 0 HP, gain CHA + warlock level temporary HP.")],
            4: [ASI],
            5: [],
            6: [F("Dark One's Own Luck", "Add a d10 to an ability check or saving throw.", {"max": "CHA", "per": "long"})],
            7: [],
            8: [ASI],
            9: [F("Contact Patron", "Cast Contact Other Plane to reach your patron without a slot.", {"max": 1, "per": "long"})],
            10: [F("Fiendish Resilience", "After a rest, choose a damage type: you have resistance to it.")],
        },
        "spellcasting": {"ability": "CHA", "type": "pact", "list": "Warlock", "known": False, "prepares": True,
                         "cantrips_known": _T(2, 2, 2, 3, 3, 3, 3, 3, 3, 4),
                         "prepared": _T(2, 3, 4, 5, 6, 7, 8, 9, 10, 10),
                         "always": {3: ["burning-hands", "command", "scorching-ray", "suggestion"],
                                    5: ["fireball", "stinking-cloud"], 7: ["fire-shield", "wall-of-fire"],
                                    9: ["geas", "insect-plague"]}},
    },
    "wizard": {
        "index": "wizard", "name": "Wizard", "hit_die": 6, "saves": ["INT", "WIS"], "primary": ["INT", "CON"],
        "description": "A scholarly magic-user who bends reality with spells from a spellbook.",
        "skill_choices": {"count": 2, "options": ["Arcana", "History", "Insight", "Investigation", "Medicine", "Nature", "Religion"]},
        "armor": [], "weapons": ["Simple"], "weapon_cats": {"simple"}, "weapon_extra": set(),
        "equipment_options": [
            {"id": "scholar", "label": "Two daggers, arcane focus (quarterstaff), robe, spellbook, scholar's pack, 5 gp",
             "items": [("dagger", 2, False), ("quarterstaff", 1, True), ("robes", 1, False), ("spellbook", 1, False)],
             "gold_cp": 500},
            gold_option(55),
        ],
        "gear": SCHOLAR_GEAR,
        "subclass_level": 3, "subclasses": [{"index": "evocation", "name": "Evoker",
                                              "description": "Potent Cantrip, Sculpt Spells and Empowered Evocation."}],
        "features": {
            1: [F("Spellcasting", "Your spellbook holds your spells; prepare spells from it each day."),
                F("Ritual Adept", "Cast ritual spells from your spellbook without preparing them."),
                F("Arcane Recovery", "Once a day after a short rest, recover spell slots.", {"max": 1, "per": "long"})],
            2: [F("Scholar", "Expertise in one of Arcana, History, Investigation, Medicine, Nature or Religion.")],
            3: [F("Evocation Savant", "Add two wizard evocation spells to your spellbook for free."),
                F("Potent Cantrip", "Creatures that avoid your cantrip's damage still take half.")],
            4: [ASI],
            5: [F("Memorize Spell", "After a short rest, swap one prepared spell for another in your spellbook.")],
            6: [F("Sculpt Spells", "Allies are unharmed by your evocation spells.")],
            7: [],
            8: [ASI],
            9: [],
            10: [F("Empowered Evocation", "Add your INT modifier to one damage roll of any wizard evocation spell.")],
        },
        "spellcasting": {"ability": "INT", "type": "full", "list": "Wizard", "known": False, "prepares": True,
                         "spellbook": True, "cantrips_known": _T(3, 3, 3, 4, 4, 4, 4, 4, 4, 5),
                         "prepared": _T(4, 5, 6, 7, 9, 10, 11, 12, 14, 15)},
    },
}

for _c in CLASSES_2024.values():
    for _lvl in range(1, MAX_LEVEL_2024 + 1):
        _c["features"].setdefault(_lvl, [])
    for _lvl, _feats in _c["features"].items():
        for _f in _feats:
            if _f.get("uses") is None:
                _f.pop("uses", None)

ASI_LEVELS_2024 = {k: sorted(l for l, fs in c["features"].items() if any(f["name"] == "Ability Score Improvement" for f in fs))
                   for k, c in CLASSES_2024.items()}

# ── backgrounds, feats ──────────────────────────────────────────────────────

BACKGROUNDS_2024 = {
    "acolyte": {"index": "acolyte", "name": "Acolyte", "ability_options": ["INT", "WIS", "CHA"],
                "skills": ["Insight", "Religion"], "tool": "Calligrapher's Supplies", "origin_feat": "Magic Initiate",
                "magic_initiate_list": "Cleric",
                "description": "You devoted yourself to service in a temple.",
                "items": [("calligraphers-supplies", 1), ("book", 1), ("amulet", 1), ("parchment-one-sheet", 10), ("robes", 1)],
                "gold_cp": 800, "gold_only_cp": 5000},
    "criminal": {"index": "criminal", "name": "Criminal", "ability_options": ["DEX", "CON", "INT"],
                 "skills": ["Sleight of Hand", "Stealth"], "tool": "Thieves' Tools", "origin_feat": "Alert",
                 "description": "You eked out a living in dark alleys, cutting purses or burgling shops.",
                 "items": [("dagger", 2), ("thieves-tools", 1), ("crowbar", 1), ("pouch", 2), ("clothes-travelers", 1)],
                 "gold_cp": 1600, "gold_only_cp": 5000},
    "sage": {"index": "sage", "name": "Sage", "ability_options": ["CON", "INT", "WIS"],
             "skills": ["Arcana", "History"], "tool": "Calligrapher's Supplies", "origin_feat": "Magic Initiate",
             "magic_initiate_list": "Wizard",
             "description": "You spent your formative years travelling between manors and monasteries, studying lore.",
             "items": [("quarterstaff", 1), ("calligraphers-supplies", 1), ("book", 1), ("parchment-one-sheet", 8), ("robes", 1)],
             "gold_cp": 800, "gold_only_cp": 5000},
    "soldier": {"index": "soldier", "name": "Soldier", "ability_options": ["STR", "DEX", "CON"],
                "skills": ["Athletics", "Intimidation"], "tool": "Gaming Set", "origin_feat": "Savage Attacker",
                "description": "You began training for war as soon as you reached adulthood.",
                "items": [("spear", 1), ("shortbow", 1), ("arrow", 20), ("dice-set", 1), ("healers-kit", 1), ("quiver", 1),
                          ("clothes-travelers", 1)],
                "gold_cp": 1400, "gold_only_cp": 5000},
}


@lru_cache(maxsize=1)
def _data_2024() -> dict:
    from ..config import SRD_2024_PATH
    return json.loads(SRD_2024_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _data_2014() -> dict:
    from ..config import SRD_PATH
    return json.loads(SRD_PATH.read_text(encoding="utf-8"))


def _feat_category(t: str) -> str:
    return {"origin": "origin", "general": "general", "fighting-style": "fighting_style", "epic-boon": "epic"}.get(t or "", "general")


def _build_feats() -> dict:
    out = {}
    for f in _data_2024().get("feats", []):
        out[f["name"]] = {"index": f["index"], "name": f["name"], "description": f.get("description", ""),
                          "category": _feat_category(f.get("type")),
                          "repeatable": bool(f.get("repeatable")),
                          "min_level": (f.get("prerequisites") or {}).get("minimum_level")}
    # mechanics the engine can key on
    for name, mech in {"Alert": {"initiative_prof": True}, "Savage Attacker": {"savage_attacker": True},
                       "Skilled": {"extra_skills": 3},
                       "Magic Initiate": {"magic_initiate": True, "cantrips": 2, "spells": 1,
                                          "list_from_background": {"acolyte": "Cleric", "sage": "Wizard"}},
                       "Ability Score Improvement": {"asi": True},
                       "Grappler": {"asi_choice": ["STR", "DEX"]}}.items():
        if name in out:
            out[name]["mechanics"] = mech
    return out


try:
    FEATS_2024 = _build_feats()
except FileNotFoundError:  # dataset not built yet — keep imports working
    FEATS_2024 = {}

# ── weapon mastery ──────────────────────────────────────────────────────────
# 2024 PHB mastery properties, keyed by the 2024 dataset's weapon indices.
MASTERY = {
    "club": "Slow", "dagger": "Nick", "greatclub": "Push", "handaxe": "Vex", "javelin": "Slow", "light-hammer": "Nick",
    "mace": "Sap", "quarterstaff": "Topple", "sickle": "Nick", "spear": "Sap",
    "dart": "Vex", "light-crossbow": "Slow", "shortbow": "Vex", "sling": "Slow",
    "battleaxe": "Topple", "flail": "Sap", "glaive": "Graze", "greataxe": "Cleave", "greatsword": "Graze",
    "halberd": "Cleave", "lance": "Topple", "longsword": "Sap", "maul": "Topple", "morningstar": "Sap", "pike": "Push",
    "rapier": "Vex", "scimitar": "Nick", "shortsword": "Vex", "trident": "Topple", "warhammer": "Push",
    "war-pick": "Sap", "whip": "Slow",
    "blowgun": "Vex", "hand-crossbow": "Vex", "heavy-crossbow": "Push", "longbow": "Slow", "musket": "Slow", "pistol": "Vex",
}

# 2014 item index → 2024 dataset index, where they differ (the game's items use the 2014 indices).
ITEM_ALIASES_2024 = {
    "crossbow-light": "light-crossbow", "crossbow-hand": "hand-crossbow", "crossbow-heavy": "heavy-crossbow",
    "arrow": "arrows", "crossbow-bolt": "bolts", "sling-bullet": "bullets-sling", "rations-1-day": "rations",
    "rope-hempen-50-feet": "rope", "antitoxin-vial": "antitoxin", "holy-water-flask": "holy-water", "oil-flask": "oil",
    "ball-bearings-bag-of-1000": "ball-bearings", "acid-vial": "acid", "alchemists-fire-flask": "alchemists-fire",
    "poison-basic-vial": "poison-basic", "perfume-vial": "perfume", "robes": "robe", "tent-two-person": "tent",
    "parchment-one-sheet": "parchment", "paper-one-sheet": "paper", "string-10-feet": "string", "spike-iron": "spikes-iron",
    "chain-10-feet": "chain", "ladder-10-foot": "ladder", "pole-10-foot": "pole", "mirror-steel": "mirror",
    "ink-1-ounce-bottle": "ink", "flask-or-tankard": "flask", "jug-or-pitcher": "jug", "clothes-costume": "costume",
    "dungeoneers-pack": "dungeoneer-pack", "diplomats-pack": "diplomat-pack", "cartographers-tools": "cartographer-tools",
    "playing-card-set": "playing-cards", "dice-set": "dice", "robes ": "robe",
}
ITEM_ALIASES_2024.pop("robes ", None)

# Mastery keyed by the game's (2014) weapon indices.
MASTERY_BY_ITEM = {k: v for k, v in MASTERY.items()}
for _old, _new in ITEM_ALIASES_2024.items():
    if _new in MASTERY:
        MASTERY_BY_ITEM[_old] = MASTERY[_new]


def _mastery_descriptions() -> dict:
    try:
        return {p["name"]: p.get("description", "") for p in _data_2024().get("weapon_mastery_properties", [])}
    except FileNotFoundError:
        return {}


MASTERY_DESCRIPTIONS = _mastery_descriptions()

# ── species ─────────────────────────────────────────────────────────────────

_DRAGON_DAMAGE = {"black": "acid", "blue": "lightning", "brass": "fire", "bronze": "lightning", "copper": "acid",
                  "gold": "fire", "green": "poison", "red": "fire", "silver": "cold", "white": "cold"}

SPECIES_2024 = {
    "dragonborn": {"name": "Dragonborn", "speed": 30, "size": "Medium", "resistances": [],
                   "traits": ["Draconic Ancestry", "Breath Weapon", "Damage Resistance", "Darkvision (60 ft.)", "Draconic Flight"],
                   "subspecies": [f"draconic-ancestor-{c}" for c in _DRAGON_DAMAGE],
                   "mechanics": {"breath_weapon": True, "breath_dice": {1: "1d10", 5: "2d10"}, "breath_uses": "PROF",
                                 "breath_shapes": ["cone15", "line30"], "breath_save": "DEX",
                                 "resist_by_subspecies": {f"draconic-ancestor-{c}": [d] for c, d in _DRAGON_DAMAGE.items()},
                                 "damage_by_subspecies": {f"draconic-ancestor-{c}": d for c, d in _DRAGON_DAMAGE.items()}}},
    "dwarf": {"name": "Dwarf", "speed": 30, "size": "Medium", "resistances": ["poison"],
              "traits": ["Darkvision (120 ft.)", "Dwarven Resilience", "Dwarven Toughness", "Stonecunning"],
              "subspecies": [], "mechanics": {"tough_per_level": 1, "poison_save_adv": True}},
    "elf": {"name": "Elf", "speed": 30, "size": "Medium", "resistances": [],
            "traits": ["Darkvision (60 ft.)", "Elven Lineage", "Fey Ancestry", "Keen Senses", "Trance"],
            "subspecies": ["elven-lineage-drow", "elven-lineage-high-elf", "elven-lineage-wood-elf"],
            "mechanics": {"keen_senses_skill_choice": ["Insight", "Perception", "Survival"],
                          "speed_by_subspecies": {"elven-lineage-wood-elf": 35},
                          "lineage_spells": {"elven-lineage-drow": {1: ["dancing-lights"], 3: ["faerie-fire"], 5: ["darkness"]},
                                             "elven-lineage-high-elf": {1: ["prestidigitation"], 3: ["detect-magic"], 5: ["misty-step"]},
                                             "elven-lineage-wood-elf": {1: ["druidcraft"], 3: ["longstrider"], 5: ["pass-without-trace"]}}}},
    "gnome": {"name": "Gnome", "speed": 30, "size": "Small", "resistances": [],
              "traits": ["Darkvision (60 ft.)", "Gnomish Cunning", "Gnomish Lineage"],
              "subspecies": ["gnomish-lineage-forest-gnome", "gnomish-lineage-rock-gnome"],
              "mechanics": {"mental_save_adv": ["INT", "WIS", "CHA"],
                            "lineage_spells": {"gnomish-lineage-forest-gnome": {1: ["minor-illusion"]},
                                               "gnomish-lineage-rock-gnome": {1: ["mending", "prestidigitation"]}}}},
    "goliath": {"name": "Goliath", "speed": 35, "size": "Medium", "resistances": [],
                "traits": ["Giant Ancestry", "Large Form", "Powerful Build"],
                "subspecies": ["giant-ancestry-clouds-jaunt", "giant-ancestry-fires-burn", "giant-ancestry-frosts-chill",
                               "giant-ancestry-hills-tumble", "giant-ancestry-stones-endurance", "giant-ancestry-storms-thunder"],
                "mechanics": {"giant_ancestry_uses": "PROF",
                              "giant_ancestry": {"giant-ancestry-clouds-jaunt": "bonus action: teleport 30 ft",
                                                 "giant-ancestry-fires-burn": "on hit: +1d10 fire",
                                                 "giant-ancestry-frosts-chill": "on hit: +1d6 cold and -10 ft speed",
                                                 "giant-ancestry-hills-tumble": "on hit: knock a Large or smaller target prone",
                                                 "giant-ancestry-stones-endurance": "reaction: reduce damage by 1d12 + CON",
                                                 "giant-ancestry-storms-thunder": "reaction: 1d8 thunder to an attacker within 60 ft"},
                              "large_form_level": 5}},
    "halfling": {"name": "Halfling", "speed": 30, "size": "Small", "resistances": [],
                 "traits": ["Brave", "Halfling Nimbleness", "Luck", "Naturally Stealthy"],
                 "subspecies": [], "mechanics": {"lucky": True, "fear_save_adv": True}},
    "human": {"name": "Human", "speed": 30, "size": "Medium", "resistances": [],
              "traits": ["Resourceful", "Skillful", "Versatile"],
              "subspecies": [], "mechanics": {"heroic_inspiration_on_long_rest": True, "extra_skill": 1, "extra_origin_feat": True}},
    "orc": {"name": "Orc", "speed": 30, "size": "Medium", "resistances": [],
            "traits": ["Adrenaline Rush", "Darkvision (120 ft.)", "Relentless Endurance"],
            "subspecies": [], "mechanics": {"relentless": True, "adrenaline_rush_uses": "PROF"}},
    "tiefling": {"name": "Tiefling", "speed": 30, "size": "Medium", "resistances": [],
                 "traits": ["Darkvision (60 ft.)", "Fiendish Legacy", "Otherworldly Presence"],
                 "subspecies": ["fiendish-legacy-abyssal", "fiendish-legacy-chthonic", "fiendish-legacy-infernal"],
                 "mechanics": {"size_choice": ["Small", "Medium"],
                               "resist_by_subspecies": {"fiendish-legacy-abyssal": ["poison"],
                                                        "fiendish-legacy-chthonic": ["necrotic"],
                                                        "fiendish-legacy-infernal": ["fire"]},
                               "lineage_spells": {"fiendish-legacy-abyssal": {1: ["poison-spray"], 3: ["ray-of-sickness"], 5: ["hold-person"]},
                                                  "fiendish-legacy-chthonic": {1: ["chill-touch"], 3: ["false-life"], 5: ["ray-of-enfeeblement"]},
                                                  "fiendish-legacy-infernal": {1: ["fire-bolt"], 3: ["hellish-rebuke"], 5: ["darkness"]}},
                               "always_cantrips": ["thaumaturgy"]}},
}

# ── spell class lists (the 2024 dataset has no class field) ─────────────────
_SPELL_CLASSES_MANUAL = {
    "arcane-vigor": ["Sorcerer", "Wizard"], "arcanist-s-magic-aura": ["Wizard"], "aura-of-life": ["Cleric", "Paladin"],
    "befuddlement": ["Bard", "Druid", "Warlock", "Wizard"], "charm-monster": ["Bard", "Druid", "Sorcerer", "Warlock", "Wizard"],
    "chromatic-orb": ["Sorcerer", "Wizard"], "dissonant-whispers": ["Bard"], "divine-smite": ["Paladin"],
    "dragon-s-breath": ["Sorcerer", "Wizard"], "elementalism": ["Druid", "Sorcerer", "Wizard"],
    "ensnaring-strike": ["Ranger"], "hex": ["Warlock"], "hunter-s-mark": ["Ranger"],
    "ice-knife": ["Druid", "Sorcerer", "Wizard"], "magical-berries": ["Druid", "Ranger"],
    "mind-spike": ["Sorcerer", "Warlock", "Wizard"], "phantasmal-force": ["Bard", "Sorcerer", "Wizard"],
    "power-word-heal": ["Bard", "Cleric"], "ray-of-sickness": ["Sorcerer", "Wizard"],
    "searing-smite": ["Paladin"], "shining-smite": ["Paladin"], "sorcerous-burst": ["Sorcerer"],
    "starry-wisp": ["Bard", "Druid"], "summon-dragon": ["Wizard"], "tsunami": ["Druid"],
    "vitriolic-sphere": ["Sorcerer", "Wizard"], "divine-favor": ["Paladin"],
}


def _norm(s: str) -> str:
    return "".join(ch for ch in (s or "").lower() if ch.isalnum())


def _build_spell_classes() -> dict:
    by_index = {s["index"]: s.get("classes") or [] for s in _data_2014()["spells"]}
    by_name = {_norm(s["name"]): s.get("classes") or [] for s in _data_2014()["spells"]}
    out = {}
    for s in _data_2024()["spells"]:
        cl = _SPELL_CLASSES_MANUAL.get(s["index"]) or by_index.get(s["index"]) or by_name.get(_norm(s["name"])) or []
        out[s["index"]] = sorted(set(cl))
    return out


try:
    SPELL_CLASSES_2024 = _build_spell_classes()
except FileNotFoundError:
    SPELL_CLASSES_2024 = dict(_SPELL_CLASSES_MANUAL)

# ── spell effects (2024 versions) ───────────────────────────────────────────
SPELL_EFFECTS_2024: dict[str, dict] = copy.deepcopy(SPELL_EFFECTS)
SPELL_EFFECTS_2024.pop("hunters-mark", None)
SPELL_EFFECTS_2024.update({
    "hunter-s-mark": {"kind": "mark", "range": 90, "dice": "1d6", "type": "force", "bonus": True, "concentration": True},
    "hex": {"kind": "mark", "range": 90, "dice": "1d6", "type": "necrotic", "bonus": True, "concentration": True},
    "cure-wounds": {"kind": "heal", "range": 5, "dice": "2d8", "upcast": "2d8"},
    "healing-word": {"kind": "heal", "range": 60, "dice": "2d4", "upcast": "2d4", "bonus": True},
    "mass-healing-word": {"kind": "heal", "range": 60, "dice": "2d4", "upcast": "1d4", "bonus": True, "multi": 6},
    "mass-cure-wounds": {"kind": "heal", "range": 60, "dice": "5d8", "upcast": "1d8", "multi": 6},
    "sleep": {"kind": "save_condition", "save": "WIS", "range": 60, "area": {"shape": "sphere", "size_ft": 5},
              "condition": "Unconscious", "concentration": True},
    "spiritual-weapon": {"kind": "summon_weapon", "range": 60, "dice": "1d8", "type": "force", "bonus": True,
                         "concentration": True},
    "chill-touch": {"kind": "attack", "range": 5, "dice": "1d10", "type": "necrotic", "cantrip": True},
    "acid-splash": {"kind": "save", "save": "DEX", "range": 60, "area": {"shape": "sphere", "size_ft": 5}, "dice": "1d6",
                    "type": "acid", "half": False, "cantrip": True},
    "poison-spray": {"kind": "attack", "range": 30, "dice": "1d12", "type": "poison", "cantrip": True},
    "produce-flame": {"kind": "attack", "range": 60, "dice": "1d8", "type": "fire", "cantrip": True},
    "vicious-mockery": {"kind": "save", "save": "WIS", "range": 60, "dice": "1d6", "type": "psychic", "half": False,
                        "fail_condition": "Mocked", "cantrip": True},
    # 2024-only combat spells
    "sorcerous-burst": {"kind": "attack", "range": 120, "dice": "1d8", "type": "fire", "cantrip": True},
    "starry-wisp": {"kind": "attack", "range": 60, "dice": "1d8", "type": "radiant", "cantrip": True},
    "chromatic-orb": {"kind": "attack", "range": 90, "dice": "3d8", "type": "fire", "upcast": "1d8"},
    "ice-knife": {"kind": "attack", "range": 60, "dice": "1d10", "type": "piercing"},
    "ray-of-sickness": {"kind": "attack", "range": 60, "dice": "2d8", "type": "poison", "upcast": "1d8", "on_hit_condition": "Poisoned"},
    "dissonant-whispers": {"kind": "save", "save": "WIS", "range": 60, "dice": "3d6", "type": "psychic", "half": True, "upcast": "1d6"},
    "mind-spike": {"kind": "save", "save": "WIS", "range": 120, "dice": "3d8", "type": "psychic", "half": True, "upcast": "1d8",
                   "concentration": True},
    "vitriolic-sphere": {"kind": "save", "save": "DEX", "range": 150, "area": {"shape": "sphere", "size_ft": 20}, "dice": "10d4",
                         "type": "acid", "half": True, "upcast": "2d4"},
    "ice-storm": {"kind": "save", "save": "DEX", "range": 300, "area": {"shape": "sphere", "size_ft": 20}, "dice": "5d8",
                  "type": "cold", "half": True, "upcast": "1d8"},
    "flame-strike": {"kind": "save", "save": "DEX", "range": 60, "area": {"shape": "sphere", "size_ft": 10}, "dice": "10d6",
                     "type": "fire", "half": True, "upcast": "1d6"},  # 5d6 fire + 5d6 radiant, folded
})


def _prune_effects() -> None:
    try:
        have = {s["index"] for s in _data_2024()["spells"]}
    except FileNotFoundError:
        return
    for k in list(SPELL_EFFECTS_2024):
        if k not in have:
            SPELL_EFFECTS_2024.pop(k)


_prune_effects()


def max_spell_level_2024(cls_key: str, level: int) -> int:
    sc = CLASSES_2024[cls_key]["spellcasting"]
    if not sc:
        return 0
    t = sc["type"]
    if t == "full":
        return max(int(k) for k in FULL_CASTER_SLOTS_2024[level])
    if t == "half":
        return max((int(k) for k in HALF_CASTER_SLOTS_2024[level]), default=0)
    if t == "pact":
        return PACT_SLOTS_2024[level][1]
    return 0


__all__ = ["CLASSES_2024", "BACKGROUNDS_2024", "FEATS_2024", "SPECIES_2024", "MASTERY", "MASTERY_BY_ITEM",
           "MASTERY_DESCRIPTIONS", "ITEM_ALIASES_2024", "SPELL_EFFECTS_2024", "SPELL_CLASSES_2024",
           "FIGHTING_STYLES_2024", "HALF_CASTER_SLOTS_2024", "FULL_CASTER_SLOTS_2024", "PACT_SLOTS_2024",
           "ASI_LEVELS_2024", "MAX_LEVEL_2024", "max_spell_level_2024", "ABILITIES"]
