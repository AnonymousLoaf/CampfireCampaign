"""Class, race, background and spell-effect data (levels 1-10, all 12 SRD 5.1 classes — the 2014 rules).

The 2024 rules (SRD 5.2) live in classes_2024.py with the same schema.

Feature `uses` specs: an int, "CHA", "CHA+1", "LEVEL", "LOH" (5 × level), "PROF" (proficiency bonus), or a
level table {level: value} — use the value for the highest key ≤ the character's level.

Class mechanics follow the 5e SRD 5.1 (one SRD subclass per class). Feature descriptions
are short paraphrases. Spells listed in SPELL_EFFECTS are resolved by code in combat;
any other spell is "utility" and adjudicated by the DM.
"""
from __future__ import annotations

ABILITIES = ["STR", "DEX", "CON", "INT", "WIS", "CHA"]

SKILLS = {
    "Acrobatics": "DEX", "Animal Handling": "WIS", "Arcana": "INT", "Athletics": "STR",
    "Deception": "CHA", "History": "INT", "Insight": "WIS", "Intimidation": "CHA",
    "Investigation": "INT", "Medicine": "WIS", "Nature": "INT", "Perception": "WIS",
    "Performance": "CHA", "Persuasion": "CHA", "Religion": "INT", "Sleight of Hand": "DEX",
    "Stealth": "DEX", "Survival": "WIS",
}
ALL_SKILLS = list(SKILLS)

PROF_BONUS = {1: 2, 2: 2, 3: 2, 4: 2, 5: 3, 6: 3, 7: 3, 8: 3, 9: 4, 10: 4, 11: 4}
XP_THRESHOLDS = {1: 0, 2: 300, 3: 900, 4: 2700, 5: 6500, 6: 14000, 7: 23000, 8: 34000, 9: 48000, 10: 64000,
                 11: 85000}
MAX_LEVEL = 10

LIGHT_ARMOR = {"padded-armor", "leather-armor", "studded-leather-armor"}
MEDIUM_ARMOR = {"hide-armor", "chain-shirt", "scale-mail", "breastplate", "half-plate-armor"}
HEAVY_ARMOR = {"ring-mail", "chain-mail", "splint-armor", "plate-armor"}

EXPLORER_GEAR = [("backpack", 1), ("bedroll", 1), ("rations-1-day", 5), ("torch", 5),
                 ("rope-hempen-50-feet", 1), ("waterskin", 1), ("tinderbox", 1)]
SCHOLAR_GEAR = [("backpack", 1), ("book", 1), ("ink-1-ounce-bottle", 1), ("ink-pen", 1),
                ("parchment-one-sheet", 5), ("rations-1-day", 3), ("waterskin", 1)]
PRIEST_GEAR = [("backpack", 1), ("blanket", 1), ("candle", 5), ("tinderbox", 1), ("rations-1-day", 3),
               ("waterskin", 1), ("vestments", 1)]

# Spell slots by caster type and character level
FULL_CASTER_SLOTS = {
    1: {"1": 2}, 2: {"1": 3}, 3: {"1": 4, "2": 2}, 4: {"1": 4, "2": 3}, 5: {"1": 4, "2": 3, "3": 2},
    6: {"1": 4, "2": 3, "3": 3}, 7: {"1": 4, "2": 3, "3": 3, "4": 1}, 8: {"1": 4, "2": 3, "3": 3, "4": 2},
    9: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 1}, 10: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 2},
}
HALF_CASTER_SLOTS = {
    1: {}, 2: {"1": 2}, 3: {"1": 3}, 4: {"1": 3}, 5: {"1": 4, "2": 2}, 6: {"1": 4, "2": 2},
    7: {"1": 4, "2": 3}, 8: {"1": 4, "2": 3}, 9: {"1": 4, "2": 3, "3": 2}, 10: {"1": 4, "2": 3, "3": 2},
}
PACT_SLOTS = {1: (1, 1), 2: (2, 1), 3: (2, 2), 4: (2, 2), 5: (2, 3), 6: (2, 3), 7: (2, 4), 8: (2, 4),
              9: (2, 5), 10: (2, 5)}  # (slots, slot level)

FIGHTING_STYLES = {
    "Archery": "+2 to attack rolls with ranged weapons.",
    "Defense": "+1 AC while wearing armor.",
    "Dueling": "+2 damage with a one-handed melee weapon and no other weapon.",
    "Great Weapon Fighting": "Reroll 1s and 2s on damage dice with two-handed melee weapons.",
}

DRAGON_ANCESTRIES = [
    {"name": "Black", "damage_type": "acid", "shape": "line"}, {"name": "Blue", "damage_type": "lightning", "shape": "line"},
    {"name": "Brass", "damage_type": "fire", "shape": "line"}, {"name": "Bronze", "damage_type": "lightning", "shape": "line"},
    {"name": "Copper", "damage_type": "acid", "shape": "line"}, {"name": "Gold", "damage_type": "fire", "shape": "cone"},
    {"name": "Green", "damage_type": "poison", "shape": "cone"}, {"name": "Red", "damage_type": "fire", "shape": "cone"},
    {"name": "Silver", "damage_type": "cold", "shape": "cone"}, {"name": "White", "damage_type": "cold", "shape": "cone"},
]

RACE_EXTRAS = {
    "half-elf": {"ability_choices": {"count": 2, "amount": 1, "exclude": ["CHA"]}},
    "dragonborn": {"ancestries": DRAGON_ANCESTRIES},
}
RACE_RESISTANCES = {"dwarf": ["poison"], "tiefling": ["fire"]}


def F(name: str, description: str, uses: dict | None = None) -> dict:
    d = {"name": name, "description": description}
    if uses:
        d["uses"] = uses
    return d


ASI = F("Ability Score Improvement", "Increase one ability score by 2, or two by 1 (max 20).")

