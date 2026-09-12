"""
Locations.py Location table for Kirby: Planet Robobot.

Locations fall into these groups:
  * Code Cube locations (100)          always on
  * Normal Sticker locations (138)     always on
  * Rare Sticker locations (35)        always on
  * All-Cubes reward (1)               always on
  * Story boss / stage clears          always on
  * EX-stage unlocks (per level)       always on
  * Kirby 3D Rumble (3)                optional
  * Team Kirby Clash (6)               optional
  * Meta Knightmare Returns (6)        optional
  * The Arena (11)                     optional
  * The True Arena (12)                optional

Each location carries the ROM coordinates (file / index / wuid) needed by the
patcher so the in-stage item can be swapped for an AP check.
"""
import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from BaseClasses import Location

from . import Constants as C

BASE_ID = 0x4B5000  # same region as items; location ids are BASE_ID + offset

import pkgutil

def _load_game_data():
    # Works whether the world is a folder or a zipped .apworld: read the JSON as
    # package data rather than via a filesystem path.
    raw = pkgutil.get_data(__package__, "data/game_data.json")
    return json.loads(raw.decode("utf-8"))

_GAME_DATA = _load_game_data()


class KirbyRobobotLocation(Location):
    game = C.GAME_NAME


@dataclass
class LocData:
    name: str
    region: str
    category: str                    # cube/sticker/rare/boss/subgame/etc
    # ROM patch coordinates (None for event/clear locations detected via save flags)
    file: Optional[str] = None
    index: Optional[int] = None
    wuid: Optional[int] = None
    appear: str = "All"
    code_offset: Optional[int] = None
    # --- runtime memory mapping (filled for cubes / stickers) ---
    level: Optional[str] = None       # "Level1".."Level6"
    stage: Optional[str] = None       # "Stage1"..
    slot_index: Optional[int] = None  # which of the 3 cubes in that stage
    stage_index: Optional[int] = None # game's flat stage index (level*stages + n)
    sticker_index: Optional[int] = None  # index into the 200-entry sticker array
    # --- per-stage clear locations ---
    area: Optional[int] = None        # 1..6 (Area number)
    stage_no: Optional[int] = None    # 1-based stage number within the Area


def _build_stage_bases() -> Dict[str, int]:
    """Flat stage index the game uses: cubes live at base + stage_index*8.

    This is no longer inferred it comes straight from the game's own
    Cmn.StoryStageKind enum (extracted from mint/Default.bin), which maps
    L1S1=0 ... L1S6=5, L2S1=6 ... L2S6=11, L3S1=12 ... L3S7=18, and so on.
    It matches what we verified live on a real save (Area 1 = 9 cubes across
    indices 0-5, Area 2 = 6 cubes across 6-11).
    """
    kinds = _GAME_DATA.get("enums", {}).get("StoryStageKind", {})
    bases: Dict[str, int] = {}
    for lvl_num in range(1, 7):
        first = kinds.get(f"L{lvl_num}S1")
        if first is not None:
            bases[f"Level{lvl_num}"] = first
    return bases


STAGE_BASES = _build_stage_bases()


def _stage_index(level: str, stage: str) -> Optional[int]:
    """'Level2','Stage3' -> the game's flat StoryStageKind index."""
    kinds = _GAME_DATA.get("enums", {}).get("StoryStageKind", {})
    try:
        lvl_num = int(level.replace("Level", ""))
        stg_num = int(stage.replace("Stage", ""))
    except ValueError:
        return None
    return kinds.get(f"L{lvl_num}S{stg_num}")


def _level_region(level: str, stage: str = None) -> str:
    return level if stage is None else f"{level} {stage}"


