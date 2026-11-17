/**
 * Plain-language explanations of D&D 5e rules terms, shown when a player hovers a keyword
 * ("Stable", "Dexterity", "prone", "concentration"…) in spell, feature and item text.
 *
 * `match` is a regex fragment (no flags). Entries are matched case-insensitively unless
 * `exact` is set — used for words that are ordinary English in lower case ("Hide", "Nature")
 * or abbreviations ("DEX", "AC"). `text2024` replaces `text` in games using the 2024 rules.
 */
import type { Ruleset } from "../api/types";

export interface GlossaryEntry {
  key: string;
  title: string;
  match: string;
  exact?: boolean;
  text: string;
  text2024?: string;
}

const ABILITY = {
  STR: "Physical power. Used for melee weapon attacks and damage (unless the weapon is finesse), Athletics (climbing, jumping, swimming, grappling), Strength saves against being pushed, held or knocked down, and how much you can carry.",
  DEX: "Agility and reflexes. Adds to your Armor Class (no armor, light armor, or up to +2 in medium armor), your initiative, ranged and finesse weapon attacks and damage, Acrobatics, Sleight of Hand and Stealth, and Dexterity saves — diving out of the way of things like Fireball or a trap.",
  CON: "Health and stamina. Adds to your hit points every level and to each Hit Die you spend healing, and to Constitution saves — resisting poison and disease, and keeping concentration on a spell when you take damage.",
  INT: "Reasoning and memory. Used for Arcana, History, Investigation, Nature and Religion, for Intelligence saves against mind-bending magic, and for casting wizard spells.",
  WIS: "Awareness and intuition. Used for Animal Handling, Insight, Medicine, Perception (and passive Perception) and Survival, for Wisdom saves against charms and fear, and for casting cleric, druid and ranger spells.",
  CHA: "Force of personality. Used for Deception, Intimidation, Performance and Persuasion, for Charisma saves against banishment or possession, and for casting bard, paladin, sorcerer and warlock spells.",
};

const skill = (name: string, ability: string, what: string): GlossaryEntry => ({
  key: `skill-${name.toLowerCase().replace(/ /g, "-")}`,
  title: `${name} (${ability})`,
  match: name.replace(/ /g, "\\s+"),
  exact: true,
  text: `A skill check: d20 + your ${ability} modifier, plus your proficiency bonus if you're proficient in ${name}. ${what}`,
});

