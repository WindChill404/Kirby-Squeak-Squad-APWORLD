"""
Items.py Item table for Kirby: Planet Robobot AP world.

Item ID space starts at BASE_ID. IDs are assigned deterministically so that
seeds remain compatible as long as the ordering here does not change.
"""
from dataclasses import dataclass
from typing import Dict, List, Optional

from BaseClasses import Item, ItemClassification

from . import Constants as C

BASE_ID = 0x4B5000  # "KP" region, arbitrary but stable


class KirbyRobobotItem(Item):
    game = C.GAME_NAME


@dataclass
class ItemData:
    name: str
    classification: ItemClassification
    count: int = 1          # how many copies exist in the pool by default
    code_offset: Optional[int] = None  # filled in at module load


# Progression items -----------------------------------------------------------
_PROGRESSION: List[str] = []
_USEFUL: List[str] = []
_FILLER: List[str] = []

# NOTE on Area/EX gating:
# Robobot already gates progression itself each Area's boss ("firewall") needs
# a number of Code Cubes, and an Area's EX stage needs *all* of that Area's
# normal-stage cubes. Adding separate "Access to Area" and "EX Key" items on top
# would be double-gating and less faithful to the game, so they're gone: Code
# Cubes are the progression currency, exactly as in vanilla.

# Copy abilities (27) progression because logic can require them
for ab in C.COPY_ABILITIES:
    _PROGRESSION.append(f"Ability: {ab}")

# The Robobot Armor itself is NOT an item you get it when the game gives it to
# you, as in vanilla. Only its individual modes are shuffled.
# (14 modes)
# items so the player physically regains armor use)
for m in C.ARMOR_MODES:
    _PROGRESSION.append(f"Armor Mode: {m}")

# The sub-game access items (3D Rumble, Team Kirby Clash, Meta Knightmare, both
# Arenas) used to live here, and so did an Ability Testing Room Key. None of them
# did anything: we never found the save offsets that record that progress, so
# receiving one had no effect in game and its location could not be checked.
# They're out until those offsets are known, rather than sitting in the pool as
# dead items taking up space that real checks could use.

# 100 Code Cubes are progression (they unlock EX stages via count thresholds)
CODE_CUBE = C.CODE_CUBE

# 36 Rare Stickers: 35 in-stage + the all-cubes reward. Each is its own named
# item ("Rare Sticker: Ultra Sword"), so receiving one puts that exact sticker in
# your album.
RARE_STICKER_ITEMS = [f"Rare Sticker: {n}" for n in C.RARE_STICKER_NAMES.values()]

# Normal stickers, one item per album slot, named for the sticker itself.
def _normal_sticker_items():
    from .Locations import _GAME_DATA
    # Names must match the location names exactly (see Locations.py): stickers
    # whose display name is shared with another sticker are tagged with their
    # source game, otherwise duplicates collapse into one entry.
    album = [e for e in _GAME_DATA["sticker_album"] if not e["rare"]]
    counts = {}
    for e in album:
        counts[e["name"]] = counts.get(e["name"], 0) + 1
    out = []
    for e in album:
        if counts[e["name"]] > 1:
            game = C.sticker_source_game(e.get("internal", ""))
            out.append(f"Sticker: {e['name']} ({game})" if game
                       else f"Sticker: {e['name']} #{e['index']}")
        else:
            out.append(f"Sticker: {e['name']}")
    return out


NORMAL_STICKER_ITEMS = _normal_sticker_items()

# Filler items used to pad the pool so item/location counts match.
# All are real in-game item kinds the bridge can spawn on receipt.
ONE_UP = "1-Up"
MAXIM_TOMATO = C.MAXIM_TOMATO      # full heal
ENERGY_DRINK = C.ENERGY_DRINK      # restores 1/2
INVINCIBLE_CANDY = C.INVINCIBLE_CANDY   # temporary invincibility

# Real in-game foods (each restores 1/5 health) instead of a generic "Food".
FOOD_ITEMS = list(C.FOOD_ITEMS)