def build_location_table() -> Dict[str, LocData]:
    table: Dict[str, LocData] = {}

    # --- Code Cubes (100) ---
    # Named the way the game does: "Patched Plains Stage 2 - Code Cube 1".
    for i, cube in enumerate(_GAME_DATA["code_cubes"]):
        name = (f"{C.area_name(cube['level'])} "
                f"Stage {C.stage_num(cube['stage'])} - "
                f"Code Cube {cube['slotIndex'] + 1}")
        table[name] = LocData(
            name, _level_region(cube["level"], cube["stage"]), "cube",
            file=cube["file"], index=cube["index"], wuid=cube["wuid"],
            appear=cube["appear"],
            level=cube["level"], stage=cube["stage"],
            slot_index=cube["slotIndex"],
            stage_index=_stage_index(cube["level"], cube["stage"]))

    # --- Rare Stickers (35) ---
    # "Rare Sticker: Ultra Sword (1-2)" the sticker's real name plus its stage.
    for rare in _GAME_DATA["rare_stickers"]:
        sticker = C.RARE_STICKER_NAMES.get(rare["rareKind"], rare["subKind"])
        name = (f"Rare Sticker: {sticker} "
                f"({C.area_num(rare['level'])}-{C.stage_num(rare['stage'])})")
        table[name] = LocData(
            name, _level_region(rare["level"], rare["stage"]), "rare",
            file=rare["file"], index=rare["index"], wuid=rare["wuid"],
            appear=rare["appear"],
            level=rare["level"], stage=rare["stage"],
            # Index into the 200-entry sticker array at save+0x82. Taken from the
            # game's own romfs/yaml/Cmn/Sticker/Config.bin (stepRareKind field) and
            # cross-checked against a live save (Rare019 -> index 89) and the
            # community walkthrough's rare-sticker list.
            sticker_index=rare["albumIndex"],
            # Rare stickers you were SENT stay in your album permanently, so the
            # album bit can no longer signal "found the physical one". These
            # numbers let the client fall back to the stage's clear flag, which
            # keeps the location obtainable either way.
            area=C.area_num(rare["level"]),
            stage_no=C.stage_num(rare["stage"]))

    # --- Normal Stickers (165) ---
    # A normal sticker pickup doesn't award a *specific* sticker: the game draws
    # one from a pool (Cmn.Sticker.LotteryUtil). So "the sticker in stage X" isn't
    # a stable thing to check for. What IS stable is the sticker itself: album
    # slot N flipping to owned is a unique, identifiable event. So each sticker in
    # the album is its own location, named for the sticker you actually got.
    #
    # Ten of them share a display name with another sticker ("Kirby" appears six
    # times, from six different games). Location names have to be unique, so those
    # duplicates used to overwrite each other and simply vanish from the pool.
    # Any name used more than once is therefore tagged with its source game.
    _album_normal = [e for e in _GAME_DATA["sticker_album"] if not e["rare"]]
    _name_counts = {}
    for entry in _album_normal:
        _name_counts[entry["name"]] = _name_counts.get(entry["name"], 0) + 1
    for entry in _album_normal:
        base_name = entry["name"]
        if _name_counts[base_name] > 1:
            game = C.sticker_source_game(entry.get("internal", ""))
            name = (f"Sticker: {base_name} ({game})" if game
                    else f"Sticker: {base_name} #{entry['index']}")
        else:
            name = f"Sticker: {base_name}"
        table[name] = LocData(
            name, "Menu", "sticker",
            sticker_index=entry["index"])

    # --- Per-stage clears (every stage, including boss and EX) ---------------
    # Detected from the save's stage array: byte 7 of each stage's 8-byte row.
    # Named the way the game presents them, e.g. "Patched Plains Stage 1 Clear".
    # Each Area's rows run: normal stages, then the boss, then EX. So the last
    # two of every Area are not "Stage 5" and "Stage 6", they're the boss fight
    # and the EX stage, and naming them by number was misleading.
    # Each Area's rows run: normal stages, then the boss, then EX. Access Ark is
    # the exception, with two more stages after its EX, so the boss and EX are
    # NOT simply the last two there. Assuming they were made "Access Ark Boss
    # Clear" point at a trailing stage while the real boss was published as
    # "Stage 6 Clear", so the boss check fired for the wrong thing entirely.
    # Positions come from the game's own layout rather than being counted from
    # the end.
    for _area in range(1, 7):
        _lv = f"Level{_area}"
        _layout = _GAME_DATA["level_layout"][_lv]
        _boss_no = _layout["boss"]
        _ex_no = _layout["ex"]
        _count = len(_layout["normal"]) + 2 + len(_layout.get("extra", []))
        for _st in range(1, _count + 1):
            if _st == _boss_no:
                _nm = f"{C.area_name(_lv)} Boss Clear"
            elif _st == _ex_no:
                _nm = f"{C.area_name(_lv)} EX Stage Clear"
            else:
                _nm = f"{C.area_name(_lv)} Stage {_st} Clear"
            table[_nm] = LocData(_nm, _lv, "stage_clear",
                                 area=_area, stage_no=_st)

    # Two sets of locations used to live here and both are gone.
    #
    # "Unlock <Area> EX Stage": nothing in game corresponds to it. The EX stage
    # simply opens once you hold enough of that Area's Code Cubes, so there was
    # no moment to detect and the check could never be sent.
    #
    # "Clear <Level> (Boss Defeated)": the same event as that Area's Boss Clear
    # above, listed twice. Only the stage-clear version is ever detected, so the
    # duplicate sat in every seed as a check that could not be earned.

    # Sub-game locations (3D Rumble, Team Kirby Clash, Meta Knightmare, The
    # Arena, The True Arena) are not included. Detecting them needs save offsets
    # for each sub-game's progress, which we haven't located, so they could never
    # actually be checked.

    # Assign stable IDs
    for offset, name in enumerate(sorted(table.keys())):
        table[name].code_offset = BASE_ID + offset

    return table


LOCATION_TABLE: Dict[str, LocData] = build_location_table()
LOCATION_NAME_TO_ID: Dict[str, int] = {
    n: d.code_offset for n, d in LOCATION_TABLE.items()
}

# Category -> option name that toggles it (None = always on)
OPTIONAL_CATEGORIES = {
    "subgame_rumble": "include_3d_rumble",
    "subgame_clash": "include_kirby_clash",
    "subgame_meta": "include_meta_knightmare",
    "subgame_arena": "include_arena",
    "subgame_true_arena": "include_true_arena",
}