export const GLOSSARY: GlossaryEntry[] = [
  // ---- life and death ----
  {
    key: "death-save",
    title: "Death saving throw",
    match: "death\\s+saving\\s+throws?|death\\s+saves?",
    text: "At 0 hit points you roll a d20 at the start of each of your turns, with no modifiers. 10 or higher is a success, 9 or lower a failure. Three successes and you become stable; three failures and you die. A natural 20 brings you back with 1 hit point; a natural 1 counts as two failures. Taking damage while at 0 hit points counts as a failure (two on a critical hit).",
  },
  {
    key: "zero-hp",
    title: "0 hit points",
    match: "0\\s+hit\\s+points",
    text: "A character who drops to 0 hit points falls unconscious and starts making death saving throws (most monsters simply die). If the damage left over after reaching 0 equals or exceeds your hit point maximum, you die outright. Any healing brings you back up and wakes you.",
  },
  {
    key: "temp-hp",
    title: "Temporary hit points",
    match: "temporary\\s+hit\\s+points?",
    text: "A buffer that soaks up damage before your real hit points do. They don't stack — if you get more, keep whichever amount is higher. Healing can't restore them, and they don't count when you're at 0 hit points. They fade after a long rest unless the effect says sooner.",
  },
  {
    key: "stable",
    title: "Stable",
    match: "stable|stabili[sz](?:e|es|ed|ing)",
    text: "A stable creature is at 0 hit points but no longer dying: it stops making death saving throws. It stays unconscious and regains 1 hit point after 1d4 hours unless healed sooner. If it takes any damage, it starts dying again.",
    text2024:
      "A Stable creature is at 0 Hit Points but no longer dying: it stops making Death Saving Throws. It stays Unconscious and regains 1 Hit Point after 1d4 hours unless healed sooner. If it takes any damage, it starts dying again.",
  },
  {
    key: "hit-dice",
    title: "Hit Dice",
    match: "hit\\s+dice|hit\\s+die",
    text: "Your class's die (d6 to d12) — you have one per level. During a short rest you can spend any number of them: roll each and add your Constitution modifier to heal that much. A long rest gives back half your total (at least one).",
    text2024:
      "Your class's die (d6 to d12) — you have one per level. During a short rest you can spend any number of them: roll each and add your Constitution modifier to heal that much. A long rest gives all of them back.",
  },

  // ---- conditions ----
  {
    key: "blinded",
    title: "Blinded",
    match: "blinded",
    text: "Can't see, and automatically fails any check that needs sight. Attack rolls against it have advantage; its own attack rolls have disadvantage.",
  },
  {
    key: "charmed",
    title: "Charmed",
    match: "charmed",
    text: "Can't attack the charmer or target them with harmful abilities or magic. The charmer has advantage on checks to interact socially with it.",
  },
  {
    key: "deafened",
    title: "Deafened",
    match: "deafened",
    text: "Can't hear, and automatically fails any check that needs hearing.",
  },
  {
    key: "frightened",
    title: "Frightened",
    match: "frightened",
    text: "Disadvantage on ability checks and attack rolls while the source of its fear is in sight, and it can't willingly move closer to that source.",
  },
  {
    key: "grappled",
    title: "Grappled",
    match: "grappled",
    text: "Speed becomes 0. Ends if the grappler is incapacitated or something moves the creature out of the grappler's reach. To escape, use an action for a Strength (Athletics) or Dexterity (Acrobatics) check against the grappler's Strength (Athletics).",
    text2024:
      "Speed becomes 0, and it has disadvantage on attack rolls against anyone other than the grappler. The grappler can drag it along (at extra movement cost). To escape, use an action for a Strength (Athletics) or Dexterity (Acrobatics) check against the grapple's escape DC.",
  },
  {
    key: "incapacitated",
    title: "Incapacitated",
    match: "incapacitated",
    text: "Can't take actions or reactions.",
    text2024: "Can't take actions, bonus actions or reactions, can't speak, and loses concentration. Rolls initiative with disadvantage.",
  },
  {
    key: "invisible",
    title: "Invisible",
    match: "invisible",
    text: "Can't be seen without magic or a special sense, so it can always try to hide. Attack rolls against it have disadvantage; its own attack rolls have advantage. Its noise or tracks can still give its location away.",
  },
  {
    key: "paralyzed",
    title: "Paralyzed",
    match: "paraly[sz]ed",
    text: "Incapacitated and can't move or speak. Automatically fails Strength and Dexterity saves. Attack rolls against it have advantage, and any hit from within 5 feet is a critical hit.",
  },
  {
    key: "petrified",
    title: "Petrified",
    match: "petrified",
    text: "Turned to stone along with what it's wearing and carrying. Incapacitated, can't move or speak, and unaware of its surroundings. Attack rolls against it have advantage; it automatically fails Strength and Dexterity saves, resists all damage, and is immune to poison and disease.",
  },
  {
    key: "poisoned",
    title: "Poisoned",
    match: "poisoned",
    text: "Disadvantage on attack rolls and ability checks.",
  },
  {
    key: "prone",
    title: "Prone",
    match: "prone",
    text: "Lying on the ground. It can only crawl until it stands up, which costs half its speed. Its attack rolls have disadvantage. Attacks against it have advantage from within 5 feet and disadvantage from farther away.",
  },
  {
    key: "restrained",
    title: "Restrained",
    match: "restrained",
    text: "Speed becomes 0. Attack rolls against it have advantage, its own attack rolls have disadvantage, and it has disadvantage on Dexterity saves.",
  },
  {
    key: "stunned",
    title: "Stunned",
    match: "stunned",
    text: "Incapacitated, can't move, and can speak only falteringly. Automatically fails Strength and Dexterity saves, and attack rolls against it have advantage.",
  },
  {
    key: "unconscious",
    title: "Unconscious",
    match: "unconscious",
    text: "Incapacitated, can't move or speak, and unaware of its surroundings; it drops what it's holding and falls prone. Automatically fails Strength and Dexterity saves. Attack rolls against it have advantage, and any hit from within 5 feet is a critical hit.",
  },
  {
    key: "exhaustion",
    title: "Exhaustion",
    match: "exhaustion|exhausted",
    text: "Comes in six levels, and the effects add up: 1 — disadvantage on ability checks; 2 — speed halved; 3 — disadvantage on attack rolls and saves; 4 — hit point maximum halved; 5 — speed 0; 6 — death. A long rest with food and drink removes one level.",
    text2024: "Comes in six levels. Each level gives −2 to every d20 roll (attacks, checks and saves) and −5 feet of speed. Level 6 is death. A long rest removes one level.",
  },

  // ---- abilities ----
  { key: "str", title: "Strength", match: "strength", text: ABILITY.STR },
  { key: "dex", title: "Dexterity", match: "dexterity", text: ABILITY.DEX },
  { key: "con", title: "Constitution", match: "constitution", text: ABILITY.CON },
  { key: "int", title: "Intelligence", match: "intelligence", text: ABILITY.INT },
  { key: "wis", title: "Wisdom", match: "wisdom", text: ABILITY.WIS },
  { key: "cha", title: "Charisma", match: "charisma", text: ABILITY.CHA },
  { key: "str", title: "Strength", match: "STR", exact: true, text: ABILITY.STR },
  { key: "dex", title: "Dexterity", match: "DEX", exact: true, text: ABILITY.DEX },
  { key: "con", title: "Constitution", match: "CON", exact: true, text: ABILITY.CON },
  { key: "int", title: "Intelligence", match: "INT", exact: true, text: ABILITY.INT },
  { key: "wis", title: "Wisdom", match: "WIS", exact: true, text: ABILITY.WIS },
  { key: "cha", title: "Charisma", match: "CHA", exact: true, text: ABILITY.CHA },

  // ---- dice and numbers ----
  {
    key: "disadvantage",
    title: "Disadvantage",
    match: "disadvantage",
    text: "Roll two d20s and use the lower. If you have both advantage and disadvantage, they cancel out and you roll one die — no matter how many sources of each.",
  },
  {
    key: "advantage",
    title: "Advantage",
    match: "advantage",
    text: "Roll two d20s and use the higher. If you have both advantage and disadvantage, they cancel out and you roll one die — no matter how many sources of each.",
  },
  {
    key: "spell-save-dc",
    title: "Spell save DC",
    match: "spell\\s+save\\s+DC",
    text: "How hard your spells are to resist: 8 + your proficiency bonus + your spellcasting ability modifier. A target rolls a saving throw and must meet or beat it. It's on your Spells tab.",
  },
  {
    key: "saving-throw",
    title: "Saving throw",
    match: "saving\\s+throws?",
    text: "A roll to resist a spell, trap or effect: d20 + the named ability's modifier (plus your proficiency bonus if you're proficient in that save), against the DC set by whatever is affecting you. Meet or beat it and you succeed — often taking half damage or avoiding the effect.",
  },
  {
    key: "ability-check",
    title: "Ability check",
    match: "ability\\s+checks?",
    text: "d20 + an ability modifier (plus your proficiency bonus if a skill or tool you're proficient in applies) against a DC the DM sets. Meet or beat it to succeed.",
  },
  {
    key: "spell-attack",
    title: "Spell attack",
    match: "spell\\s+attacks?",
    text: "An attack roll made with a spell: d20 + your spellcasting ability modifier + your proficiency bonus (the \"Spell attack\" number on your Spells tab), against the target's Armor Class.",
  },
  {
    key: "attack-roll",
    title: "Attack roll",
    match: "attack\\s+rolls?",
    text: "d20 + your ability modifier + your proficiency bonus (if proficient with the weapon or it's a spell), against the target's Armor Class. Meet or beat it to hit. A natural 20 always hits and is a critical hit; a natural 1 always misses.",
  },
  {
    key: "critical-hit",
    title: "Critical hit",
    match: "critical\\s+hits?",
    text: "Rolling a natural 20 on an attack roll. The attack hits no matter what, and you roll all of its damage dice twice, then add your modifiers once.",
  },
  {
    key: "armor-class",
    title: "Armor Class (AC)",
    match: "armou?r\\s+class",
    text: "How hard you are to hit. An attack roll must meet or beat it. It comes from your armor, shield and Dexterity, plus things like spells and cover.",
  },
  { key: "armor-class", title: "Armor Class (AC)", match: "AC", exact: true, text: "How hard you are to hit. An attack roll must meet or beat it. It comes from your armor, shield and Dexterity, plus things like spells and cover." },
  {
    key: "dc",
    title: "DC (Difficulty Class)",
    match: "DC",
    exact: true,
    text: "The number a check or saving throw has to meet or beat to succeed.",
  },
  {
    key: "proficiency",
    title: "Proficiency bonus",
    match: "proficiency\\s+bonus",
    text: "A bonus that grows with your level: +2 at levels 1–4, +3 at 5–8, +4 at 9–12, +5 at 13–16, +6 at 17–20. Added to attacks with weapons you're proficient with, spell attacks, and the skills, tools and saves you're proficient in, and to your spell save DC.",
  },
  {
    key: "expertise",
    title: "Expertise",
    match: "expertise",
    text: "Double your proficiency bonus on checks with that skill.",
  },
  {
    key: "initiative",
    title: "Initiative",
    match: "initiative",
    text: "A Dexterity check everyone rolls when a fight starts. Highest goes first; turns then follow that order every round.",
  },
  {
    key: "resistance",
    title: "Resistance",
    match: "resistance|resistant",
    text: "Takes half damage of that type (rounded down). Several resistances to the same damage don't stack.",
  },
  {
    key: "vulnerability",
    title: "Vulnerability",
    match: "vulnerability|vulnerable",
    text: "Takes double damage of that type.",
  },
  {
    key: "immunity",
    title: "Immunity",
    match: "immunity|immune",
    text: "Takes no damage of that type, or can't be affected by that condition.",
  },

  // ---- turns and actions ----
  {
    key: "bonus-action",
    title: "Bonus action",
    match: "bonus\\s+actions?",
    text: "A quick extra action on your turn — but only for things that say they take a bonus action (a spell, a class feature). You get at most one per turn, and it's separate from your action.",
  },
  {
    key: "opportunity-attack",
    title: "Opportunity attack",
    match: "opportunity\\s+attacks?",
    text: "When an enemy you can see moves out of your reach, you can use your reaction to make one melee attack against it. Taking the Disengage action, or being moved by something else (pushed, teleported), doesn't provoke one.",
  },
  {
    key: "reaction",
    title: "Reaction",
    match: "reactions?",
    text: "An instant response to a trigger, which can happen even on someone else's turn — an opportunity attack, or a spell like Shield. You get one per round, and it comes back at the start of your turn.",
  },
  {
    key: "dash",
    title: "Dash",
    match: "Dash",
    exact: true,
    text: "An action that gives you extra movement equal to your speed for this turn.",
  },
  {
    key: "disengage",
    title: "Disengage",
    match: "Disengage",
    exact: true,
    text: "An action: your movement doesn't provoke opportunity attacks for the rest of the turn.",
  },
  {
    key: "dodge",
    title: "Dodge",
    match: "Dodge",
    exact: true,
    text: "An action: until the start of your next turn, attack rolls against you have disadvantage (if you can see the attacker) and you make Dexterity saves with advantage.",
  },
  {
    key: "hide",
    title: "Hide",
    match: "Hide(?!\\s+armou?r)",
    exact: true,
    text: "An action: make a Dexterity (Stealth) check to become hidden while out of sight. While hidden, enemies don't know where you are, and you have advantage on your first attack.",
  },
  {
    key: "help",
    title: "Help",
    match: "Help(?=\\s+action)",
    exact: true,
    text: "An action: give an ally advantage on their next ability check, or on their next attack against a creature within 5 feet of you.",
  },
  {
    key: "ready",
    title: "Ready",
    match: "Ready(?=\\s+action)",
    exact: true,
    text: "An action: choose a trigger and a response (\"if the orc comes through the door, I hit it\"). When the trigger happens, you use your reaction to act.",
  },

  // ---- spellcasting ----
  {
    key: "concentration",
    title: "Concentration",
    match: "concentration|concentrat(?:e|es|ing)",
    text: "Some spells last only while you concentrate on them. You can concentrate on one spell at a time — casting another concentration spell ends the first. Taking damage forces a Constitution save (DC 10, or half the damage if higher) to keep it, and being incapacitated or killed ends it.",
  },
  {
    key: "ritual",
    title: "Ritual",
    match: "rituals?",
    text: "A spell with the ritual tag can be cast taking 10 minutes longer than normal, without spending a spell slot — if your class can cast rituals.",
  },
  {
    key: "cantrip",
    title: "Cantrip",
    match: "cantrips?",
    text: "A level-0 spell you can cast as often as you like, with no spell slot. Damage cantrips get stronger at character levels 5, 11 and 17.",
  },
  {
    key: "spell-slot",
    title: "Spell slot",
    match: "spell\\s+slots?",
    text: "Casting a spell of level 1 or higher uses up a slot of that level or higher; a higher slot often makes the spell stronger. Slots come back after a long rest (warlock Pact Magic slots come back after a short rest).",
  },
  {
    key: "short-rest",
    title: "Short rest",
    match: "short\\s+rests?",
    text: "At least an hour of downtime. You can spend Hit Dice to heal, and some features recharge (like a warlock's spell slots or a fighter's Second Wind).",
  },
  {
    key: "long-rest",
    title: "Long rest",
    match: "long\\s+rests?",
    text: "Eight hours, mostly sleeping. You regain all your hit points and spell slots and most features. You can benefit from only one long rest in 24 hours.",
  },

  // ---- seeing and moving ----
  {
    key: "difficult-terrain",
    title: "Difficult terrain",
    match: "difficult\\s+terrain",
    text: "Rubble, undergrowth, deep snow and the like. Every foot of movement costs 2 feet.",
  },
  { key: "half-cover", title: "Half cover", match: "half\\s+cover", text: "Something blocks at least half of the target: +2 to its AC and Dexterity saves." },
  {
    key: "three-quarters-cover",
    title: "Three-quarters cover",
    match: "three-quarters\\s+cover",
    text: "Something blocks about three-quarters of the target: +5 to its AC and Dexterity saves.",
  },
  { key: "total-cover", title: "Total cover", match: "total\\s+cover", text: "The target is completely hidden behind something and can't be targeted directly by attacks or spells." },
  {
    key: "heavily-obscured",
    title: "Heavily obscured",
    match: "heavily\\s+obscured",
    text: "Darkness, thick fog or dense foliage. Anyone trying to see something there is effectively blinded.",
  },
  {
    key: "lightly-obscured",
    title: "Lightly obscured",
    match: "lightly\\s+obscured",
    text: "Dim light, patchy fog or light foliage. Disadvantage on Wisdom (Perception) checks that rely on sight.",
  },
  {
    key: "darkvision",
    title: "Darkvision",
    match: "darkvision",
    text: "Within its range you see in dim light as if it were bright, and in darkness as if it were dim light — in shades of gray only.",
  },
  { key: "blindsight", title: "Blindsight", match: "blindsight", text: "Perceives its surroundings within that range without relying on sight." },
  {
    key: "truesight",
    title: "Truesight",
    match: "truesight",
    text: "Within that range it sees in any darkness, sees invisible creatures and objects, sees through illusions, and perceives the true form of shapechangers.",
  },
  { key: "tremorsense", title: "Tremorsense", match: "tremorsense", text: "Senses anything touching the same ground (or water) within that range through vibrations." },
  {
    key: "passive-perception",
    title: "Passive Perception",
    match: "passive\\s+perception",
    text: "10 + your Wisdom (Perception) modifier. The DM compares it against hidden creatures and traps to see if you notice them without rolling.",
  },

  // ---- skills ----
  skill("Acrobatics", "Dexterity", "Keeping your balance, tumbling, and slipping free of a grapple."),
  skill("Animal Handling", "Wisdom", "Calming, controlling or reading an animal."),
  skill("Arcana", "Intelligence", "Knowing about spells, magic items, other planes and magical traditions."),
  skill("Athletics", "Strength", "Climbing, jumping, swimming, grappling and shoving."),
  skill("Deception", "Charisma", "Lying convincingly, disguising your intent, bluffing."),
  skill("History", "Intelligence", "Recalling lore about past events, kingdoms, wars and people."),
  skill("Insight", "Wisdom", "Reading someone's true intentions and spotting a lie."),
  skill("Intimidation", "Charisma", "Influencing someone through threats or a show of force."),
  skill("Investigation", "Intelligence", "Searching for clues and working out how things fit together."),
  skill("Medicine", "Wisdom", "Stabilizing a dying companion or diagnosing an illness."),
  skill("Nature", "Intelligence", "Knowing about terrain, plants, animals and the weather."),
  skill("Perception", "Wisdom", "Noticing things: spotting, hearing or otherwise sensing what's around you."),
  skill("Performance", "Charisma", "Entertaining an audience with music, dance, acting or storytelling."),
  skill("Persuasion", "Charisma", "Influencing someone with tact, good nature or a reasonable argument."),
  skill("Religion", "Intelligence", "Knowing about deities, rites, holy symbols and cults."),
  skill("Sleight of Hand", "Dexterity", "Picking pockets, planting something on someone, palming an object."),
  skill("Stealth", "Dexterity", "Moving without being seen or heard, and hiding."),
  skill("Survival", "Wisdom", "Tracking, hunting, finding your way and predicting the weather."),
];