# Ordered by preference when padding: the ordinary foods first (they're the most
# common pickup in the game), then 1-Ups, then the stronger heals and candy.
FILLER_ITEMS = FOOD_ITEMS + [ONE_UP, ENERGY_DRINK, MAXIM_TOMATO, INVINCIBLE_CANDY]


def build_item_table() -> Dict[str, ItemData]:
    table: Dict[str, ItemData] = {}

    # Copy abilities and most armor modes are 'useful': nice to have, never the
    # only way into a location.
    #
    # The exception is an armor mode a stage is built around. 2-2 and 4-4 are
    # Jet Mode stages, and everything in them sits inside the flying section, so
    # Jet really is the key to those locations. Left as merely useful, fill was
    # free to put Jet inside 2-2 itself, which made 2-2 need Jet to get Jet and
    # generation rightly complained that those locations were unreachable.
    _GATING_ARMOR = {"Armor Mode: %s" % m
                     for m in C.STAGE_ARMOR_REQUIREMENT.values()}
    _GATING_ARMOR |= {"Armor Mode: %s" % m
                      for m in C.CUBE_ARMOR_REQUIREMENT.values()}
    _GATING_ARMOR |= {"Armor Mode: %s" % m
                      for m in C.RARE_STICKER_ARMOR_REQUIREMENT.values()}
    # Copy abilities that a cube's puzzle genuinely requires must be progression
    # too, for the same reason: if Sword stays merely useful, fill can drop it
    # inside the very cube that needs Sword, and generation fails.
    # The ANY_ABILITY sentinel names no particular item, so it contributes
    # nothing here: a spot that takes any ability is satisfied by whichever one
    # the seed happens to give you.
    _GATING_ABILITY = {"Ability: %s" % ab
                       for ab in C.CUBE_ABILITY_REQUIREMENT.values()
                       if ab != C.ANY_ABILITY}
    _GATING_ABILITY |= {"Ability: %s" % ab
                        for ab in C.RARE_STICKER_ABILITY_REQUIREMENT.values()
                        if ab != C.ANY_ABILITY}
    _USEFUL_PREFIXES = ("Ability: ", "Armor Mode: ")
    for name in _PROGRESSION:
        if name in _GATING_ARMOR or name in _GATING_ABILITY:
            table[name] = ItemData(name, ItemClassification.progression)
        elif name.startswith(_USEFUL_PREFIXES):
            table[name] = ItemData(name, ItemClassification.useful)
        else:
            table[name] = ItemData(name, ItemClassification.progression)

    # Code Cubes: per-Area items (matching vanilla cube counts) so each Area's
    # boss firewall counts only its own cubes. progression_skip_balancing so they
    # gate bosses/EX without distorting fill balancing.
    for _lv, _cnt in C.AREA_CUBE_COUNTS.items():
        _nm = C.area_cube_name(_lv)
        table[_nm] = ItemData(
            _nm, ItemClassification.progression_skip_balancing, count=_cnt)

    # Rare stickers, named for the sticker you actually get. All stickers are
    # filler: they're collectibles, never gate anything.
    for nm in RARE_STICKER_ITEMS:
        table[nm] = ItemData(nm, ItemClassification.filler)

    # Normal stickers, likewise one named item each.
    for nm in NORMAL_STICKER_ITEMS:
        table[nm] = ItemData(nm, ItemClassification.filler)
    # NOTE: there is deliberately no "all cubes" reward item. It had no
    # matching location, so it could be received but never checked.

    # Filler items (count=0: created on demand to pad the pool)
    for filler_name in FILLER_ITEMS:
        table[filler_name] = ItemData(
            filler_name, ItemClassification.filler, count=0)

    # Assign stable IDs
    for offset, name in enumerate(sorted(table.keys())):
        table[name].code_offset = BASE_ID + offset

    return table


ITEM_TABLE: Dict[str, ItemData] = build_item_table()
ITEM_NAME_TO_ID: Dict[str, int] = {
    name: data.code_offset for name, data in ITEM_TABLE.items()
}