CLASSES: dict[str, dict] = {
    "barbarian": {
        "index": "barbarian", "name": "Barbarian", "hit_die": 12, "saves": ["STR", "CON"], "primary": ["STR", "CON"],
        "description": "A fierce warrior of primal rage who shrugs off blows that would fell others.",
        "skill_choices": {"count": 2, "options": ["Animal Handling", "Athletics", "Intimidation", "Nature", "Perception", "Survival"]},
        "armor": ["Light", "Medium", "Shields"], "weapons": ["Simple", "Martial"],
        "weapon_cats": {"simple", "martial"}, "weapon_extra": set(),
        "equipment_options": [
            {"id": "reaver", "label": "Greataxe, two handaxes, four javelins",
             "items": [("greataxe", 1, True), ("handaxe", 2, False), ("javelin", 4, False)]},
            {"id": "raider", "label": "Battleaxe, shield, four javelins",
             "items": [("battleaxe", 1, True), ("shield", 1, True), ("javelin", 4, False)]},
        ],
        "gear": EXPLORER_GEAR,
        "subclass_level": 3, "subclasses": [{"index": "berserker", "name": "Path of the Berserker",
                                              "description": "Frenzy: while raging, make a melee attack as a bonus action."}],
        "features": {
            1: [F("Rage", "Bonus action: +2 melee damage, resistance to bludgeoning, piercing and slashing damage, advantage on Strength checks. Lasts the fight.", {"max": 2, "per": "long"}),
                F("Unarmored Defense", "Without armor, AC = 10 + DEX + CON (a shield still counts).")],
            2: [F("Reckless Attack", "Attack with advantage on your melee attacks this turn; attacks against you have advantage until your next turn."),
                F("Danger Sense", "Advantage on Dexterity saving throws against effects you can see.")],
            3: [F("Frenzy", "While raging, you can make one melee weapon attack as a bonus action.")],
            4: [ASI],
            5: [F("Extra Attack", "Attack twice when you take the Attack action."),
                F("Fast Movement", "+10 ft speed while not wearing heavy armor.")],
        },
        "spellcasting": None,
    },
    "bard": {
        "index": "bard", "name": "Bard", "hit_die": 8, "saves": ["DEX", "CHA"], "primary": ["CHA", "DEX"],
        "description": "An inspiring magician whose words and music weave magic and lift allies.",
        "skill_choices": {"count": 3, "options": ALL_SKILLS},
        "armor": ["Light"], "weapons": ["Simple", "Hand crossbows", "Longswords", "Rapiers", "Shortswords"],
        "weapon_cats": {"simple"}, "weapon_extra": {"crossbow-hand", "longsword", "rapier", "shortsword"},
        "equipment_options": [
            {"id": "duelist", "label": "Rapier, leather armor, dagger", "items": [("rapier", 1, True), ("leather-armor", 1, True), ("dagger", 1, False)]},
            {"id": "minstrel", "label": "Longsword, leather armor, dagger", "items": [("longsword", 1, True), ("leather-armor", 1, True), ("dagger", 1, False)]},
        ],
        "gear": EXPLORER_GEAR,
        "subclass_level": 3, "subclasses": [{"index": "lore", "name": "College of Lore",
                                              "description": "Bonus proficiencies and Cutting Words."}],
        "features": {
            1: [F("Bardic Inspiration", "Bonus action: give an ally within 60 ft an Inspiration die (d6) to add to one attack roll, check or save.", {"max": "CHA", "per": "long"})],
            2: [F("Jack of All Trades", "Add half your proficiency bonus to checks you aren't proficient in."),
                F("Song of Rest", "Allies who spend hit dice during your short rest regain an extra 1d6 HP.")],
            3: [F("Expertise", "Double proficiency for two more skills."),
                F("Cutting Words", "Use Bardic Inspiration to reduce an enemy's roll (narrated).")],
            4: [ASI],
            5: [F("Font of Inspiration", "Bardic Inspiration recovers on a short rest and becomes a d8.")],
        },
        "spellcasting": {"ability": "CHA", "type": "full", "list": "Bard", "known": True, "prepares": False,
                         "cantrips_known": {1: 2, 2: 2, 3: 2, 4: 3, 5: 3}, "spells_known": {1: 4, 2: 5, 3: 6, 4: 7, 5: 8}},
    },
    "cleric": {
        "index": "cleric", "name": "Cleric", "hit_die": 8, "saves": ["WIS", "CHA"], "primary": ["WIS", "CON"],
        "description": "A priestly champion who wields divine magic in service of a higher power (Life domain).",
        "skill_choices": {"count": 2, "options": ["History", "Insight", "Medicine", "Persuasion", "Religion"]},
        "armor": ["Light", "Medium", "Heavy (Life domain)", "Shields"], "weapons": ["Simple"],
        "weapon_cats": {"simple"}, "weapon_extra": set(),
        "equipment_options": [
            {"id": "warpriest", "label": "Mace, chain mail, shield, holy symbol",
             "items": [("mace", 1, True), ("chain-mail", 1, True), ("shield", 1, True), ("amulet", 1, False)]},
            {"id": "pilgrim", "label": "Mace, scale mail, shield, light crossbow and 20 bolts, holy symbol",
             "items": [("mace", 1, True), ("scale-mail", 1, True), ("shield", 1, True),
                       ("crossbow-light", 1, False), ("crossbow-bolt", 20, False), ("amulet", 1, False)]},
        ],
        "gear": PRIEST_GEAR,
        "subclass_level": 1, "subclasses": [{"index": "life", "name": "Life Domain",
                                              "description": "Heavy armor; your healing spells heal more."}],
        "features": {
            1: [F("Spellcasting", "You prepare cleric spells each day (WIS mod + level) and cast them with Wisdom."),
                F("Disciple of Life", "Your healing spells restore an extra 2 + the spell's level hit points.")],
            2: [F("Channel Divinity", "Turn Undead, or Preserve Life (heal 5 × your level split among allies within 30 ft).", {"max": 1, "per": "short"})],
            3: [],
            4: [ASI],
            5: [F("Destroy Undead", "Turned undead of CR 1/2 or lower are destroyed.")],
        },
        "spellcasting": {"ability": "WIS", "type": "full", "list": "Cleric", "known": False, "prepares": True,
                         "cantrips_known": {1: 3, 2: 3, 3: 3, 4: 4, 5: 4},
                         "always": {1: ["bless", "cure-wounds"], 3: ["lesser-restoration", "spiritual-weapon"],
                                    5: ["beacon-of-hope", "revivify"]}},
    },
    "druid": {
        "index": "druid", "name": "Druid", "hit_die": 8, "saves": ["INT", "WIS"], "primary": ["WIS", "CON"],
        "description": "A priest of the Old Faith who wields the powers of nature (Circle of the Land).",
        "skill_choices": {"count": 2, "options": ["Arcana", "Animal Handling", "Insight", "Medicine", "Nature", "Perception", "Religion", "Survival"]},
        "armor": ["Light", "Medium", "Shields (non-metal)"],
        "weapons": ["Clubs", "Daggers", "Darts", "Javelins", "Maces", "Quarterstaffs", "Scimitars", "Sickles", "Slings", "Spears"],
        "weapon_cats": set(), "weapon_extra": {"club", "dagger", "dart", "javelin", "mace", "quarterstaff", "scimitar", "sickle", "sling", "spear"},
        "equipment_options": [
            {"id": "warden", "label": "Scimitar, leather armor, wooden shield, druidic focus",
             "items": [("scimitar", 1, True), ("leather-armor", 1, True), ("shield", 1, True), ("sprig-of-mistletoe", 1, False)]},
            {"id": "wanderer", "label": "Quarterstaff, leather armor, druidic focus",
             "items": [("quarterstaff", 1, True), ("leather-armor", 1, True), ("totem", 1, False)]},
        ],
        "gear": EXPLORER_GEAR,
        "subclass_level": 2, "subclasses": [{"index": "land", "name": "Circle of the Land",
                                              "description": "Bonus cantrip and Natural Recovery of spell slots."}],
        "features": {
            1: [F("Druidic", "You know the secret language of druids."),
                F("Spellcasting", "You prepare druid spells each day (WIS mod + level) and cast them with Wisdom.")],
            2: [F("Wild Shape", "Transform into a beast you have seen (CR 1/4, no flying or swimming). Describe it to the DM.", {"max": 2, "per": "short"}),
                F("Natural Recovery", "Once a day after a short rest, recover spell slots (narrated).")],
            3: [], 4: [ASI], 5: [],
        },
        "spellcasting": {"ability": "WIS", "type": "full", "list": "Druid", "known": False, "prepares": True,
                         "cantrips_known": {1: 2, 2: 3, 3: 3, 4: 4, 5: 4}},
    },
    "fighter": {
        "index": "fighter", "name": "Fighter", "hit_die": 10, "saves": ["STR", "CON"], "primary": ["STR", "DEX"],
        "description": "A master of weapons and armour who wins fights through skill, grit and stamina.",
        "skill_choices": {"count": 2, "options": ["Acrobatics", "Animal Handling", "Athletics", "History",
                                                   "Insight", "Intimidation", "Perception", "Survival"]},
        "armor": ["Light", "Medium", "Heavy", "Shields"], "weapons": ["Simple", "Martial"],
        "weapon_cats": {"simple", "martial"}, "weapon_extra": set(),
        "fighting_style_level": 1,
        "equipment_options": [
            {"id": "defender", "label": "Chain mail, longsword, shield, light crossbow and 20 bolts",
             "items": [("chain-mail", 1, True), ("longsword", 1, True), ("shield", 1, True),
                       ("crossbow-light", 1, False), ("crossbow-bolt", 20, False)], "fighting_style": "Defense"},
            {"id": "archer", "label": "Leather armor, longbow and 20 arrows, two shortswords",
             "items": [("leather-armor", 1, True), ("longbow", 1, True), ("arrow", 20, False), ("shortsword", 2, True)],
             "fighting_style": "Archery"},
            {"id": "brute", "label": "Chain mail, greatsword, two handaxes",
             "items": [("chain-mail", 1, True), ("greatsword", 1, True), ("handaxe", 2, False)],
             "fighting_style": "Great Weapon Fighting"},
        ],
        "gear": EXPLORER_GEAR,
        "subclass_level": 3, "subclasses": [{"index": "champion", "name": "Champion",
                                              "description": "Improved Critical: crit on 19-20."}],
        "features": {
            1: [F("Fighting Style", "You adopt a style of fighting."),
                F("Second Wind", "Bonus action: regain 1d10 + fighter level hit points.", {"max": 1, "per": "short"})],
            2: [F("Action Surge", "On your turn, take one additional action.", {"max": 1, "per": "short"})],
            3: [F("Improved Critical", "Your weapon attacks score a critical hit on a roll of 19 or 20.")],
            4: [ASI],
            5: [F("Extra Attack", "Attack twice when you take the Attack action.")],
        },
        "spellcasting": None,
    },
    "monk": {
        "index": "monk", "name": "Monk", "hit_die": 8, "saves": ["STR", "DEX"], "primary": ["DEX", "WIS"],
        "description": "A master of martial arts who harnesses ki to strike with speed and precision.",
        "skill_choices": {"count": 2, "options": ["Acrobatics", "Athletics", "History", "Insight", "Religion", "Stealth"]},
        "armor": [], "weapons": ["Simple", "Shortswords"], "weapon_cats": {"simple"}, "weapon_extra": {"shortsword"},
        "equipment_options": [
            {"id": "blade", "label": "Shortsword and 10 darts", "items": [("shortsword", 1, True), ("dart", 10, False)]},
            {"id": "spear", "label": "Spear and 10 darts", "items": [("spear", 1, True), ("dart", 10, False)]},
        ],
        "gear": EXPLORER_GEAR,
        "subclass_level": 3, "subclasses": [{"index": "open-hand", "name": "Way of the Open Hand",
                                              "description": "Flurry of Blows can knock foes prone or push them."}],
        "features": {
            1: [F("Unarmored Defense", "Without armor or shield, AC = 10 + DEX + WIS."),
                F("Martial Arts", "Use DEX for monk weapons and unarmed strikes (d4, d6 at 5th); after attacking, make an unarmed strike as a bonus action.")],
            2: [F("Ki", "Spend ki on Flurry of Blows, Patient Defense or Step of the Wind.", {"max": "LEVEL", "per": "short"}),
                F("Unarmored Movement", "+10 ft speed without armor or shield.")],
            3: [F("Open Hand Technique", "Flurry of Blows hits can knock the target prone."),
                F("Deflect Missiles", "Reduce ranged weapon damage against you (narrated).")],
            4: [ASI, F("Slow Fall", "Reduce falling damage by 5 × your level.")],
            5: [F("Extra Attack", "Attack twice when you take the Attack action."),
                F("Stunning Strike", "Spend 1 ki when you hit with a melee attack: the target makes a CON save or is stunned until the end of your next turn.")],
        },
        "spellcasting": None,
    },
    "paladin": {
        "index": "paladin", "name": "Paladin", "hit_die": 10, "saves": ["WIS", "CHA"], "primary": ["STR", "CHA"],
        "description": "A holy warrior bound to a sacred oath (Oath of Devotion).",
        "skill_choices": {"count": 2, "options": ["Athletics", "Insight", "Intimidation", "Medicine", "Persuasion", "Religion"]},
        "armor": ["Light", "Medium", "Heavy", "Shields"], "weapons": ["Simple", "Martial"],
        "weapon_cats": {"simple", "martial"}, "weapon_extra": set(), "fighting_style_level": 2,
        "equipment_options": [
            {"id": "knight", "label": "Longsword, shield, chain mail, five javelins, holy symbol",
             "items": [("longsword", 1, True), ("shield", 1, True), ("chain-mail", 1, True), ("javelin", 5, False), ("emblem", 1, False)]},
            {"id": "crusader", "label": "Greatsword, chain mail, five javelins, holy symbol",
             "items": [("greatsword", 1, True), ("chain-mail", 1, True), ("javelin", 5, False), ("emblem", 1, False)]},
        ],
        "gear": PRIEST_GEAR,
        "subclass_level": 3, "subclasses": [{"index": "devotion", "name": "Oath of Devotion",
                                              "description": "Sacred Weapon: add CHA to attack rolls."}],
        "features": {
            1: [F("Divine Sense", "Sense celestials, fiends and undead nearby (narrated).", {"max": "CHA+1", "per": "long"}),
                F("Lay on Hands", "Action: heal from a pool of 5 × your level hit points.", {"max": "LOH", "per": "long"})],
            2: [F("Fighting Style", "You adopt a style of fighting."),
                F("Spellcasting", "You prepare paladin spells (CHA mod + half your level) and cast them with Charisma."),
                F("Divine Smite", "When you hit with a melee weapon, spend a spell slot for +2d8 radiant (+1d8 per slot level above 1st, +1d8 vs undead or fiends).")],
            3: [F("Divine Health", "Immune to disease."),
                F("Channel Divinity", "Sacred Weapon: add your CHA modifier to attack rolls for the fight.", {"max": 1, "per": "short"})],
            4: [ASI],
            5: [F("Extra Attack", "Attack twice when you take the Attack action.")],
        },
        "spellcasting": {"ability": "CHA", "type": "half", "list": "Paladin", "known": False, "prepares": True,
                         "cantrips_known": {}, "always": {3: ["protection-from-evil-and-good", "sanctuary"],
                                                         5: ["lesser-restoration", "zone-of-truth"]}},
    },
    "ranger": {
        "index": "ranger", "name": "Ranger", "hit_die": 10, "saves": ["STR", "DEX"], "primary": ["DEX", "WIS"],
        "description": "A warrior of the wilds who hunts the monsters that threaten civilisation (Hunter).",
        "skill_choices": {"count": 3, "options": ["Animal Handling", "Athletics", "Insight", "Investigation", "Nature", "Perception", "Stealth", "Survival"]},
        "armor": ["Light", "Medium", "Shields"], "weapons": ["Simple", "Martial"],
        "weapon_cats": {"simple", "martial"}, "weapon_extra": set(), "fighting_style_level": 2,
        "equipment_options": [
            {"id": "stalker", "label": "Scale mail, two shortswords, longbow and 20 arrows",
             "items": [("scale-mail", 1, True), ("shortsword", 2, True), ("longbow", 1, True), ("arrow", 20, False)]},
            {"id": "scout", "label": "Leather armor, two shortswords, longbow and 20 arrows",
             "items": [("leather-armor", 1, True), ("shortsword", 2, True), ("longbow", 1, True), ("arrow", 20, False)]},
        ],
        "gear": EXPLORER_GEAR,
        "subclass_level": 3, "subclasses": [{"index": "hunter", "name": "Hunter",
                                              "description": "Colossus Slayer: +1d8 once per turn against a wounded target."}],
        "features": {
            1: [F("Favored Enemy", "Advantage on tracking and recalling lore about your favoured foes."),
                F("Natural Explorer", "You travel and forage well in your favoured terrain.")],
            2: [F("Fighting Style", "You adopt a style of fighting."),
                F("Spellcasting", "You know ranger spells and cast them with Wisdom.")],
            3: [F("Colossus Slayer", "Once per turn, +1d8 damage to a creature below its hit point maximum."),
                F("Primeval Awareness", "Sense nearby aberrations, dragons, fiends and undead (narrated).")],
            4: [ASI],
            5: [F("Extra Attack", "Attack twice when you take the Attack action.")],
        },
        "spellcasting": {"ability": "WIS", "type": "half", "list": "Ranger", "known": True, "prepares": False,
                         "cantrips_known": {}, "spells_known": {1: 0, 2: 2, 3: 3, 4: 3, 5: 4}},
    },
    "rogue": {
        "index": "rogue", "name": "Rogue", "hit_die": 8, "saves": ["DEX", "INT"], "primary": ["DEX", "CON"],
        "description": "A scoundrel who uses stealth and trickery to find the weak spot and strike it.",
        "skill_choices": {"count": 4, "options": ["Acrobatics", "Athletics", "Deception", "Insight", "Intimidation",
                                                   "Investigation", "Perception", "Performance", "Persuasion",
                                                   "Sleight of Hand", "Stealth"]},
        "armor": ["Light"], "weapons": ["Simple", "Hand crossbows", "Longswords", "Rapiers", "Shortswords"],
        "weapon_cats": {"simple"}, "weapon_extra": {"crossbow-hand", "longsword", "rapier", "shortsword"},
        "expertise_at_l1": 2,
        "equipment_options": [
            {"id": "duelist", "label": "Rapier, shortbow and 20 arrows, leather armor, two daggers",
             "items": [("rapier", 1, True), ("shortbow", 1, True), ("arrow", 20, False),
                       ("leather-armor", 1, True), ("dagger", 2, False)]},
            {"id": "cutpurse", "label": "Two shortswords, leather armor, two daggers, crowbar, ball bearings",
             "items": [("shortsword", 2, True), ("leather-armor", 1, True), ("dagger", 2, False),
                       ("crowbar", 1, False), ("ball-bearings-bag-of-1000", 1, False)]},
        ],
        "gear": EXPLORER_GEAR,
        "subclass_level": 3, "subclasses": [{"index": "thief", "name": "Thief", "description": "Fast Hands and Second-Story Work."}],
        "features": {
            1: [F("Expertise", "Double proficiency in two of your skills."),
                F("Sneak Attack", "Once per turn, extra damage (1d6, +1d6 at 3rd and 5th) to a finesse or ranged attack with advantage, or when an ally is next to the target."),
                F("Thieves' Cant", "A secret mix of dialect, jargon and code.")],
            2: [F("Cunning Action", "Bonus action on each turn: Dash, Disengage or Hide.")],
            3: [F("Fast Hands", "Use an object or Sleight of Hand as a bonus action."),
                F("Second-Story Work", "Climb at full speed.")],
            4: [ASI],
            5: [F("Uncanny Dodge", "When an attacker you can see hits you, halve the damage (once per round).")],
        },
        "spellcasting": None,
    },
    "sorcerer": {
        "index": "sorcerer", "name": "Sorcerer", "hit_die": 6, "saves": ["CON", "CHA"], "primary": ["CHA", "CON"],
        "description": "A spellcaster with innate magic from a draconic bloodline.",
        "skill_choices": {"count": 2, "options": ["Arcana", "Deception", "Insight", "Intimidation", "Persuasion", "Religion"]},
        "armor": [], "weapons": ["Daggers", "Darts", "Slings", "Quarterstaffs", "Light crossbows"],
        "weapon_cats": set(), "weapon_extra": {"dagger", "dart", "sling", "quarterstaff", "crossbow-light"},
        "equipment_options": [
            {"id": "arbalist", "label": "Light crossbow and 20 bolts, component pouch, two daggers",
             "items": [("crossbow-light", 1, True), ("crossbow-bolt", 20, False), ("component-pouch", 1, False), ("dagger", 2, False)]},
            {"id": "mystic", "label": "Quarterstaff, crystal focus, two daggers",
             "items": [("quarterstaff", 1, True), ("crystal", 1, False), ("dagger", 2, False)]},
        ],
        "gear": EXPLORER_GEAR,
        "subclass_level": 1, "subclasses": [{"index": "draconic", "name": "Draconic Bloodline",
                                              "description": "+1 HP per level; unarmored AC 13 + DEX."}],
        "features": {
            1: [F("Spellcasting", "You know sorcerer spells and cast them with Charisma."),
                F("Draconic Resilience", "+1 hit point per sorcerer level; without armor, AC = 13 + DEX.")],
            2: [F("Font of Magic", "Sorcery points (narrated) to fuel metamagic and slots.", {"max": "LEVEL", "per": "long"})],
            3: [F("Metamagic", "Twist your spells (narrated with the DM).")],
            4: [ASI], 5: [],
        },
        "spellcasting": {"ability": "CHA", "type": "full", "list": "Sorcerer", "known": True, "prepares": False,
                         "cantrips_known": {1: 4, 2: 4, 3: 4, 4: 5, 5: 5}, "spells_known": {1: 2, 2: 3, 3: 4, 4: 5, 5: 6}},
    },
    "warlock": {
        "index": "warlock", "name": "Warlock", "hit_die": 8, "saves": ["WIS", "CHA"], "primary": ["CHA", "CON"],
        "description": "A wielder of magic granted by a pact with a fiendish patron.",
        "skill_choices": {"count": 2, "options": ["Arcana", "Deception", "History", "Intimidation", "Investigation", "Nature", "Religion"]},
        "armor": ["Light"], "weapons": ["Simple"], "weapon_cats": {"simple"}, "weapon_extra": set(),
        "equipment_options": [
            {"id": "hexer", "label": "Light crossbow and 20 bolts, component pouch, leather armor, two daggers",
             "items": [("crossbow-light", 1, True), ("crossbow-bolt", 20, False), ("component-pouch", 1, False),
                       ("leather-armor", 1, True), ("dagger", 2, False)]},
            {"id": "occultist", "label": "Quarterstaff, rod focus, leather armor, two daggers",
             "items": [("quarterstaff", 1, True), ("rod", 1, False), ("leather-armor", 1, True), ("dagger", 2, False)]},
        ],
        "gear": SCHOLAR_GEAR,
        "subclass_level": 1, "subclasses": [{"index": "fiend", "name": "The Fiend",
                                              "description": "Dark One's Blessing: temporary HP when you drop a foe."}],
        "features": {
            1: [F("Pact Magic", "Few spell slots, always cast at the highest level, recovered on a short rest."),
                F("Dark One's Blessing", "When you reduce a hostile creature to 0 HP, gain CHA + warlock level temporary HP.")],
            2: [F("Agonizing Blast", "Add your CHA modifier to Eldritch Blast damage."),
                F("Armor of Shadows", "Cast Mage Armor on yourself at will (narrated).")],
            3: [F("Pact of the Blade", "Summon a pact weapon (narrated).")],
            4: [ASI], 5: [],
        },
        "spellcasting": {"ability": "CHA", "type": "pact", "list": "Warlock", "known": True, "prepares": False,
                         "cantrips_known": {1: 2, 2: 2, 3: 2, 4: 3, 5: 3}, "spells_known": {1: 2, 2: 3, 3: 4, 4: 5, 5: 6}},
    },
    "wizard": {
        "index": "wizard", "name": "Wizard", "hit_die": 6, "saves": ["INT", "WIS"], "primary": ["INT", "CON"],
        "description": "A scholarly magic-user who bends reality with spells from a spellbook (School of Evocation).",
        "skill_choices": {"count": 2, "options": ["Arcana", "History", "Insight", "Investigation", "Medicine", "Religion"]},
        "armor": [], "weapons": ["Daggers", "Darts", "Slings", "Quarterstaffs", "Light crossbows"],
        "weapon_cats": set(), "weapon_extra": {"dagger", "dart", "sling", "quarterstaff", "crossbow-light"},
        "equipment_options": [
            {"id": "scholar", "label": "Quarterstaff, component pouch, spellbook",
             "items": [("quarterstaff", 1, True), ("component-pouch", 1, False), ("spellbook", 1, False)]},
            {"id": "adept", "label": "Two daggers, crystal arcane focus, spellbook",
             "items": [("dagger", 2, True), ("crystal", 1, False), ("spellbook", 1, False)]},
        ],
        "gear": SCHOLAR_GEAR,
        "subclass_level": 2, "subclasses": [{"index": "evocation", "name": "School of Evocation",
                                              "description": "Sculpt Spells: your evocation spells spare allies."}],
        "features": {
            1: [F("Spellcasting", "Your spellbook holds your spells; prepare INT mod + level of them each day."),
                F("Arcane Recovery", "Once a day after a short rest, recover spell slots.", {"max": 1, "per": "long"})],
            2: [F("Sculpt Spells", "Allies are unharmed by your evocation spells.")],
            3: [], 4: [ASI], 5: [],
        },
        "spellcasting": {"ability": "INT", "type": "full", "list": "Wizard", "known": False, "prepares": True,
                         "spellbook": True, "cantrips_known": {1: 3, 2: 3, 3: 3, 4: 4, 5: 4}},
    },
}

