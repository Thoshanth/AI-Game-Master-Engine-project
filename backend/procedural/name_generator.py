import random
import hashlib
from backend.logger import get_logger

logger = get_logger("procedural.names")

# Syllable pools by culture/biome
# Each culture has prefixes, middles, and suffixes
CULTURE_SYLLABLES = {
    "human": {
        "prefixes": [
            "Al", "Bram", "Cor", "Dal", "Ed", "Fal", "Gor",
            "Hal", "Ire", "Jed", "Kar", "Lorn", "Mar", "Nor",
            "Old", "Pell", "Roth", "Stor", "Tal", "Urd", "Val",
            "Wren", "Yor", "Zeth",
        ],
        "middles": [
            "den", "fen", "gar", "hold", "kel", "mor", "rath",
            "sten", "tor", "ven", "wick", "worth",
        ],
        "suffixes": [
            "bridge", "burg", "dale", "falls", "ford", "gate",
            "ham", "haven", "keep", "moor", "port", "rock",
            "shire", "stead", "ton", "vale", "ville", "watch",
        ],
    },
    "elven": {
        "prefixes": [
            "Aer", "Cael", "Dael", "Eil", "Faer", "Gal",
            "Ith", "Lael", "Mael", "Naer", "Quel", "Rael",
            "Sael", "Tael", "Uel", "Vael", "Yael", "Zel",
        ],
        "middles": [
            "ath", "dor", "eth", "iel", "ith", "lor", "mel",
            "nar", "oel", "ril", "sel", "thal", "uel", "vel",
        ],
        "suffixes": [
            "ador", "aen", "aith", "alas", "alor", "amis",
            "anar", "aras", "aris", "dor", "elor", "enas",
            "iel", "ilas", "ilor", "inar", "iras", "orel",
        ],
    },
    "dwarven": {
        "prefixes": [
            "Bor", "Dur", "Gim", "Grond", "Kaz", "Khaz",
            "Mor", "Thur", "Tor", "Unn", "Vor", "Zor",
        ],
        "middles": [
            "ak", "dim", "dur", "gal", "grim", "hold",
            "kul", "mur", "rak", "rok", "rum", "tur",
        ],
        "suffixes": [
            "ak", "bara", "dum", "dun", "grad", "grim",
            "hold", "khal", "kor", "mur", "rak", "rim",
            "rok", "thak", "thar", "thor", "tur", "zar",
        ],
    },
    "dark": {
        "prefixes": [
            "Ash", "Blight", "Crypt", "Death", "Dread",
            "Fell", "Grim", "Hollow", "Malice", "Nether",
            "Shadow", "Skull", "Spite", "Terror", "Void",
        ],
        "middles": [
            "bone", "dark", "fell", "gloom", "gore",
            "grave", "mire", "murk", "reek", "rot",
            "shade", "shroud", "slaughter", "wither",
        ],
        "suffixes": [
            "abyss", "bane", "barrow", "bog", "chasm",
            "deep", "fall", "gate", "maw", "mere",
            "pit", "ravine", "ruin", "sink", "spire",
        ],
    },
    "coastal": {
        "prefixes": [
            "Bay", "Cape", "Crest", "Cove", "Drift",
            "Gull", "Harbour", "Mast", "Reef", "Salt",
            "Sea", "Shore", "Storm", "Tide", "Wave",
        ],
        "middles": [
            "anchor", "beacon", "break", "cliff", "crest",
            "drift", "fall", "gale", "mist", "rock",
            "sand", "spray", "surge", "swell", "watch",
        ],
        "suffixes": [
            "bay", "bluff", "cove", "creek", "dock",
            "haven", "inlet", "isle", "landing", "point",
            "port", "reach", "shore", "sound", "wharf",
        ],
    },
}

# NPC first name pools by culture
NPC_NAMES = {
    "human_male": [
        "Aldric", "Bram", "Cael", "Dorn", "Edmund", "Finn",
        "Gareth", "Hadwin", "Ivan", "Jasper", "Keld", "Leoric",
        "Marcus", "Nael", "Owen", "Pell", "Rolf", "Soren",
        "Theron", "Ulric", "Vance", "Wynn", "Xander", "Yoren",
    ],
    "human_female": [
        "Alara", "Brynn", "Cora", "Delia", "Elara", "Faye",
        "Gwen", "Hilda", "Isolde", "Jana", "Kira", "Lyra",
        "Mara", "Nessa", "Ophel", "Petra", "Rhea", "Sera",
        "Tara", "Una", "Vera", "Wren", "Xena", "Yara",
    ],
    "neutral": [
        "Aiden", "Blair", "Casey", "Drew", "Emery", "Finley",
        "Gray", "Harper", "Indigo", "Jordan", "Kendall", "Lane",
        "Morgan", "Noel", "Onyx", "Page", "Quinn", "Reed",
        "Sage", "Taylor", "Uma", "Vale", "Winter", "Zephyr",
    ],
}

# Surname pools
SURNAMES = [
    "Ashwood", "Blackthorn", "Coldwater", "Dawnbringer",
    "Emberveil", "Frostborn", "Grimstone", "Halfmoon",
    "Ironforge", "Jadeheart", "Kindlewick", "Lightbane",
    "Moonshadow", "Nightfall", "Oakhaven", "Pyrebrand",
    "Quicksilver", "Ravenmoor", "Silverwind", "Thornwall",
    "Underhill", "Voidwalker", "Wintermere", "Xenobrook",
]