const BY_KEY = new Map<string, GlossaryEntry>();
for (const e of GLOSSARY) if (!BY_KEY.has(e.key)) BY_KEY.set(e.key, e);

/** Look up an entry by key (e.g. "dex", "stable", "skill-stealth"). */
export function glossaryEntry(key: string): GlossaryEntry | undefined {
  return BY_KEY.get(key);
}

/** The ability entry key for "DEX", "Dexterity", etc. */
export function abilityKey(ability: string): string {
  return ability.slice(0, 3).toLowerCase();
}

/** The skill entry key for a skill name ("Sleight of Hand" → "skill-sleight-of-hand"). */
export function skillKey(name: string): string {
  return `skill-${name.toLowerCase().replace(/ /g, "-")}`;
}

export function entryText(e: GlossaryEntry, ruleset: Ruleset | undefined): string {
  return ruleset === "2024" && e.text2024 ? e.text2024 : e.text;
}

/** One regex with a capture group per entry; longer phrases first so "death saving throw" beats "saving throw". */
const ORDERED = [...GLOSSARY].sort((a, b) => b.match.length - a.match.length);
const PATTERN = new RegExp(ORDERED.map((e) => `\\b(${e.match})\\b`).join("|"), "gi");
const EXACT_RE = new Map(ORDERED.filter((e) => e.exact).map((e) => [e, new RegExp(`^(?:${e.match})$`)]));

export type TextPiece = string | { text: string; entry: GlossaryEntry };

/**
 * Split text into plain strings and glossary hits. Only the first mention of each term in a
 * block is marked, so a description isn't a wall of underlines.
 */
export function splitTerms(text: string, skip?: Set<string>): TextPiece[] {
  const out: TextPiece[] = [];
  const seen = new Set<string>(skip);
  let last = 0;
  PATTERN.lastIndex = 0;
  for (let m = PATTERN.exec(text); m; m = PATTERN.exec(text)) {
    const i = m.findIndex((g, n) => n > 0 && g !== undefined) - 1;
    const entry = ORDERED[i];
    if (!entry) continue;
    if (entry.exact && !EXACT_RE.get(entry)!.test(m[0])) continue;
    if (seen.has(entry.key)) continue;
    seen.add(entry.key);
    if (m.index > last) out.push(text.slice(last, m.index));
    out.push({ text: m[0], entry });
    last = m.index + m[0].length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}