# ── levels 6-10 (2014 / SRD 5.1) ────────────────────────────────────────────
# Spell progressions to level 10.
_T = lambda *vals: {i + 1: v for i, v in enumerate(vals)}  # noqa: E731  (level table from a list)
_SPELL_TABLES_2014 = {
    "bard": {"cantrips_known": _T(2, 2, 2, 3, 3, 3, 3, 3, 3, 4), "spells_known": _T(4, 5, 6, 7, 8, 9, 10, 11, 12, 14)},
    "cleric": {"cantrips_known": _T(3, 3, 3, 4, 4, 4, 4, 4, 4, 5)},
    "druid": {"cantrips_known": _T(2, 2, 2, 3, 3, 3, 3, 3, 3, 4)},
    "paladin": {"cantrips_known": {}},
    "ranger": {"cantrips_known": {}, "spells_known": _T(0, 2, 3, 3, 4, 4, 5, 5, 6, 6)},
    "sorcerer": {"cantrips_known": _T(4, 4, 4, 5, 5, 5, 5, 5, 5, 6), "spells_known": _T(2, 3, 4, 5, 6, 7, 8, 9, 10, 11)},
    "warlock": {"cantrips_known": _T(2, 2, 2, 3, 3, 3, 3, 3, 3, 4), "spells_known": _T(2, 3, 4, 5, 6, 7, 8, 9, 10, 10)},
    "wizard": {"cantrips_known": _T(3, 3, 3, 4, 4, 4, 4, 4, 4, 5)},
}
for _k, _tables in _SPELL_TABLES_2014.items():
    CLASSES[_k]["spellcasting"].update(_tables)

