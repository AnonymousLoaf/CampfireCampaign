"""Ready-made campaign plots any host can pick, alongside the ones they write under My content.

Each is an original story in the spirit of a popular kind of tale (a televised death-dungeon, a caste
rebellion, a war academy...), with its own world, people and names. They use the same fields as a host's plot
(see plot.py), so the DM reads them the same way. `suggest` is the story type and tone they play best with.
"""
from __future__ import annotations

PRESETS: list[dict] = [
    {
        "key": "dungeon_show",
        "name": "Live from the Deep",
        "pitch": "The world's surface is gone overnight. The survivors are dropped into a sprawling dungeon that is also the "
                 "most-watched show in the multiverse, with sponsors, ratings and very sarcastic prize boxes.",
        "suggest": {"story_type": "dungeon_crawl", "tone": "lighthearted"},
        "data": {
            "premise": "At dawn every city on the surface folds into the earth. The handful of survivors, the party among "
                       "them, wake in the first floor of the Gauntlet: an endless, shifting dungeon built by the Spectator "
                       "Concord, bored immortals who broadcast it to a billion worlds. Each floor has a timer; when it "
                       "runs out the floor collapses with anyone still on it. The audience loves a good show, and a "
                       "crowd favourite gets sponsor gifts. A dull one gets forgotten, or worse.",
            "opening": "A bright, chirpy voice welcomes the party to Season Ninety-One as their bedroom, tavern or cell "
                       "walls dissolve into torchlit stone. A floating gilded box drifts down with a ribbon: 'Welcome "
                       "Gift (Common).' Inside: one sock and a potion of mild courage. Somewhere a laugh track plays.",
            "villain": "Showrunner Vell Ormandy, a glittering, smiling producer of the Concord who treats the dungeon as "
                       "her career. She rewrites floors on a whim for ratings, and she hates being upstaged.",
            "goal": "Vell wants the most-watched finale in history: a final floor where the last survivors are pitted "
                    "against each other. If nobody stops her, the season ends with the party hunted by the very "
                    "survivors they saved.",
            "ending": "The party reaches the broadcast core under the deepest floor and chooses: win the show and earn a "
                      "'prize' world of their own, or seize the broadcast and show a billion viewers what the Concord "
                      "really is, turning the audience against the showrunner.",
            "themes": "Gallows humour, spectacle versus humanity, found family among strangers, defiance with a grin.",
            "acts": [
                "Floor one: tutorial horrors, sponsor boxes, first allies among the frightened survivors.",
                "Floor two: a town-sized safe zone run by a guild of contestants who sell 'protection'.",
                "A themed floor (a carnival of mimics) where the audience votes on hazards in real time.",
                "The party becomes popular; Vell starts sending 'special guest' monsters just for them.",
                "A rival crew of veteran contestants offers an alliance, then betrays it on live broadcast.",
                "The party discovers the dungeon's maintenance tunnels and the workers who never appear on screen.",
                "Final floor: the arena, the vote, the broadcast core.",
            ],
            "secrets": [
                "The cheerful announcer voice is a captured contestant from a previous season, forced to host.",
                "Sponsor gifts come with hidden strings: each one lets a sponsor 'ride along' and see through your eyes.",
                "Collapsing floors don't kill everyone: some fall into the maintenance levels and work the dungeon.",
                "The Concord's ratings are falling. Vell is desperate, and desperate producers make mistakes.",
                "The prize world promised to past winners is a gilded cage on display.",
            ],
            "twists": [
                "The rival crew's leader is a past winner who came back to stop the show from inside.",
                "The audience can be reached: a heartfelt moment on camera makes a sponsor defect to the party.",
            ],
            "npcs": [
                {"name": "Pip the Announcer", "role": "The relentlessly upbeat voice of the dungeon.",
                 "secret": "A former contestant trapped in the broadcast; she slips the party hints in her jokes."},
                {"name": "Showrunner Vell Ormandy", "role": "Producer of the Gauntlet.",
                 "secret": "One more bad season and the Concord will cancel her too, literally."},
                {"name": "Grandma Tuck", "role": "A tough old survivor with a cast-iron pan and no patience.",
                 "secret": "She's been on the show before, and she knows a way down that skips a floor."},
                {"name": "Rook Daventry", "role": "Leader of the veteran contestant crew.",
                 "secret": "A past winner who refused his prize world and came back to burn the show down."},
            ],
        },
    },
    {
        "key": "iron_and_gold",
        "name": "Iron Beneath the Sun",
        "pitch": "A born miner of the lowest caste learns the deep shafts were built on a lie, and is smuggled into "
                 "the ruling class's court of duellists to bring the whole hierarchy down from inside.",
        "suggest": {"story_type": "intrigue", "tone": "dark"},
        "data": {
            "premise": "The Spire Dominion is ordered by brands burned at birth: the Sunborn rule, the Ledgered count, the "
                       "Sworn fight, the Hollowed dig. Hollowed miners are told the surface is ash and that their ore keeps "
                       "the last cities breathing. It is a lie: the surface has been green for two hundred years. A secret "
                       "network, the Rust, smuggles the party upward under false brands and places them in the Court of "
                       "Blades, the duelling society where Sunborn heirs win their titles, and their enemies' lives.",
            "opening": "Deep in Shaft Nine, the party's crew makes quota and is told it wasn't enough, again. That night a "
                       "stranger with rust-stained hands leads them up a forgotten ventilation shaft to a grate. Through "
                       "it: rain, birdsong and an orchard heavy with fruit.",
            "villain": "Archon Severin Vael, ruler of the Spire, who believes the brands are the only thing keeping the "
                       "Dominion from civil war, and who is not entirely wrong about how ugly freedom will be.",
            "goal": "Severin intends to flood the deep shafts the moment the Rust is uncovered and start over with a "
                    "more obedient Hollowed caste. If no one stops him, a hundred thousand miners drown in the dark.",
            "ending": "The party must decide whether to seize the Spire and rule better, burn the brands and face the "
                      "chaos, or forge something new, while their Sunborn friends learn who they really are.",
            "themes": "Class, loyalty, the cost of revolution, becoming the thing you hate, friendship across a lie.",
            "acts": [
                "Life in the shafts; the grate to the orchard; recruitment by the Rust.",
                "False brands, new names, courtly manners learned in a hurry from a disgraced etiquette tutor.",
                "The Court of Blades: formal duels, salons and wagers where reputations are made and ended.",
                "A season of patronage: the party must win a Sunborn house's sponsorship or be exposed.",
                "A tax ledger reveals how many shafts there really are, and how many have already been flooded.",
                "The Rust is betrayed; the flooding of Shaft Nine begins.",
                "Open rebellion, with every caste choosing a side.",
            ],
            "secrets": [
                "The Rust has smuggled others upward before; all were caught at the Court within a season.",
                "Duels at the Court are secretly arranged to decide which houses rise and fall.",
                "Severin's own heir sympathises with the Hollowed and funds the Rust in secret.",
                "The brands mean nothing: castes were assigned by lottery three generations ago.",
            ],
            "twists": [
                "A trusted Rust handler is selling secrets to Severin to win his family a better brand.",
                "The Sunborn duellist who humiliated the party becomes their most loyal ally.",
            ],
            "npcs": [
                {"name": "Mother Calla", "role": "Leader of the Rust, a scarred former surgeon.",
                 "secret": "She was Sunborn once, and she cut the brand off her own wrist."},
                {"name": "Cassian Lorne", "role": "Proud Sunborn duellist, the party's rival at Court.",
                 "secret": "His house is in debt and one lost duel from ruin."},
                {"name": "Archon Severin Vael", "role": "Ruler of the Spire Dominion.",
                 "secret": "He knows the brands are a lie; he thinks the lie is mercy."},
                {"name": "Dax", "role": "A cheerful Hollowed miner and the party's oldest friend.",
                 "secret": "Pressed into service as an informant to keep his sister fed."},
            ],
        },
    },
    {
        "key": "four_tides",
        "name": "The Four Tides",
        "pitch": "In a world where people call on the elements through song and dance, a child who can wake all four "
                 "sleeping spirits must be kept from an empire that wants to cage them.",
        "suggest": {"story_type": "sandbox", "tone": "heroic"},
        "data": {
            "premise": "The archipelago of Seastone has four great elemental spirits: Gale, Tide, Ember and Root. Callers draw "
                       "on one of them through song, dance and discipline. A century ago the spirits fell silent, and the "
                       "Brass Dominion, whose people had no spirit of their own, used clockwork and cannon to conquer the "
                       "islands. Now a child has been born who can hear all four spirits singing, and the party becomes "
                       "her escort.",
            "opening": "A storm-wrecked lighthouse island. In the cellar, a child humming a song no one taught her, while "
                       "seawater around her feet moves in time. On the horizon, the brass sails of a Dominion "
                       "survey ship.",
            "villain": "Inquisitor Maren Osk of the Brass Dominion, a cold, devout engineer who believes callers are a "
                       "disease and that caging the spirits will end a century of suffering.",
            "goal": "The Dominion plans to cage the four spirits in great brass reliquaries on the night of the eclipse, "
                    "making calling the empire's alone. If no one stops it, the islands lose their spirits forever.",
            "ending": "On the eclipse night, the party and the child stand inside the Dominion's reliquary-engine. They can "
                      "free the spirits, which will reshape the islands, or strike a bargain, and the child must choose "
                      "what she becomes.",
            "themes": "Hope, balance, growing up too fast, faith versus fear, joy and humour in dark times.",
            "acts": [
                "The child is found; the survey ship attacks; the party flees by sea.",
                "The Gale islands' sky-temples, empty, and the song she learns there.",
                "The Tide reefs, where a pirate queen of callers resists the Dominion.",
                "Maren's hunt: a chase across islands with clockwork hounds and bounty-callers.",
                "The Root forest island, where the trees remember the last war.",
                "Into the Brass capital in disguise; the Dominion's ordinary people are hungry and afraid too.",
                "The eclipse.",
            ],
            "secrets": [
                "The child is not the spirits' chosen; she is the four of them, sleeping in a single mortal form.",
                "The Dominion had a spirit once, the Fifth Tide of metal, and caged it themselves long ago.",
                "The reliquaries run on captured callers.",
                "Maren's brother was a caller who was taken from her as a child.",
            ],
            "twists": [
                "Freeing the Fifth Tide, the Dominion's lost spirit, ends the war better than any battle.",
                "Freeing all the spirits would end calling forever; the child must decide whether that's the price.",
            ],
            "npcs": [
                {"name": "Lio", "role": "The child who hears all four spirits.",
                 "secret": "She is losing her own memories as the spirits wake within her."},
                {"name": "Inquisitor Maren Osk", "role": "The Dominion's relentless hunter.",
                 "secret": "Her lost brother is a prisoner powering a reliquary."},
                {"name": "Queen Saltbraid", "role": "A boisterous pirate captain and Tide caller.",
                 "secret": "She once sold callers to the Dominion and is making up for it."},
                {"name": "The Brass Chancellor", "role": "Ruler of the Dominion.",
                 "secret": "He knows of the caged Fifth Tide and fears what it will do if freed."},
            ],
        },
    },
    {
        "key": "drowned_crown",
        "name": "The Drowned Crown",
        "pitch": "Ordinary folk carry a cursed crown across a darkening world to unmake it, while a bodiless king "
                 "hunts them and the crown learns each of their dreams.",
        "suggest": {"story_type": "wilderness", "tone": "heroic"},
        "data": {
            "premise": "Three hundred years ago Queen Ysolde the Lantern-Bearer sank the Crown of Echoes in the Mere of Ys, "
                       "for whoever wears it hears and commands the hearts of all who serve them. Now a drought has "
                       "drained the Mere, the crown lies in the mud, and the spirit of its maker, the Hollow King, wants "
                       "it back. The crown can only be unmade by returning it to the starfall crater where its silver "
                       "fell from the sky, on the far side of the world.",
            "opening": "A cracked lake bed at harvest. A child brings the party a muddy circlet she found, and the "
                       "party all hear, for a moment, someone they love calling their name. That night every dog in the "
                       "village howls at once.",
            "villain": "The Hollow King, a voice without a body who works through anyone who longs to be heard, "
                       "collecting a court of followers who all carry a little of his voice.",
            "goal": "Reclaim the crown and speak through every soldier, steward and ruler of the free lands. If no one "
                    "stops him, the free lands fall to whispers, not war.",
            "ending": "At the starfall crater the crown offers its bearer the voice of everyone they've lost. The party "
                      "must let it go together, or fight the one of them who won't.",
            "themes": "Friendship, temptation, grief, small people mattering, hope against despair.",
            "acts": [
                "The crown found; the village turned by whispers; flight at night.",
                "A circus caravan that hides the party, and a fortune teller who knows too much.",
                "The salt flats, where thirst and the crown's voice test the party.",
                "A city of bells where the crown can silence the Hollow King's followers, for a price.",
                "A ferry across the sea of glass with a crew who can't be trusted.",
                "The starfall crater, and the Hollow King's last servants.",
            ],
            "secrets": [
                "The crown speaks with the voices of the dead the bearer loved.",
                "The fortune teller is Ysolde's last descendant and knows the crater's way.",
                "The ferry captain is one of the Hollow King's court.",
                "The Hollow King can only take a body if the crown is put on willingly.",
            ],
            "twists": [
                "Ysolde did not sink the crown; she wore it, and the Hollow King is what she became.",
                "The crown can be unmade only by a song only the dead remember, and the party must ask the crown for it.",
            ],
            "npcs": [
                {"name": "Madame Orsolya", "role": "A circus fortune teller.",
                 "secret": "The last of Ysolde's line, and the crown wants her most of all."},
                {"name": "Captain Edric Vane", "role": "A charming ferry captain.",
                 "secret": "Already one of the Hollow King's court."},
                {"name": "Tilly Marsh", "role": "The child who found the crown.",
                 "secret": "She can hear the crown even from far away, and it talks to her kindly."},
            ],
        },
    },
    {
        "key": "dragons_hoard",
        "name": "A Burglar for the Brass Hall",
        "pitch": "A homebody signs a contract with a company of exiled gnome clockwrights to steal back their "
                 "clockwork city from a dragon who has made it her home. Cosy road, perilous end.",
        "suggest": {"story_type": "heist", "tone": "lighthearted"},
        "data": {
            "premise": "A generation ago the dragon Saffrael drove the gnome clockwrights from their mountain city, the Brass "
                       "Hall, and made its great clock tower her nest. Now Princess Oddny Gearwright wants her city back. "
                       "The plan is not a war but a burglary: get inside, restart the city's great clockwork heart, and "
                       "let the city do the rest. She needs a burglar who has never been anywhere and so has no "
                       "reputation, and the party is recruited along the way.",
            "opening": "A gnome on the doorstep at breakfast with a contract, a pot of very strong tea and an apology "
                       "for the clockwork owl that has just set the curtains on fire.",
            "villain": "Saffrael, ancient, lonely and proud, who has come to love the ticking city as her own and who is "
                       "more dangerous for being reasonable. Behind her, a merchant prince who wants the Hall's "
                       "gold for himself.",
            "goal": "Prince Casimir of the river town is secretly funding the expedition so it can wake the dragon and "
                    "drive her onto the gnomes, then claim the Hall. If no one stops him, the dragon burns the town "
                    "and the gnomes, and he walks in afterwards.",
            "ending": "Inside the Hall, the party can restart the clockwork heart and drive the dragon out, strike a "
                      "deal with her to share the city, or expose Casimir, who arrives with mercenaries for the gold.",
            "themes": "Comfort versus adventure, courage in small packages, home, greed, friendship.",
            "acts": [
                "The contract, the company and the clockwork owl.",
                "A road-side inn with a bounty-hunting ogre chef who wants the company's princess.",
                "A clockwork maze guarding the gnomes' old mountain road.",
                "A wild hunt of fey riders who demand a game of wits for passage.",
                "Prince Casimir's river town, all flattery and spies.",
                "Inside the Brass Hall: a conversation with a dragon at teatime.",
                "Mercenaries at the gates; dragon in the tower.",
            ],
            "secrets": [
                "The great clockwork heart, restarted, would make the Hall uninhabitable for a dragon's heat.",
                "Saffrael is the last of her kind and has been talking to the city's clocks for years.",
                "Casimir hired the company's map-maker to lead them into traps.",
                "Oddny's grandfather provoked the dragon by stealing her eggs.",
            ],
            "twists": [
                "Saffrael's last egg is still in the Hall's deepest vault, and the burglar finds it first.",
                "Saffrael fights alongside the gnomes against Casimir's mercenaries if the party earns her trust.",
            ],
            "npcs": [
                {"name": "Princess Oddny Gearwright", "role": "Brisk, brilliant leader of the gnome company.",
                 "secret": "She knows what her grandfather did and is ashamed of it."},
                {"name": "Saffrael", "role": "The dragon of the Brass Hall.",
                 "secret": "Lonely, the last of her kind, guarding her last egg."},
                {"name": "Prince Casimir", "role": "Generous patron of the expedition.",
                 "secret": "Wants the dragon and the gnomes to destroy each other."},
                {"name": "Pell", "role": "The company's cheerful map-maker.",
                 "secret": "Paid by Casimir to lead them astray; growing fond of them."},
            ],
        },
    },
    {
        "key": "war_academy",
        "name": "Skyward Academy",
        "pitch": "Gifted young cadets are trained at a floating war college through illusion battles against a "
                 "monstrous swarm, ranked, isolated and pushed to the edge.",
        "suggest": {"story_type": "war", "tone": "gritty"},
        "data": {
            "premise": "Fifty years ago the Chitter, an insectile swarm from beneath the world, nearly overran the kingdoms. "
                       "Now the Concord of Realms gathers its most promising young people at Skyward, a war college "
                       "floating above the clouds, where cadets duel on wind-swept skybridges and lead illusion armies in "
                       "the Mirror Halls. The party are new cadets.",
            "opening": "The skyship docks at Skyward. The headmistress greets the new cadets and announces that only "
                       "half of them will see the end of the year, and that one of them will lead the next war.",
            "villain": "Headmistress Corvane Thale, who believes the kingdoms will die unless she forges a perfect "
                       "commander, and who will isolate, manipulate and break the party to do it.",
            "goal": "Thale will push the party through ever harder trials until one of them becomes the weapon she wants. "
                    "If no one stops her, the Concord launches a war of extermination into the Chitter deeps.",
            "ending": "In the final trial, the party must choose whether to lead the assault on the Chitter deeps or to "
                      "find another way to end the war.",
            "themes": "Youth used as a weapon, rivalry and friendship, empathy for the enemy, the morality of war.",
            "acts": [
                "Arrival; the house sorting; making enemies and the first friend.",
                "Skybridge duels and wind-glider races; the party is handed the worst squad in the school.",
                "The Mirror Halls: illusion war games that seem to cheat.",
                "A field trip to the old battlefields, where something below the ground stirs.",
                "Promotion to the front-line fortress and a real skirmish.",
                "The Mirror Halls grow strangely real; the Chitter in them start to behave differently.",
                "The final trial.",
            ],
            "secrets": [
                "The Chitter are not mindless: they speak through a hum the party starts to hear in their sleep.",
                "The Mirror Halls are scrying into the real Chitter deeps.",
                "Thale has done this before; her last 'perfect commander' leads the Concord's armies and is unravelling.",
                "The first war began when Concord miners broke into the Chitter's nurseries.",
            ],
            "twists": [
                "The Concord's great general, Thale's last protégé, defects to the party.",
                "The Chitter will make peace, but only if the nurseries are sealed and left alone forever.",
            ],
            "npcs": [
                {"name": "Headmistress Corvane Thale", "role": "Head of Skyward Academy.",
                 "secret": "She hates what she does and does it anyway."},
                {"name": "Ash Varrow", "role": "Cadet squad leader who resents the party.",
                 "secret": "Being pushed by Thale to break them."},
                {"name": "Mira Tal", "role": "A brilliant cadet tactician and the party's first friend.",
                 "secret": "Also hearing the hum."},
                {"name": "Sergeant Bram Holloway", "role": "Instructor and veteran of the first war.",
                 "secret": "He saw the nurseries, and was ordered to forget them."},
            ],
        },
    },
    {
        "key": "masquerade_heist",
        "name": "Six Keys to the Gilded Vault",
        "pitch": "A crew of misfits must pull off an impossible heist during a masquerade in a city where every "
                 "lord has a secret and every secret has a price.",
        "suggest": {"story_type": "heist", "tone": "gritty"},
        "data": {
            "premise": "Velmora, a canal city of merchant princes. Its greatest treasure, the Gilded Vault of the Moneyers' "
                       "Guild, opens only at the Night of Masks, when six keyholders gather for the annual audit. A "
                       "mysterious patron hires the party to empty the vault, promising a fortune and a pardon.",
            "opening": "A note under a tavern door, a gondola at midnight, and a masked patron who knows each party member's "
                       "worst secret, and what it would take to make it disappear.",
            "villain": "Guildmaster Corvin Sallow, who keeps the city's secrets in the vault as blackmail, and who has a "
                       "spy in every crew.",
            "goal": "Corvin wants to use the night's audit to crown himself Doge, buying the council with the secrets in "
                    "his vault. If no one stops him, Velmora falls into the hands of a blackmailer.",
            "ending": "The vault is opened. The party can take the gold, steal the secrets, or free the city from them, "
                      "while the patron reveals what they really wanted.",
            "themes": "Trust, cleverness, reinvention, the line between thieves and nobles.",
            "acts": [
                "The job, the crew, the plan.",
                "Getting six keys from six keyholders: seduction, theft, forgery, duels.",
                "A plan unravels; one crew member is caught.",
                "Rescue from the canal prison.",
                "The Night of Masks: the heist, in real time.",
                "Double-crosses in the vault.",
            ],
            "secrets": [
                "The patron is one of the six keyholders.",
                "The vault holds secrets about every party member's past.",
                "The Guild's gold is mostly fake; the secrets are the real treasure.",
                "One crew member was paid by Corvin to sell the party out.",
            ],
            "twists": [
                "The traitor in the crew turns again, at the last second, for the party.",
                "The patron wants the secrets burned, and wants the party to decide whether to burn their own.",
            ],
            "npcs": [
                {"name": "The Patron in the Silver Mask", "role": "The party's mysterious employer.",
                 "secret": "Lady Isotta Venn, a keyholder blackmailed for years."},
                {"name": "Guildmaster Corvin Sallow", "role": "Head of the Moneyers' Guild.",
                 "secret": "He has a spy in every crew, including this one."},
                {"name": "Fennick Quill", "role": "A charming forger the party recruits.",
                 "secret": "Corvin's spy, with a family held hostage."},
            ],
        },
    },
    {
        "key": "saltmarsh_horror",
        "name": "What the Tide Brings",
        "pitch": "A fog-bound fishing town, strange catches, missing sailors and a congregation that sings to "
                 "the sea at night. Cosmic horror on a rotten coast.",
        "suggest": {"story_type": "horror", "tone": "dark"},
        "data": {
            "premise": "The fishing town of Grey Hollow has had the best catches in its history this year, and its "
                       "townsfolk are changing. The party arrives searching for a missing friend and finds a town "
                       "that smiles too much, a church that sings to the sea, and something vast stirring under the bay.",
            "opening": "The coach drops the party in thick fog at a shuttered inn. The innkeeper says the friend left "
                       "weeks ago. The party's friend's boots, still wet with salt, sit behind the bar.",
            "villain": "Mother Selka, high priestess of the Church of the Deep Tide, who believes the thing in the bay will "
                       "grant her people eternal life beneath the waves.",
            "goal": "Selka plans to wake the Sleeper under the bay on the spring tide, drowning the town into its "
                    "congregation. If no one stops her, Grey Hollow vanishes, and the Sleeper's dreams spread up the coast.",
            "ending": "On the night of the spring tide, the party can seal the Sleeper with its own hymn, destroy the "
                      "church, or flee, and some townsfolk may not want to be saved.",
            "themes": "Dread, isolation, the cost of comfort, the unknowable, choosing to stay human.",
            "acts": [
                "Arrival, the missing friend, the smiling town.",
                "The church service and the sea hymn.",
                "The old lighthouse keeper's warnings and journal.",
                "A night hunt by the changed fishermen.",
                "Under the bay: sunken caves and what lives there.",
                "The spring tide ritual.",
            ],
            "secrets": [
                "The missing friend joined the church willingly, and is half-changed.",
                "The town's founder struck the first bargain with the Sleeper a century ago.",
                "The sea hymn can lull the Sleeper back to rest if sung backwards.",
                "The lighthouse keeper has been keeping the Sleeper's dreams at bay with the lamp.",
            ],
            "twists": [
                "The innkeeper is the founder, still alive, a century old and terrified.",
                "One party member has been dreaming of the bay since they arrived and hears the hymn too.",
            ],
            "npcs": [
                {"name": "Mother Selka", "role": "High priestess of the Church of the Deep Tide.",
                 "secret": "She is already more fish than woman beneath her robes."},
                {"name": "Old Amos Kerrow", "role": "The half-mad lighthouse keeper.",
                 "secret": "The only one who knows the hymn backwards."},
                {"name": "Innkeeper Josiah Marsh", "role": "Runs the town's only inn.",
                 "secret": "The town's founder, kept alive by the Sleeper."},
            ],
        },
    },

    {
        "key": "hollow_moon",
        "name": "The Hollow Moon's Gold",
        "pitch": "A crew of misfit sailors lifts a pirate captain's cursed treasure and discovers that the curse "
                 "comes with a ghost ship, a sea witch and a very angry captain who can't die.",
        "suggest": {"story_type": "seafaring", "tone": "lighthearted"},
        "data": {
            "premise": "Thirty years ago Captain Morwen Blackwake stole the Hollow Moon, a sea goddess's silver idol, and "
                       "her whole crew was cursed: they cannot die, cannot rest, and rot a little more each night. The "
                       "idol was lost in a wreck. Now the party has found one of its silver coins, and every coin "
                       "calls the ghost ship Lamentation to whoever holds it.",
            "opening": "A dockside tavern brawl over a lost bet. In the chaos someone presses a cold silver coin into "
                       "a party member's hand and whispers 'Don't let them see it.' That night fog rolls into the "
                       "harbour and the bells of a ship no one can see start ringing.",
            "villain": "Captain Morwen Blackwake, charming, theatrical and three decades undead, who will do anything to "
                       "gather every coin and break the curse, including sacrificing whoever holds the last one.",
            "goal": "Morwen means to return the idol to the goddess's drowned shrine with a living sacrifice. If no one "
                    "stops her, the party member holding the last coin is drowned, and the curse passes to them.",
            "ending": "At the drowned shrine during the blood-moon tide, the party can return the idol, bargain with the "
                      "goddess, keep the treasure and inherit the curse, or free Morwen's crew, who have their own ideas.",
            "themes": "Swashbuckling, greed and its price, loyalty among rogues, second chances.",
            "acts": [
                "The coin, the fog and the first night attack by undead sailors.",
                "Acquiring a ship: buying, borrowing or stealing a leaky sloop and a crew of oddballs.",
                "The pirate haven of Saltgallows, where everyone wants the coin and nobody can be trusted.",
                "A sea witch who will read the coin's map, for a price paid in memories.",
                "Racing the Lamentation to the wreck of the first treasure ship.",
                "Morwen's offer: join her crew, or be hunted across the sea.",
                "The drowned shrine at the blood-moon tide.",
            ],
            "secrets": [
                "Morwen's first mate wants the curse to continue: he likes being unkillable.",
                "The sea witch is the goddess's former priestess and Morwen's lost love.",
                "Returning the idol frees the crew, but they all crumble to dust within the hour.",
                "One coin is missing from the hoard: it's been sewn into a party member's lucky charm all along.",
            ],
            "twists": [
                "The first mate mutinies and takes the idol for himself.",
                "The goddess offers the party the curse as a gift: immortality at sea, forever.",
            ],
            "npcs": [
                {"name": "Captain Morwen Blackwake", "role": "Undead pirate captain of the Lamentation.",
                 "secret": "She wants to die, after thirty years; she just won't admit it."},
                {"name": "Gristle Pike", "role": "Morwen's grinning, rotting first mate.",
                 "secret": "Plans to keep the idol and the curse for himself."},
                {"name": "Mother Kelpie", "role": "A sea witch in a hut on stilts.",
                 "secret": "The goddess's former priestess, who still loves Morwen."},
                {"name": "Tobias Fenn", "role": "A nervous young cabin boy who stows away on the party's ship.",
                 "secret": "Morwen's son, born before the curse."},
            ],
        },
    },
    {
        "key": "silver_for_wicked",
        "name": "Silver for the Wicked",
        "pitch": "Monster hunters for hire wander a war-torn, plague-haunted land where the monsters are dangerous "
                 "and the people who pay you are often worse.",
        "suggest": {"story_type": "sandbox", "tone": "gritty"},
        "data": {
            "premise": "The Duchy of Varn is falling apart: a three-way civil war, a wasting plague, and monsters "
                       "flooding out of the old battlefields. The party are hunters with a guild token and silver "
                       "blades, travelling village to village taking contracts. Every contract is a little mystery: "
                       "what is really killing people, and who really wants it dead?",
            "opening": "A muddy village notice board: 'REWARD. The thing in the mill. 40 crowns. Ask for the reeve.' The "
                       "reeve lies about how many have died. The miller's widow lies about why.",
            "villain": "The Pale Abbess, leader of a plague-curing order, who has learned to make monsters from the "
                       "dying and is selling them to all three sides of the civil war.",
            "goal": "The Abbess will finish her masterwork, a plague that turns soldiers into beasts, and sell it to "
                    "the highest bidder. If no one stops her, the war ends with no humans left to win it.",
            "ending": "In the abbey's catacombs the party confronts the Abbess, who offers a cure for the plague in "
                      "exchange for her freedom, and the three warring lords all want her alive.",
            "themes": "Moral grey, monsters versus men, the price of mercy, professionalism amid horror.",
            "acts": [
                "The mill contract: the monster was a cursed son, and the widow cursed him.",
                "A noble's contract to kill a 'beast' that is actually a deserter.",
                "A village of plague victims guarded by a creature that protects them.",
                "Patterns emerge: the monsters have stitched surgical scars.",
                "Hired by one warlord, framed by another.",
                "Into the abbey, posing as plague victims.",
                "The catacombs and the Abbess's offer.",
            ],
            "secrets": [
                "The Abbess's monsters are made from the dying, and some remember who they were.",
                "One warlord has already bought a monster regiment.",
                "The guild that issues the party's tokens takes a cut from the Abbess.",
                "The plague cure is real; the Abbess developed it first and hid it.",
            ],
            "twists": [
                "The creature guarding the plague village is the Abbess's first, rebellious creation, and an ally.",
                "The party's guildmaster sends other hunters to kill them when they get too close.",
            ],
            "npcs": [
                {"name": "The Pale Abbess Ilse", "role": "Head of the Order of the White Rose.",
                 "secret": "She believes she is saving humanity by making it stronger."},
                {"name": "Guildmaster Corran Thane", "role": "The party's employer and paymaster.",
                 "secret": "Paid by the Abbess to look the other way."},
                {"name": "Mother of Thorns", "role": "A monstrous protector of the plague village.",
                 "secret": "The Abbess's first creation, who remembers being a midwife."},
                {"name": "Lord Varic Stagg", "role": "A warlord who hires the party.",
                 "secret": "Has bought a monster regiment for his final assault."},
            ],
        },
    },
    {
        "key": "rimeford_hall",
        "name": "Murder at Rimeford Hall",
        "pitch": "Snowed in at a nobleman's winter estate for his birthday, the guests wake to find him dead in a "
                 "locked study, and everyone had a reason.",
        "suggest": {"story_type": "mystery", "tone": "gritty"},
        "data": {
            "premise": "Baron Aldous Rime, a wealthy, spiteful old collector of magical curiosities, invites the party and "
                       "a handful of relatives and rivals to Rimeford Hall to hear the reading of his new will. A blizzard "
                       "seals the mountain estate. At dawn the Baron is found dead in his locked study, and his newest "
                       "curiosity, a clockwork songbird, is missing.",
            "opening": "Dinner at Rimeford Hall: candlelight, a roaring fire, and the Baron announcing that he has "
                       "rewritten his will to leave everything to 'the one guest who has never lied to me.' Every "
                       "face at the table goes pale.",
            "villain": "The killer is Lady Celestine Rime, the Baron's quiet, devoted niece, who learned the songbird can "
                       "record and replay voices, and who used it to fake the Baron calling from inside the study "
                       "long after he died.",
            "goal": "Celestine plans to frame the Baron's illegitimate son and inherit. If no one stops her, an innocent "
                    "man hangs, and the songbird's other recordings, which hold everyone's secrets, are hers to use.",
            "ending": "The party gathers the suspects in the library. With enough clues they unmask Celestine; with too "
                      "few, she escapes into the storm with the songbird, or an innocent is accused.",
            "themes": "Secrets, greed, family, deduction, paranoia in a snowbound house.",
            "acts": [
                "Arrival, the guests, the dinner and the will.",
                "The body in the locked study; everyone's alibi.",
                "Searching the house: servants' passages, a hidden vault, a burnt letter.",
                "A second death: the butler, who knew too much.",
                "The songbird found, and what it recorded.",
                "The gathering in the library.",
            ],
            "secrets": [
                "The 'voice' heard from the study at midnight was the songbird, not the Baron.",
                "The Baron's illegitimate son is among the servants, posing as a footman.",
                "The Baron was being poisoned slowly by his doctor, who is a fraud, but not the killer.",
                "Every guest is in the Baron's black book of blackmail.",
                "The servants' passages connect the study to Celestine's room.",
            ],
            "twists": [
                "The songbird also recorded the Baron's last words, naming his real heir.",
                "The fraudulent doctor tries to flee and is mistaken for the killer.",
            ],
            "npcs": [
                {"name": "Lady Celestine Rime", "role": "The Baron's quiet, helpful niece.",
                 "secret": "The killer."},
                {"name": "Doctor Silas Warrender", "role": "The Baron's personal physician.",
                 "secret": "A fraud who has been slowly poisoning his patient for his fees."},
                {"name": "Jory", "role": "A young footman.",
                 "secret": "The Baron's illegitimate son, and the intended scapegoat."},
                {"name": "Madame Vesna Korr", "role": "A rival collector and old flame of the Baron.",
                 "secret": "Came to steal the songbird herself."},
                {"name": "Hargreave", "role": "The stiff old butler.",
                 "secret": "Saw Celestine in the servants' passage at midnight."},
            ],
        },
    },
    {
        "key": "regents_gambit",
        "name": "The Regent's Gambit",
        "pitch": "The old queen is dead, her heir is nine years old, and five great houses circle the throne. The "
                 "party are sworn to protect the child-king, and everyone smiles at them.",
        "suggest": {"story_type": "intrigue", "tone": "dark"},
        "data": {
            "premise": "Queen Alis the Wise has died suddenly, leaving a nine-year-old son, Prince Aubric, and a realm held "
                       "together by her will alone. A council of regents from the five great houses will rule until he "
                       "comes of age. The party are appointed his guardians on the queen's last command, and every house "
                       "would rather the boy be under its own control, or not at all.",
            "opening": "The queen's funeral in the rain. A frightened boy king holds a party member's hand. During the "
                       "procession an arrow is fired from the crowd, and it misses, but not by much.",
            "villain": "Lord Regent Matthias Corvane, the queen's oldest friend and the court's most trusted man, who "
                       "poisoned her and plans to rule through the boy, or replace him with his own grandson.",
            "goal": "Corvane intends to discredit the other houses one by one, have the boy declared mad, and crown his "
                    "grandson. If no one stops him, the realm falls into civil war when the houses rebel.",
            "ending": "At the boy's coronation feast, the party must expose Corvane, broker peace between the houses, "
                      "or seize the regency themselves. Aubric will remember how they did it.",
            "themes": "Loyalty, power, protecting innocence, the price of peace, trust in a court of liars.",
            "acts": [
                "The funeral, the arrow and the first council meeting.",
                "Each house courts the party: gifts, threats, marriages, bribes.",
                "A poisoning at the king's table; the food taster dies.",
                "The party discovers the queen was murdered.",
                "A house rebels in the provinces; the party must ride out or stay to guard the boy.",
                "Corvane moves openly to have the king declared mad.",
                "The coronation feast.",
            ],
            "secrets": [
                "The queen knew she was being poisoned and left a coded letter in the king's favourite storybook.",
                "The arrow at the funeral was fired by a rival house to frame Corvane.",
                "The boy king overhears far more than anyone realises.",
                "Corvane's grandson doesn't want the crown and is in love with a commoner.",
            ],
            "twists": [
                "The rival house that fired the arrow becomes the party's most important ally.",
                "Aubric is braver than everyone thinks and makes his own move at the feast.",
            ],
            "npcs": [
                {"name": "Prince Aubric", "role": "The nine-year-old heir to the throne.",
                 "secret": "He knows his mother was murdered; he heard her say so."},
                {"name": "Lord Regent Matthias Corvane", "role": "The queen's oldest friend and chief regent.",
                 "secret": "Her murderer."},
                {"name": "Lady Sabine Hollis", "role": "Sharp-tongued head of House Hollis.",
                 "secret": "Ordered the arrow fired at the funeral to frame Corvane."},
                {"name": "Brother Eadric", "role": "The royal confessor.",
                 "secret": "Heard the queen's suspicions and is terrified to speak."},
            ],
        },
    },
    {
        "key": "giants_walk",
        "name": "Where Giants Walk",
        "pitch": "A failed expedition, a crashed airship and an island where giant lizards, living jungle and the "
                 "ruins of a lost empire all want the party dead.",
        "suggest": {"story_type": "wilderness", "tone": "heroic"},
        "data": {
            "premise": "The Royal Society of Explorers' airship Meridian crashes on the uncharted Isle of Ammon, a land "
                       "where great thunder-lizards roam primeval jungle and the ruins of a lost serpent empire rise "
                       "from the fog. The party must survive, find the survivors scattered by the crash, and reach the "
                       "far mountain where a beacon could call rescue, before the island's rainy season floods the "
                       "lowlands.",
            "opening": "Smoke, wreckage and screaming engines. The party crawls out of the Meridian's broken hull into "
                       "steaming jungle. Somewhere close, something enormous breathes.",
            "villain": "Expedition financier Lord Basil Thorncastle, who caused the crash on purpose to claim the island's "
                       "ancient treasure for himself, and who has a private army hidden in the cargo hold.",
            "goal": "Thorncastle will wake the island's ancient serpent-god to seize its power and its treasure. If no "
                    "one stops him, the god wakes hungry, and the island, and the party, are its first meal.",
            "ending": "At the serpent temple on the volcano's rim, the party can stop the ritual, bargain with the "
                      "waking god, or flee as the island tears itself apart.",
            "themes": "Survival, wonder and terror, greed, the hubris of explorers, nature's power.",
            "acts": [
                "The crash; the first night; the first thunder-lizard.",
                "Finding survivors and building a camp.",
                "A river journey through living jungle with carnivorous plants.",
                "A tribe of lizardfolk descendants of the serpent empire.",
                "Thorncastle's betrayal revealed; his mercenaries hunt the party.",
                "The beacon on the mountain, and a choice: call rescue or stop the ritual.",
                "The serpent temple on the volcano.",
            ],
            "secrets": [
                "Thorncastle sabotaged the airship's engines to land on the island.",
                "The lizardfolk keep the god asleep with a song, and their singers are being hunted.",
                "The thunder-lizards flee the volcano because they sense the god waking.",
                "The beacon is a trap: Thorncastle's ship is waiting for its signal.",
            ],
            "twists": [
                "The expedition's quiet botanist is Thorncastle's estranged daughter and turns on him.",
                "The serpent-god is not evil, only ancient; it can be reasoned with by those who sing its song.",
            ],
            "npcs": [
                {"name": "Lord Basil Thorncastle", "role": "Wealthy financier of the expedition.",
                 "secret": "Caused the crash on purpose."},
                {"name": "Dr. Imogen Larke", "role": "The expedition's botanist.",
                 "secret": "Thorncastle's estranged daughter."},
                {"name": "Sseth-Ka", "role": "A lizardfolk song-keeper.",
                 "secret": "The last singer who knows the whole lullaby."},
                {"name": "Captain Ruth Ashby", "role": "The Meridian's battered pilot.",
                 "secret": "Knows the engines were sabotaged and suspects everyone."},
            ],
        },
    },
    {
        "key": "long_midsummer",
        "name": "The Endless Midsummer",
        "pitch": "Stepping through a ring of mushrooms, the party falls into a fey realm stuck in an eternal "
                 "summer, where the sun never sets, nothing ever dies, and the crops are starting to burn.",
        "suggest": {"story_type": "sandbox", "tone": "heroic"},
        "data": {
            "premise": "The fey Summer Queen has stolen the turning of the year, binding the Autumn Prince in chains so her "
                       "court's revelry never ends. In the fey realm of Evergleam it has been midsummer for a hundred "
                       "years: rivers are drying, the forests burning, and the people starving in endless sunlight. In "
                       "the mortal world, the seasons are faltering too. The party is pulled in through a fairy ring.",
            "opening": "A village harvest festival. Children dare each other to step into a ring of mushrooms. One "
                       "vanishes. The party follows, and steps out into blinding sunlight, scorched meadows and a fox "
                       "in a waistcoat who asks if they've come to save the world.",
            "villain": "Queen Aurelith of the Ever-Bright, beautiful, generous and terrified of the dark, who would "
                       "rather see her realm burn than let night fall again.",
            "goal": "The Queen plans to bind the mortal world's seasons too, making summer endless everywhere. If no one "
                    "stops her, the mortal harvest fails and famine follows.",
            "ending": "In the Sun Palace at the height of the Queen's revel, the party can free the Autumn Prince and "
                      "restore the seasons, convince the Queen to let go of her fear, or take her crown.",
            "themes": "Wonder, bargains, fear of change, the beauty of endings, growing up.",
            "acts": [
                "The fairy ring, the lost child and the fox guide.",
                "Fey bargains in the sun-drunk market of Goldenmeet.",
                "A parched river kingdom of water spirits.",
                "The Winter Witch, exiled and weak, who knows where the Prince is chained.",
                "Infiltrating the Summer Court's endless revel.",
                "The lost child is found, enchanted, and doesn't want to leave.",
                "The Sun Palace.",
            ],
            "secrets": [
                "The lost village child is the Autumn Prince reborn, hidden among mortals by his mother.",
                "The Queen's fear of the dark began when the last winter took her twin.",
                "The fox guide is the Queen's spy, though he's starting to like the party.",
                "Eating fey food in the Summer Court binds you to stay.",
            ],
            "twists": [
                "The Winter Witch is the Queen's lost twin, alive all along.",
                "Freeing the Autumn Prince means the child the party came to rescue must stay in Evergleam forever.",
            ],
            "npcs": [
                {"name": "Queen Aurelith of the Ever-Bright", "role": "Ruler of the Summer Court.",
                 "secret": "Terrified of the dark since her twin was lost to winter."},
                {"name": "Reynard", "role": "A fox in a waistcoat, the party's guide.",
                 "secret": "The Queen's spy, going soft."},
                {"name": "The Winter Witch", "role": "An exiled, frail sorceress in a cave of melting ice.",
                 "secret": "The Queen's lost twin."},
                {"name": "Pip Hollow", "role": "The lost village child.",
                 "secret": "The Autumn Prince reborn."},
            ],
        },
    },
    {
        "key": "last_wall",
        "name": "The Last Wall",
        "pitch": "A forgotten border fortress, a skeleton garrison, and an undead tide marching out of the north. "
                 "Hold the wall for thirty days until the army comes, if it comes at all.",
        "suggest": {"story_type": "war", "tone": "gritty"},
        "data": {
            "premise": "Fort Greyhold guards the only pass through the Thornspine Mountains. Its garrison has dwindled to "
                       "a few dozen convicts, old soldiers and youths. When a horn sounds from the north and the dead "
                       "rise from the old battlefields, the party is placed in command and told the king's army will "
                       "arrive in thirty days.",
            "opening": "The party arrives at Greyhold as punishment, reassignment or bad luck, to find the commander "
                       "dead by his own hand and a letter on his desk: 'They are coming. Do not let them through.'",
            "villain": "The Ashen Marshal, an ancient general of a fallen empire who has risen with his whole legion, "
                       "seeking the crown buried beneath the fortress.",
            "goal": "The Marshal must claim the buried crown to rebuild his empire with the dead. If no one stops him, "
                    "every grave in the kingdom opens behind him.",
            "ending": "On the thirtieth day, the final assault. The party can hold the wall, destroy the crown, or "
                      "bargain with the Marshal, who was once a defender of this same wall.",
            "themes": "Duty, sacrifice, leadership, despair and hope, honour among the forgotten.",
            "acts": [
                "Arrival; the dead commander; taking stock of the garrison and supplies.",
                "The first night attack: skeletons at the walls.",
                "Raids beyond the walls for supplies and for refugees fleeing south.",
                "Treachery: someone opens a postern gate.",
                "The crypts beneath the fortress and what's buried there.",
                "News: the army isn't coming.",
                "The thirtieth day.",
            ],
            "secrets": [
                "The fortress was built over the Marshal's tomb to keep his crown hidden.",
                "The dead commander knew the army wasn't coming and couldn't face telling the garrison.",
                "The quartermaster has been selling supplies to smugglers.",
                "The Marshal once held this same wall against invaders, before he was betrayed and killed here.",
            ],
            "twists": [
                "The Marshal offers peace if the crown is returned to him; he only wants to rest.",
                "Help arrives on the last day, not from the king but from the smugglers the party spared.",
            ],
            "npcs": [
                {"name": "The Ashen Marshal", "role": "Undead general of a fallen empire.",
                 "secret": "Wants only his crown and rest, and remembers defending Greyhold."},
                {"name": "Sergeant Maud Barrow", "role": "The garrison's grizzled veteran.",
                 "secret": "Read the commander's letters; knows the army isn't coming."},
                {"name": "Quartermaster Lisle", "role": "Keeper of supplies.",
                 "secret": "Has been selling them to smugglers."},
                {"name": "Corin", "role": "A young recruit, barely sixteen.",
                 "secret": "A descendant of the Marshal, and the crown recognises him."},
            ],
        },
    },
    {
        "key": "ashen_bell",
        "name": "The Ashen Bell",
        "pitch": "Cursed wanderers who can't stay dead climb through a ruined, beautiful kingdom of fallen knights and mad gods, ringing the old bells that might end the curse. Hard, lonely and full of secrets.",
        "suggest": {
            "story_type": "dungeon_crawl",
            "tone": "dark"
        },
        "data": {
            "premise": "The kingdom of the Vale is dying slowly. A curse called the Ashmark has spread through its people: the marked cannot die, but each time they fall and rise they lose a little of their memory, until they become empty husks. The party are marked. Legend says that ringing the five Ashen Bells, hidden in the Vale's most dangerous places, will end the curse. Many have tried; their husks guard the way.",
            "opening": "The party wakes in a stone coffin in a flooded crypt, the Ashmark burning on their skin. A husk of a knight sits by a dead campfire, waiting, and says only: 'Another one. Ring them, if you can.' A cracked bell tolls far away.",
            "villain": "King Aldric the Unsleeping, who bound the gods to sleep beneath the Vale to stop them dying, and caused the curse by doing it. He sits on his throne, ancient and half-faded, still guarding their sleep.",
            "goal": "Aldric's binding is failing; to hold it he gathers the souls of the marked. If no one stops him, every marked soul in the Vale is fed to the binding, and the sleeping gods wake anyway, starving.",
            "ending": "At the fifth bell the party learns the truth: ringing it ends the curse by waking the gods, who will remake the Vale, for better or worse. They can ring it, take Aldric's throne and keep the gods asleep, or find a third path the Vale's oldest flame-tender knows.",
            "themes": "Persistence, loss of self, beauty in ruin, mystery told through objects and places, earned triumph.",
            "acts": [
                "The flooded crypt and the first campfire; a merchant who sells to the marked.",
                "The first bell in a burning cathedral, guarded by a fading saint.",
                "A poisoned swamp town where marked pilgrims beg for death.",
                "A knight of the old order who joins the party, fading a little more each night.",
                "The painted keep, where time stands still.",
                "The sunken city of the gods, where the sleeping gods' dreams leak into the waking world.",
                "The throne of the Unsleeping King and the fifth bell."
            ],
            "secrets": [
                "Every boss guarding a bell was once someone who tried to ring it.",
                "Resting at a campfire restores the party but strengthens Aldric's binding.",
                "The gentle flame-tender at the first campfire is Aldric's daughter.",
                "Memories lost to the curse can be found again as ghostly echoes at the places they were lost.",
                "The gods were not bound out of mercy: Aldric did it to steal their immortality."
            ],
            "twists": [
                "The friendly knight who travels with the party fades completely and must be fought.",
                "Aldric is not the king: he is the last loyal guard, sitting on a dead king's throne."
            ],
            "npcs": [
                {
                    "name": "Flame-tender Mira",
                    "role": "Tends the party's campfire and speaks in riddles.",
                    "secret": "Aldric's daughter, who knows a way to end the curse without waking the gods."
                },
                {
                    "name": "Sir Gavren of the Ninth Oath",
                    "role": "A courteous, tired knight who joins the party.",
                    "secret": "He is one death away from fading forever."
                },
                {
                    "name": "Old Crow",
                    "role": "A shady merchant who trades in the Vale's ruins.",
                    "secret": "Sells the souls of fallen marked to Aldric."
                },
                {
                    "name": "King Aldric the Unsleeping",
                    "role": "The ancient ruler on the Vale's throne.",
                    "secret": "Not a king at all, but the last loyal guard."
                }
            ]
        }
    },
    {
        "key": "hundred_year_sleep",
        "name": "The Hundred-Year Sleep",
        "pitch": "The party wakes in an ancient shrine with no memory, a century after they failed to stop a calamity. Explore a wild, overgrown kingdom, recover what they lost and finish what they started.",
        "suggest": {
            "story_type": "sandbox",
            "tone": "heroic"
        },
        "data": {
            "premise": "A hundred years ago the party were the Queen of Aerendell's sworn champions. They failed: the Blight, a living storm of rust and shadow, swallowed the capital, and the champions were sealed in a healing shrine to sleep. Now they wake with no memory, in a kingdom gone wild: villages scattered, ruins overgrown, and the Blight coiled around the old capital. The Queen's voice still calls to them from inside it.",
            "opening": "Light on stone. The party wakes in a pool of glowing water in a cave they don't remember, wearing unfamiliar clothes. A voice in their heads, warm and urgent, says: 'You have to wake up. Please. I can't hold it much longer.' Outside, an endless green kingdom and, on the horizon, a castle wrapped in a swirling dark storm.",
            "villain": "The Blight, the corrupted spirit of the old king's war machine, and its herald, the Rust Knight, who hunts the champions to finish the job.",
            "goal": "The Blight will break free of the Queen's century-long hold and spread across the land. If no one stops it, the whole kingdom rusts and rots to nothing.",
            "ending": "With their memories restored, the party storms the castle. They must face the Blight in the throne room, free the Queen, and decide what to do with the power she has been holding back for a hundred years.",
            "themes": "Wonder and exploration, memory and identity, freedom, hope after failure, the beauty of the wild.",
            "acts": [
                "Waking up; learning to survive in the wild; a kindly old hermit.",
                "A village that remembers the champions as legends.",
                "The first of four great guardian-golems, corrupted, to free.",
                "Shrines that test the party with puzzles and give back memories.",
                "The Rust Knight's ambush, and what he once was.",
                "Freeing the other guardian-golems across mountains, desert and sea.",
                "The castle, the Blight and the Queen."
            ],
            "secrets": [
                "The kindly hermit is the Queen's father, the old king, in a spirit form.",
                "The Rust Knight was one of the champions, the one who didn't make it to the shrine.",
                "The Blight began as a weapon the old king built to protect the kingdom.",
                "Each recovered memory reveals a little more about how the party failed, and why."
            ],
            "twists": [
                "One of the party's own choices, a century ago, let the Blight loose; the memories prove it.",
                "The Queen has been aging inside the storm all along, and has only days left."
            ],
            "npcs": [
                {
                    "name": "Queen Elara",
                    "role": "The voice in the party's heads, holding the Blight back.",
                    "secret": "She is almost out of strength."
                },
                {
                    "name": "The Old Hermit",
                    "role": "A kindly old man on the plateau.",
                    "secret": "The old king's ghost, who built the Blight."
                },
                {
                    "name": "The Rust Knight",
                    "role": "A rusted armoured hunter that stalks the party.",
                    "secret": "Their lost fifth champion, corrupted."
                },
                {
                    "name": "Tamsin Brightwater",
                    "role": "A cheerful young scholar who studies the ruins.",
                    "secret": "Descended from the champions' old quartermaster, with their journals."
                }
            ]
        }
    },
    {
        "key": "dragon_tongue",
        "name": "Tongue of the Wyrm",
        "pitch": "Dragons return to a frozen northern kingdom torn by civil war, and one of the party can speak their ancient language, and steal their power.",
        "suggest": {
            "story_type": "sandbox",
            "tone": "gritty"
        },
        "data": {
            "premise": "The northern kingdom of Hrimgard is splitting between the old king's loyalists and a rebel jarl who wants independence. In the middle of the war, dragons, thought extinct for a thousand years, return to its mountains. One party member (or each, in a small way) begins to understand the dragons' roaring language, and finds that shouting their words carries real power.",
            "opening": "A prisoner cart on a mountain road. The party is about to be executed for crossing the border at the wrong time. Then a black shape blots out the sun and the executioner's block explodes in fire.",
            "villain": "Nyxrath the Devourer, eldest of dragons, returned to rule the world again, and resurrecting the dead dragons one by one.",
            "goal": "Nyxrath will resurrect every dragon and end the age of mortals. If no one stops him, the kingdoms fall while they fight each other.",
            "ending": "On Wyrmspire, the mountain where dragons were first defeated, the party must end Nyxrath with the ancient shout that once banished him, while the loyalists and rebels watch, or join forces.",
            "themes": "Destiny versus choice, power and its cost, civil war, frozen wilds, ancient magic.",
            "acts": [
                "The execution interrupted; escape; a village under dragon threat.",
                "Killing a first dragon and absorbing its power.",
                "Old monks atop a mountain who teach the dragon tongue.",
                "Both sides of the civil war want the party for their cause.",
                "Searching ancient barrows for lost dragon words.",
                "A peace council between loyalists and rebels to face the dragons together.",
                "Wyrmspire."
            ],
            "secrets": [
                "The monks once worked with dragons and can teach the party to tame one, not just kill it.",
                "A dragon in hiding wants Nyxrath dead too and can teach the banishing shout.",
                "The rebel jarl's advisor is a dragon cultist.",
                "The power the party absorbs from dragons slowly makes them more dragon-like."
            ],
            "twists": [
                "The friendly dragon ally asks for something terrible in return: the party member's soul shard.",
                "The loyalist general and the rebel jarl are brothers, and the war began over a death that wasn't murder."
            ],
            "npcs": [
                {
                    "name": "Nyxrath the Devourer",
                    "role": "Eldest of dragons, returned.",
                    "secret": "Can be banished, not killed, by those who know the shout."
                },
                {
                    "name": "Master Hjorvald",
                    "role": "Elder of the mountain monks.",
                    "secret": "Was once Nyxrath's servant, a thousand years ago."
                },
                {
                    "name": "Jarl Ulfgar Stormbrow",
                    "role": "The rebel leader.",
                    "secret": "His closest advisor serves the dragon cult."
                },
                {
                    "name": "Saelvyr the Grey",
                    "role": "A wounded old dragon in hiding.",
                    "secret": "Wants Nyxrath gone, and wants a mortal soul to heal herself."
                }
            ]
        }
    },
    {
        "key": "shelter_seven",
        "name": "Shelter Seven Opens",
        "pitch": "After two hundred years sealed in an underground shelter, the doors open on a wasteland twisted by wild magic, full of mutated beasts, scavenger towns and dangerous factions. Darkly funny.",
        "suggest": {
            "story_type": "wilderness",
            "tone": "gritty"
        },
        "data": {
            "premise": "Two centuries ago a magical war scoured the surface with wild magic. The Gnomish Shelter Company built great sealed shelters for those who could pay. The party were born in Shelter Seven, raised on cheerful instructional songs and canned porridge. Now the shelter's great door has opened, the water purifier has failed, and the Warden sends the party out to find a replacement part.",
            "opening": "Shelter Seven's morning chime. A cheerful voice reminds everyone that today is a wonderful day. Then the lights flicker, the water turns brown, and the Warden hands the party a map from two hundred years ago and a jaunty farewell speech.",
            "villain": "The Warden of Shelter Seven, Mr. Penwick, who has known for years that the surface is habitable and kept everyone inside as part of the Shelter Company's experiment.",
            "goal": "Penwick plans to seal the shelter forever and let everyone inside wither, completing the experiment, once he knows the party is gone. If no one stops him, the party's families die inside.",
            "ending": "The party returns to the shelter with what they've learned, and must stop the Warden, free their families, and choose which surface faction to trust with the shelter's secrets.",
            "themes": "Dark humour, survival, community, corporate cruelty, finding the good in a broken world.",
            "acts": [
                "Leaving the shelter for the first time; a sky that's the wrong colour.",
                "A scavenger town built in a crashed airship, run by a charming crook.",
                "Mutated beasts and wild magic storms in the ruined city.",
                "A knightly order hoarding pre-war magic.",
                "A rival shelter where the experiment went horribly differently.",
                "The truth about the Shelter Company.",
                "Back to Shelter Seven."
            ],
            "secrets": [
                "The water purifier was sabotaged by the Warden to get rid of 'troublemakers'.",
                "Every shelter was an experiment; the party's is about obedience.",
                "The charming crook is a shelter dweller who left years ago and knows a way back in.",
                "A powerful pre-war construct still runs the Shelter Company's offices, and still sends orders."
            ],
            "twists": [
                "The Warden is only following orders from the Shelter Company's construct.",
                "The party's parents knew the truth and stayed for their children."
            ],
            "npcs": [
                {
                    "name": "Warden Penwick",
                    "role": "Shelter Seven's kindly-seeming leader.",
                    "secret": "Running a cruel experiment for the Shelter Company."
                },
                {
                    "name": "Lucky Jack Mercer",
                    "role": "Mayor and crook of the scavenger town.",
                    "secret": "A former Shelter Seven dweller."
                },
                {
                    "name": "Knight-Paladin Rhea Holt",
                    "role": "Leader of a magic-hoarding knightly order.",
                    "secret": "Wants the shelter's sealed magical archives."
                },
                {
                    "name": "COMPANY",
                    "role": "A pre-war construct in a ruined office tower.",
                    "secret": "Still running every shelter's experiment."
                }
            ]
        }
    },
    {
        "key": "drowned_utopia",
        "name": "The City Beneath the Waves",
        "pitch": "A glittering undersea city built by a genius for the brilliant and free, now flooded, broken and ruled by people driven mad by the miracle elixir that built it.",
        "suggest": {
            "story_type": "horror",
            "tone": "dark"
        },
        "data": {
            "premise": "Sixty years ago the alchemist Cassius Rane built Halcyon, a city under the sea where the brilliant could live free of kings and priests. Its miracle was Elan, an elixir that grants extraordinary gifts, and slowly destroys the mind. Now Halcyon is failing: its domes leak, its citizens are twisted by Elan, and its factions wage war in the flooded halls. The party arrive by accident, or on a rescue mission.",
            "opening": "A ship sinks in a storm. The party swims to a lighthouse in the middle of the sea, and inside finds a brass diving bell and a recording: a man's voice welcoming them to a world without chains.",
            "villain": "Cassius Rane, the city's founder, who still believes in his vision and controls Halcyon from its central tower, and Doctor Eleni Voss, the brilliant creator of Elan, who has her own plans.",
            "goal": "Rane will flood the city's lower levels to wipe out the 'unworthy' rather than admit his utopia failed. If no one stops him, thousands of survivors drown.",
            "ending": "In Rane's tower the party learns how they were brought here, and must choose: stop Rane, side with Voss, save the survivors and escape, or take Halcyon for themselves.",
            "themes": "Utopia and its failure, freedom and control, addiction, power and responsibility, art deco dread.",
            "acts": [
                "Arrival by diving bell; a gorgeous, ruined city.",
                "The first Elan-maddened citizens, called the Altered.",
                "A friendly voice on a speaking-tube who guides the party.",
                "A flooded theatre ruled by a mad artist.",
                "The Elan farms and their terrible secret.",
                "Rane's broadcasts grow desperate.",
                "Rane's tower."
            ],
            "secrets": [
                "The friendly voice on the speaking-tube is manipulating the party.",
                "Elan is made from a creature in the deep, and it is aware.",
                "Children in the city are immune to Elan's madness and hold the key to a cure.",
                "The party were not shipwrecked by accident: they were lured."
            ],
            "twists": [
                "The friendly voice is Doctor Voss, who wants Rane dead so she can rule.",
                "One party member was born in Halcyon and smuggled to the surface as a baby."
            ],
            "npcs": [
                {
                    "name": "Cassius Rane",
                    "role": "Founder of Halcyon.",
                    "secret": "Would rather drown the city than see it fail."
                },
                {
                    "name": "Doctor Eleni Voss",
                    "role": "The creator of Elan; the friendly voice on the speaking-tube.",
                    "secret": "Wants to replace Rane."
                },
                {
                    "name": "Sister Lune",
                    "role": "A nun who protects a group of immune children.",
                    "secret": "Has been hiding them from both Rane and Voss."
                },
                {
                    "name": "The Maestro",
                    "role": "A mad, brilliant artist ruling a flooded theatre.",
                    "secret": "Knows a secret way into Rane's tower."
                }
            ]
        }
    },
    {
        "key": "pale_halls",
        "name": "Escape from the Pale Halls",
        "pitch": "The party has died, and wakes in the underworld. Fight up through its realms of the dead, make deals with gods and shades, and when you fall, start again a little wiser.",
        "suggest": {
            "story_type": "dungeon_crawl",
            "tone": "heroic"
        },
        "data": {
            "premise": "The party died together (in a fight, an accident or a betrayal) and wakes in the Pale Halls, the realm of Morvane, god of the dead. Morvane offers a wager: if they escape his realm to the surface, they can live again. If they fall along the way, they wake back in the Halls to try again, remembering what they learned. The way out runs through four realms of the dead, each ruled by a fallen champion.",
            "opening": "A long table in a great black hall, set for a feast. The party sits, confused and translucent. At the head of the table a tall, tired god pours himself wine and says: 'Ah. You're the ones who think you're not supposed to be here. Shall we make it interesting?'",
            "villain": "Morvane, god of the dead, who is lonely, bored and secretly hopes someone will beat his game, and his zealous son, Prince Cael, who wants the party to fail and will cheat to make sure.",
            "goal": "Cael means to keep every soul in the Halls forever and overthrow his father. If no one stops him, the dead can never leave, and the realm of the living fills with ghosts.",
            "ending": "At the gates of dawn, Cael waits. The party can beat him, help Morvane reclaim his realm, or bargain for the freedom of other trapped souls, at a price.",
            "themes": "Persistence, death and life, family, second chances, fun through failure.",
            "acts": [
                "The wager and the first realm: the grey fields of the forgotten.",
                "Dying and returning, with a new boon from a friendly shade.",
                "The burning realm of oath-breakers and its champion.",
                "Meeting the shades of people the party knew in life.",
                "The flooded realm of the drowned, where Cael's cheating becomes clear.",
                "The gods of the surface send gifts to help.",
                "The gates of dawn."
            ],
            "secrets": [
                "Each fall resets the realms, but the shades remember and can be won over between attempts.",
                "Morvane secretly wants them to win: their escape would prove his son wrong.",
                "Cael has been sabotaging the champions to make them stronger against the party.",
                "The party's death was arranged, by someone still alive on the surface."
            ],
            "twists": [
                "One of the four realm champions is the party's killer, also dead.",
                "Winning the wager means another soul must take their place, unless they can change the rules."
            ],
            "npcs": [
                {
                    "name": "Morvane",
                    "role": "God of the dead.",
                    "secret": "Hopes the party will win."
                },
                {
                    "name": "Prince Cael",
                    "role": "Morvane's son.",
                    "secret": "Plans to overthrow his father."
                },
                {
                    "name": "Ione",
                    "role": "A cheerful shade who runs a shop between realms.",
                    "secret": "Was once Morvane's mortal love."
                },
                {
                    "name": "Varos the Oath-Breaker",
                    "role": "Champion of the burning realm.",
                    "secret": "The man who killed the party."
                }
            ]
        }
    },
    {
        "key": "sky_crystals",
        "name": "Crystals of the Sky",
        "pitch": "A ragtag crew with a stolen airship races an empire that is draining the world's elemental crystals to power its war machines, while the world itself starts to die.",
        "suggest": {
            "story_type": "sandbox",
            "tone": "heroic"
        },
        "data": {
            "premise": "The world of Solenne is kept alive by four great elemental crystals: Wind, Water, Fire and Earth. The Engine Empire has learned to drain them to power airships and war-engines. As each crystal dims, its land suffers: winds die, seas still, volcanoes cool, fields wither. The party are rebels, mercenaries and misfits who end up with a stolen imperial airship and a mysterious girl who can hear the crystals.",
            "opening": "A daring raid on an imperial reactor. Alarms, explosions and a girl in chains who whispers 'Take me with you, or the crystal dies.' The party escapes in the first airship they can steal.",
            "villain": "Emperor Halvard Croix and his general, Kael Ardent, a genetically enhanced super-soldier with a terrible secret.",
            "goal": "The Emperor will drain the last crystal to awaken the ancient weapon at the planet's core. If no one stops him, the world dies, and he becomes a god.",
            "ending": "Inside the planet's core, the party faces the Emperor as he merges with the weapon, while Kael chooses a side and the girl decides whether to give her life to restore the crystals.",
            "themes": "Found family, hope against an empire, nature versus industry, destiny, sacrifice.",
            "acts": [
                "The reactor raid and the stolen airship.",
                "The Wind crystal's dying kingdom, and the girl's first vision.",
                "A pirate sky-port; recruiting a crew.",
                "The empire's capital in disguise.",
                "Kael's first confrontation, and his revelation.",
                "The last crystal falls.",
                "The planet's core."
            ],
            "secrets": [
                "The girl is the crystals' guardian, reborn in human form.",
                "Kael was created from the same experiment as the girl.",
                "The ancient weapon is a crystal of its own, the fifth, sleeping and enraged.",
                "The airship the party stole was built for Kael."
            ],
            "twists": [
                "Kael is the girl's brother; they were made together.",
                "The fifth crystal is the planet's heart and can heal the world, or destroy it."
            ],
            "npcs": [
                {
                    "name": "Lumi",
                    "role": "The girl who hears the crystals.",
                    "secret": "The crystals' guardian reborn."
                },
                {
                    "name": "General Kael Ardent",
                    "role": "The Empire's super-soldier.",
                    "secret": "The girl's brother."
                },
                {
                    "name": "Captain Odo Brass",
                    "role": "A grumpy, cigar-chewing airship engineer.",
                    "secret": "Designed the airship the party stole."
                },
                {
                    "name": "The Emperor",
                    "role": "Ruler of the Engine Empire.",
                    "secret": "Wants to become a god."
                }
            ]
        }
    },
]

BY_ID = {f"preset:{p['key']}": p for p in PRESETS}


def listing() -> list[dict]:
    """What the pickers show: id, name, a one-line pitch, and the settings it plays best with."""
    return [{"id": f"preset:{p['key']}", "name": p["name"], "pitch": p["pitch"], "suggest": p.get("suggest") or {}}
            for p in PRESETS]


def entry(pid: str) -> dict | None:
    """A preset shaped like a library entry, for plot.snapshot()."""
    p = BY_ID.get(pid)
    if not p:
        return None
    return {"id": pid, "name": p["name"], "description": p["pitch"], "data": p["data"]}