# Item name components
ITEM_PREFIXES = {
    "weapon": [
        "Ancient", "Blessed", "Cursed", "Dark", "Eldritch",
        "Fallen", "Gilded", "Hollow", "Iron", "Jagged",
        "Keen", "Lost", "Mythril", "Obsidian", "Phantom",
        "Runed", "Shadow", "Thorn", "Void", "War",
    ],
    "armor": [
        "Ancient", "Battle-worn", "Cursed", "Dragon-scale",
        "Enchanted", "Forged", "Guardian", "Heavy", "Iron",
        "Knight's", "Layered", "Mythril", "Noble", "Ornate",
        "Plate", "Royal", "Shadow", "Templar", "Undying",
    ],
    "potion": [
        "Alchemist's", "Bottled", "Concentrated", "Diluted",
        "Elixir of", "Foul", "Greater", "Hunter's", "Inferior",
        "Legendary", "Minor", "Noxious", "Potent", "Rare",
        "Superior", "Thick", "Unusual", "Volatile", "Wicked",
    ],
}


def generate_location_name(
    terrain: str = "plains",
    location_type: str = "city",
    culture: str = "human",
    seed: str = None,
) -> str:
    """
    Generates a consistent location name based on terrain and culture.
    Same seed always produces same name — ensures consistency.
    """
    if seed:
        random.seed(int(hashlib.md5(seed.encode()).hexdigest(), 16))

    # Select culture syllable set
    syllables = CULTURE_SYLLABLES.get(
        culture,
        CULTURE_SYLLABLES["human"]
    )

    # Dungeons use dark naming
    if location_type in ["dungeon", "ruins"]:
        syllables = CULTURE_SYLLABLES["dark"]

    if location_type in ["city", "village", "market"]:
        # City pattern: Prefix + Middle + Suffix
        prefix = random.choice(syllables["prefixes"])
        if random.random() > 0.5:
            middle = random.choice(syllables["middles"])
            suffix = random.choice(syllables["suffixes"])
            name = f"{prefix}{middle} {suffix.title()}"
        else:
            suffix = random.choice(syllables["suffixes"])
            name = f"{prefix}{suffix.title()}"

    elif location_type in ["dungeon", "ruins", "cave"]:
        # Dungeon pattern: "The [Dark adjective] [Noun]"
        prefix = random.choice(syllables["prefixes"])
        middle = random.choice(syllables["middles"])
        suffix = random.choice(syllables["suffixes"])
        articles = ["The", "The Ancient", "The Cursed", "The Forgotten"]
        name = f"{random.choice(articles)} {prefix}{middle} {suffix.title()}"

    elif location_type == "tavern":
        # Tavern pattern: "The [Adjective] [Noun]"
        adj = random.choice([
            "Golden", "Silver", "Iron", "Rusty", "Broken",
            "Laughing", "Weeping", "Wandering", "Lost", "Last",
        ])
        noun = random.choice([
            "Flagon", "Sword", "Shield", "Crown", "Compass",
            "Dragon", "Coin", "Barrel", "Lantern", "Pilgrim",
        ])
        name = f"The {adj} {noun}"

    else:
        prefix = random.choice(syllables["prefixes"])
        suffix = random.choice(syllables["suffixes"])
        name = f"{prefix}{suffix.title()}"

    # Reset random seed
    random.seed()

    logger.debug(f"Location name generated | name='{name}' | type={location_type}")
    return name


def generate_npc_name(
    gender: str = "neutral",
    culture: str = "human",
    seed: str = None,
) -> str:
    """Generates a consistent NPC name."""
    if seed:
        random.seed(int(hashlib.md5(seed.encode()).hexdigest(), 16))

    # First name
    if gender == "male":
        first = random.choice(NPC_NAMES["human_male"])
    elif gender == "female":
        first = random.choice(NPC_NAMES["human_female"])
    else:
        first = random.choice(NPC_NAMES["neutral"])

    # Surname (not always present)
    if random.random() > 0.4:
        last = random.choice(SURNAMES)
        name = f"{first} {last}"
    else:
        name = first

    random.seed()
    return name


def generate_item_name(
    item_type: str = "weapon",
    rarity: str = "common",
    seed: str = None,
) -> str:
    """Generates a consistent item name."""
    if seed:
        random.seed(int(hashlib.md5(seed.encode()).hexdigest(), 16))

    prefixes = ITEM_PREFIXES.get(item_type, ITEM_PREFIXES["weapon"])

    weapon_bases = [
        "Sword", "Blade", "Dagger", "Axe", "Mace", "Spear",
        "Bow", "Staff", "Wand", "Hammer", "Rapier", "Scythe",
    ]
    armor_bases = [
        "Helmet", "Chestplate", "Gauntlets", "Greaves", "Shield",
        "Cloak", "Boots", "Pauldrons", "Vambrace", "Cuirass",
    ]
    potion_bases = [
        "Health", "Mana", "Strength", "Speed", "Invisibility",
        "Fire Resistance", "Night Vision", "Regeneration",
    ]

    if item_type == "weapon":
        base = random.choice(weapon_bases)
    elif item_type == "armor":
        base = random.choice(armor_bases)
    elif item_type == "potion":
        base = random.choice(potion_bases)
        random.seed()
        return f"{random.choice(prefixes)} {base} Potion"
    else:
        base = random.choice(weapon_bases)

    prefix = random.choice(prefixes)
    name = f"{prefix} {base}"

    # Legendary items get special naming
    if rarity == "legendary":
        legendary_names = [
            "Worldbreaker", "Soulreaver", "Dawnbringer",
            "Voidcleaver", "Deathwhisper", "Truthseeker",
            "Heartsbane", "Fateweaver", "Shadowmend",
        ]
        name = random.choice(legendary_names)

    random.seed()
    return name