# Domain / oath spells (always prepared) through level 9.
CLASSES["cleric"]["spellcasting"]["always"] = {
    1: ["bless", "cure-wounds"], 3: ["lesser-restoration", "spiritual-weapon"], 5: ["beacon-of-hope", "revivify"],
    7: ["death-ward", "guardian-of-faith"], 9: ["mass-cure-wounds", "raise-dead"]}
CLASSES["paladin"]["spellcasting"]["always"] = {
    3: ["protection-from-evil-and-good", "sanctuary"], 5: ["lesser-restoration", "zone-of-truth"],
    9: ["beacon-of-hope", "dispel-magic"]}

# Scaling uses (level tables).
CLASSES["barbarian"]["features"][1][0]["uses"]["max"] = {1: 2, 3: 3, 6: 4}          # Rage
CLASSES["cleric"]["features"][2][0]["uses"]["max"] = {2: 1, 6: 2}                   # Channel Divinity

_FEATURES_6_10: dict[str, dict[int, list[dict]]] = {
    "barbarian": {
        6: [F("Mindless Rage", "While raging you can't be charmed or frightened; such effects are suspended.")],
        7: [F("Feral Instinct", "Advantage on initiative rolls; you can act normally on a surprise round if you rage first.")],
        8: [ASI],
        9: [F("Brutal Critical", "Roll one additional weapon damage die when you score a critical hit with a melee attack.")],
        10: [F("Intimidating Presence", "Action: frighten a creature within 30 ft (WIS save) until the end of your next turn.")],
    },
    "bard": {
        6: [F("Countercharm", "Action: allies within 30 ft have advantage on saves against being charmed or frightened."),
            F("Additional Magical Secrets", "Learn two spells from any class's list (counted as bard spells).")],
        7: [],
        8: [ASI],
        9: [F("Song of Rest (d8)", "Your Song of Rest die becomes a d8.")],
        10: [F("Expertise (more)", "Double proficiency for two more skills."),
             F("Magical Secrets", "Learn two spells from any class's list."),
             F("Bardic Inspiration (d10)", "Your Bardic Inspiration die becomes a d10.")],
    },
    "cleric": {
        6: [F("Blessed Healer", "When you cast a healing spell on someone else, you regain 2 + the spell's level hit points.")],
        7: [],
        8: [ASI, F("Divine Strike", "Once per turn, a weapon hit deals an extra 1d8 radiant damage."),
            F("Destroy Undead (CR 1)", "Turned undead of CR 1 or lower are destroyed.")],
        9: [],
        10: [F("Divine Intervention", "Call on your deity for help; succeeds if a d100 roll is at or under your cleric level.",
               {"max": 1, "per": "long"})],
    },
    "druid": {
        6: [F("Land's Stride", "Nonmagical difficult terrain costs no extra movement; advantage on saves against magical plants.")],
        7: [],
        8: [ASI, F("Wild Shape (CR 1)", "You can become beasts of CR 1, including ones that fly.")],
        9: [],
        10: [F("Nature's Ward", "Immune to poison and disease; elementals and fey can't charm or frighten you.")],
    },
    "fighter": {
        6: [ASI],
        7: [F("Remarkable Athlete", "Add half your proficiency bonus to STR, DEX and CON checks you aren't proficient in.")],
        8: [ASI],
        9: [F("Indomitable", "Reroll a failed saving throw.", {"max": 1, "per": "long"})],
        10: [F("Additional Fighting Style", "You learn a second fighting style.")],
    },
    "monk": {
        6: [F("Ki-Empowered Strikes", "Your unarmed strikes count as magical."),
            F("Wholeness of Body", "Action: regain hit points equal to three times your monk level.", {"max": 1, "per": "long"}),
            F("Unarmored Movement (+15 ft)", "Your unarmored speed bonus becomes +15 ft.")],
        7: [F("Evasion", "On a DEX save for half damage, you take none on a success and half on a failure."),
            F("Stillness of Mind", "Action: end one effect charming or frightening you.")],
        8: [ASI],
        9: [F("Unarmored Movement Improvement", "Move along walls and across liquids on your turn.")],
        10: [F("Purity of Body", "Immune to disease and poison."),
             F("Unarmored Movement (+20 ft)", "Your unarmored speed bonus becomes +20 ft.")],
    },
    "paladin": {
        6: [F("Aura of Protection", "You and allies within 10 ft add your CHA modifier (min +1) to saving throws while you're conscious.")],
        7: [F("Aura of Devotion", "You and allies within 10 ft can't be charmed while you're conscious.")],
        8: [ASI],
        9: [],
        10: [F("Aura of Courage", "You and allies within 10 ft can't be frightened while you're conscious.")],
    },
    "ranger": {
        6: [F("Favored Enemy (improved)", "Choose another favoured enemy and learn its language."),
            F("Natural Explorer (improved)", "Choose another favoured terrain.")],
        7: [F("Defensive Tactics", "Escape the Horde: opportunity attacks against you have disadvantage.")],
        8: [ASI, F("Land's Stride", "Nonmagical difficult terrain costs no extra movement.")],
        9: [],
        10: [F("Hide in Plain Sight", "Spend a minute camouflaging yourself: +10 to Stealth while you stay still."),
             F("Natural Explorer (third terrain)", "Choose a third favoured terrain.")],
    },
    "rogue": {
        6: [F("Expertise (more)", "Double proficiency for two more skills.")],
        7: [F("Evasion", "On a DEX save for half damage, you take none on a success and half on a failure.")],
        8: [ASI],
        9: [F("Supreme Sneak", "Advantage on Stealth checks if you move no more than half your speed.")],
        10: [ASI],
    },
    "sorcerer": {
        6: [F("Elemental Affinity", "Add your CHA modifier to one damage roll of a spell that deals your draconic ancestry's damage type.")],
        7: [],
        8: [ASI],
        9: [],
        10: [F("Metamagic (third option)", "Learn another Metamagic option.")],
    },
    "warlock": {
        6: [F("Dark One's Own Luck", "Add a d10 to an ability check or saving throw.", {"max": 1, "per": "short"})],
        7: [],
        8: [ASI],
        9: [],
        10: [F("Fiendish Resilience", "After a rest, choose a damage type: you have resistance to it until you choose another.")],
    },
    "wizard": {
        6: [F("Potent Cantrip", "Creatures that succeed on a save against your cantrip still take half its damage.")],
        7: [],
        8: [ASI],
        9: [],
        10: [F("Empowered Evocation", "Add your INT modifier to one damage roll of any wizard evocation spell you cast.")],
    },
}
for _k, _levels in _FEATURES_6_10.items():
    for _lvl, _feats in _levels.items():
        CLASSES[_k]["features"].setdefault(_lvl, []).extend(_feats)
    for _lvl in range(1, MAX_LEVEL + 1):
        CLASSES[_k]["features"].setdefault(_lvl, [])

# Levels with an Ability Score Improvement, per class (used by level-up offers).
ASI_LEVELS = {k: sorted(l for l, fs in c["features"].items() if any(f["name"] == "Ability Score Improvement" for f in fs))
              for k, c in CLASSES.items()}

BACKGROUNDS = {
    "acolyte": {"index": "acolyte", "name": "Acolyte", "skills": ["Insight", "Religion"], "gold_cp": 1500,
                "description": "You served in a temple and know its rites and people."},
    "soldier": {"index": "soldier", "name": "Soldier", "skills": ["Athletics", "Intimidation"], "gold_cp": 1000,
                "description": "You fought in a war or served a lord's garrison."},
    "criminal": {"index": "criminal", "name": "Criminal", "skills": ["Deception", "Stealth"], "gold_cp": 1500,
                 "description": "You have a history of breaking the law and contacts who still do."},
    "sage": {"index": "sage", "name": "Sage", "skills": ["Arcana", "History"], "gold_cp": 1000,
             "description": "You spent years learning the lore of the world."},
    "folk-hero": {"index": "folk-hero", "name": "Folk Hero", "skills": ["Animal Handling", "Survival"], "gold_cp": 1000,
                  "description": "You come from humble roots and stood up for your people."},
    "noble": {"index": "noble", "name": "Noble", "skills": ["History", "Persuasion"], "gold_cp": 2500,
              "description": "You were born to wealth, title and expectation."},
    "outlander": {"index": "outlander", "name": "Outlander", "skills": ["Athletics", "Survival"], "gold_cp": 1000,
                  "description": "You grew up in the wilds, far from towns and roads."},
    "entertainer": {"index": "entertainer", "name": "Entertainer", "skills": ["Acrobatics", "Performance"], "gold_cp": 1500,
                    "description": "You thrive in front of an audience."},
    "guild-artisan": {"index": "guild-artisan", "name": "Guild Artisan", "skills": ["Insight", "Persuasion"], "gold_cp": 1500,
                      "description": "You are a member of a craft guild."},
    "hermit": {"index": "hermit", "name": "Hermit", "skills": ["Medicine", "Religion"], "gold_cp": 500,
               "description": "You lived in seclusion for years."},
}

ALIGNMENTS = ["Lawful Good", "Neutral Good", "Chaotic Good", "Lawful Neutral", "True Neutral",
              "Chaotic Neutral", "Lawful Evil", "Neutral Evil", "Chaotic Evil"]

POINT_BUY_COSTS = {8: 0, 9: 1, 10: 2, 11: 3, 12: 4, 13: 5, 14: 7, 15: 9}
STANDARD_ARRAY = [15, 14, 13, 12, 10, 8]

# ── spell effects ───────────────────────────────────────────────────────────
# kind: attack | auto | save | heal | buff | sleep | save_condition | mark | teleport | summon_weapon
# target: enemy | ally | self | point | none ; area: {shape, size_ft} with shape sphere|cube|cone|line
SPELL_EFFECTS: dict[str, dict] = {
    # cantrips
    "fire-bolt": {"kind": "attack", "range": 120, "dice": "1d10", "type": "fire", "cantrip": True},
    "ray-of-frost": {"kind": "attack", "range": 60, "dice": "1d8", "type": "cold", "condition": "Slowed", "cantrip": True},
    "shocking-grasp": {"kind": "attack", "range": 5, "dice": "1d8", "type": "lightning", "cantrip": True},
    "chill-touch": {"kind": "attack", "range": 120, "dice": "1d8", "type": "necrotic", "cantrip": True},
    "eldritch-blast": {"kind": "attack", "range": 120, "dice": "1d10", "type": "force", "beams": True, "cantrip": True},
    "produce-flame": {"kind": "attack", "range": 30, "dice": "1d8", "type": "fire", "cantrip": True},
    "acid-splash": {"kind": "save", "save": "DEX", "range": 60, "dice": "1d6", "type": "acid", "half": False, "cantrip": True},
    "poison-spray": {"kind": "save", "save": "CON", "range": 10, "dice": "1d12", "type": "poison", "half": False, "cantrip": True},
    "sacred-flame": {"kind": "save", "save": "DEX", "range": 60, "dice": "1d8", "type": "radiant", "half": False, "cantrip": True},
    "vicious-mockery": {"kind": "save", "save": "WIS", "range": 60, "dice": "1d4", "type": "psychic", "half": False,
                        "fail_condition": "Mocked", "cantrip": True},
    "shillelagh": {"kind": "buff", "range": 0, "condition": "Shillelagh", "bonus": True, "target": "self"},
    # 1st level
    "magic-missile": {"kind": "auto", "range": 120, "darts": 3, "type": "force"},
    "burning-hands": {"kind": "save", "save": "DEX", "range": 15, "area": {"shape": "cone", "size_ft": 15}, "from_self": True,
                      "dice": "3d6", "type": "fire", "half": True, "upcast": "1d6"},
    "thunderwave": {"kind": "save", "save": "CON", "range": 15, "area": {"shape": "cube", "size_ft": 15}, "from_self": True,
                    "dice": "2d8", "type": "thunder", "half": True, "upcast": "1d8"},
    "guiding-bolt": {"kind": "attack", "range": 120, "dice": "4d6", "type": "radiant", "upcast": "1d6", "on_hit_condition": "Outlined"},
    "inflict-wounds": {"kind": "attack", "range": 5, "dice": "3d10", "type": "necrotic", "upcast": "1d10"},
    "cure-wounds": {"kind": "heal", "range": 5, "dice": "1d8", "upcast": "1d8"},
    "healing-word": {"kind": "heal", "range": 60, "dice": "1d4", "upcast": "1d4", "bonus": True},
    "false-life": {"kind": "buff", "range": 0, "target": "self", "temp_hp": "1d4+4"},
    "heroism": {"kind": "buff", "range": 5, "temp_hp": "MOD", "concentration": True, "condition": "Heroism"},
    "sleep": {"kind": "sleep", "range": 90, "area": {"shape": "sphere", "size_ft": 20}, "dice": "5d8", "upcast": "2d8"},
    "shield-of-faith": {"kind": "buff", "range": 60, "condition": "Shield of Faith", "bonus": True, "concentration": True},
    "mage-armor": {"kind": "buff", "range": 5, "condition": "Mage Armor"},
    "bless": {"kind": "buff", "range": 30, "condition": "Blessed", "concentration": True, "multi": 3},
    "bane": {"kind": "save_condition", "save": "CHA", "range": 30, "condition": "Baned", "concentration": True},
    "command": {"kind": "save_condition", "save": "WIS", "range": 60, "condition": "Prone", "one_turn": True},
    "entangle": {"kind": "save_condition", "save": "STR", "range": 90, "area": {"shape": "cube", "size_ft": 20},
                 "condition": "Restrained", "concentration": True},
    "faerie-fire": {"kind": "save_condition", "save": "DEX", "range": 60, "area": {"shape": "cube", "size_ft": 20},
                    "condition": "Outlined", "concentration": True},
    "hunters-mark": {"kind": "mark", "range": 90, "dice": "1d6", "bonus": True, "concentration": True},
    # 2nd level
    "scorching-ray": {"kind": "attack", "range": 120, "dice": "2d6", "type": "fire", "rays": 3},
    "acid-arrow": {"kind": "attack", "range": 90, "dice": "4d4", "type": "acid", "upcast": "1d4"},
    "shatter": {"kind": "save", "save": "CON", "range": 60, "area": {"shape": "sphere", "size_ft": 10}, "dice": "3d8",
                "type": "thunder", "half": True, "upcast": "1d8"},
    "hold-person": {"kind": "save_condition", "save": "WIS", "range": 60, "condition": "Paralyzed",
                    "creature_type": "humanoid", "concentration": True, "save_ends": True},
    "web": {"kind": "save_condition", "save": "DEX", "range": 60, "area": {"shape": "cube", "size_ft": 20},
            "condition": "Restrained", "concentration": True, "save_ends": True},
    "blindness-deafness": {"kind": "save_condition", "save": "CON", "range": 30, "condition": "Blinded", "save_ends": True},
    "moonbeam": {"kind": "save", "save": "CON", "range": 120, "area": {"shape": "sphere", "size_ft": 5}, "dice": "2d10",
                 "type": "radiant", "half": True, "upcast": "1d10", "concentration": True},
    "flaming-sphere": {"kind": "save", "save": "DEX", "range": 60, "area": {"shape": "sphere", "size_ft": 5}, "dice": "2d6",
                       "type": "fire", "half": True, "upcast": "1d6", "concentration": True},
    "spiritual-weapon": {"kind": "summon_weapon", "range": 60, "dice": "1d8", "type": "force", "bonus": True},
    "misty-step": {"kind": "teleport", "range": 30, "bonus": True},
    "aid": {"kind": "buff", "range": 30, "max_hp": 5, "multi": 3},
    "lesser-restoration": {"kind": "cleanse", "range": 5},
    # 3rd level
    "fireball": {"kind": "save", "save": "DEX", "range": 150, "area": {"shape": "sphere", "size_ft": 20}, "dice": "8d6",
                 "type": "fire", "half": True, "upcast": "1d6"},
    "lightning-bolt": {"kind": "save", "save": "DEX", "range": 100, "area": {"shape": "line", "size_ft": 100}, "from_self": True,
                       "dice": "8d6", "type": "lightning", "half": True, "upcast": "1d6"},
    "call-lightning": {"kind": "save", "save": "DEX", "range": 120, "area": {"shape": "sphere", "size_ft": 5}, "dice": "3d10",
                       "type": "lightning", "half": True, "upcast": "1d10", "concentration": True},
    "spirit-guardians": {"kind": "save", "save": "WIS", "range": 15, "area": {"shape": "sphere", "size_ft": 15}, "from_self": True,
                         "dice": "3d8", "type": "radiant", "half": True, "upcast": "1d8", "concentration": True, "enemies_only": True},
    "mass-healing-word": {"kind": "heal", "range": 60, "dice": "1d4", "upcast": "1d4", "bonus": True, "multi": 6},
    "vampiric-touch": {"kind": "attack", "range": 5, "dice": "3d6", "type": "necrotic", "upcast": "1d6", "drain": True,
                       "concentration": True},
    "hypnotic-pattern": {"kind": "save_condition", "save": "WIS", "range": 120, "area": {"shape": "cube", "size_ft": 30},
                         "condition": "Charmed", "concentration": True},
    "fear": {"kind": "save_condition", "save": "WIS", "range": 30, "area": {"shape": "cone", "size_ft": 30}, "from_self": True,
             "condition": "Frightened", "concentration": True, "save_ends": True},
    "stinking-cloud": {"kind": "save_condition", "save": "CON", "range": 90, "area": {"shape": "sphere", "size_ft": 20},
                       "condition": "Poisoned", "concentration": True, "one_turn": True},
    "haste": {"kind": "buff", "range": 30, "condition": "Hasted", "concentration": True},
    "beacon-of-hope": {"kind": "buff", "range": 30, "condition": "Hopeful", "concentration": True, "multi": 6},
    "revivify": {"kind": "revive", "range": 5},
    # 4th level
    "ice-storm": {"kind": "save", "save": "DEX", "range": 300, "area": {"shape": "sphere", "size_ft": 20}, "dice": "5d8",
                  "type": "cold", "half": True, "upcast": "1d8"},  # 2d8 bludgeoning + 4d6 cold, folded into one roll
    "blight": {"kind": "save", "save": "CON", "range": 30, "dice": "8d8", "type": "necrotic", "half": True, "upcast": "1d8"},
    "phantasmal-killer": {"kind": "save", "save": "WIS", "range": 120, "dice": "4d10", "type": "psychic", "half": False,
                          "fail_condition": "Frightened", "concentration": True, "upcast": "1d10"},
    "wall-of-fire": {"kind": "save", "save": "DEX", "range": 120, "area": {"shape": "cube", "size_ft": 20}, "dice": "5d8",
                     "type": "fire", "half": True, "upcast": "1d8", "concentration": True},
    "dimension-door": {"kind": "teleport", "range": 500},
    # 5th level
    "cone-of-cold": {"kind": "save", "save": "CON", "range": 60, "area": {"shape": "cone", "size_ft": 60}, "from_self": True,
                     "dice": "8d8", "type": "cold", "half": True, "upcast": "1d8"},
    "flame-strike": {"kind": "save", "save": "DEX", "range": 60, "area": {"shape": "sphere", "size_ft": 10}, "dice": "8d6",
                     "type": "fire", "half": True, "upcast": "1d6"},  # 4d6 fire + 4d6 radiant, folded
    "insect-plague": {"kind": "save", "save": "CON", "range": 300, "area": {"shape": "sphere", "size_ft": 20}, "dice": "4d10",
                      "type": "piercing", "half": True, "upcast": "1d10", "concentration": True},
    "cloudkill": {"kind": "save", "save": "CON", "range": 120, "area": {"shape": "sphere", "size_ft": 20}, "dice": "5d8",
                  "type": "poison", "half": True, "upcast": "1d8", "concentration": True},
    "mass-cure-wounds": {"kind": "heal", "range": 60, "dice": "3d8", "upcast": "1d8", "multi": 6},
    "hold-monster": {"kind": "save_condition", "save": "WIS", "range": 90, "condition": "Paralyzed",
                     "concentration": True, "save_ends": True},
    "dominate-person": {"kind": "save_condition", "save": "WIS", "range": 60, "condition": "Charmed",
                        "creature_type": "humanoid", "concentration": True, "save_ends": True},
}


def spell_target(index: str) -> str:
    eff = SPELL_EFFECTS.get(index)
    if not eff:
        return "none"
    if eff.get("target"):
        return eff["target"]
    if eff.get("area"):
        return "self" if eff.get("from_self") and eff["area"]["shape"] in ("sphere",) else "point"
    if eff["kind"] in ("heal", "buff", "cleanse", "revive"):
        return "ally"
    if eff["kind"] == "teleport":
        return "point"
    return "enemy"


def prof_bonus(level: int) -> int:
    return PROF_BONUS.get(level, 2)


def spell_kind(index: str) -> str:
    eff = SPELL_EFFECTS.get(index)
    if not eff:
        return "utility"
    k = eff["kind"]
    return {"sleep": "save", "save_condition": "save", "buff": "utility", "mark": "utility", "teleport": "utility",
            "summon_weapon": "attack", "cleanse": "heal", "revive": "heal"}.get(k, k)


def caster_type(cls_key: str) -> str | None:
    sc = CLASSES[cls_key]["spellcasting"]
    return sc["type"] if sc else None


def max_spell_level(cls_key: str, level: int) -> int:
    t = caster_type(cls_key)
    if t == "full":
        return max(int(k) for k in FULL_CASTER_SLOTS[level])
    if t == "half":
        slots = HALF_CASTER_SLOTS[level]
        return max((int(k) for k in slots), default=0)
    if t == "pact":
        return PACT_SLOTS[level][1]
    return 0
