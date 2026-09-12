"""
Regions.py Region graph for Kirby: Planet Robobot.

Structure:
  Menu
   -> each Story Level (gated by "Access to LevelN")
        -> each Stage within the level
        -> the level's EX stage (gated by EX handling)
        -> boss
      (each gated by the relevant access item, and only created if the option is on)
"""
from typing import Dict, List

from BaseClasses import Region

from . import Constants as C
from .Locations import LOCATION_TABLE, KirbyRobobotLocation, OPTIONAL_CATEGORIES


def _stages_for_level(level: str) -> List[str]:
    layout = None
    from .Locations import _GAME_DATA
    layout = _GAME_DATA["level_layout"][level]
    stages = [f"Stage{n}" for n in layout["normal"]]
    stages.append(f"Stage{layout['boss']}")
    stages.append(f"Stage{layout['ex']}")
    for extra in layout.get("extra", []):
        stages.append(f"Stage{extra}")
    return stages


def create_regions(world) -> Dict[str, Region]:
    multiworld = world.multiworld
    player = world.player
    options = world.options

    regions: Dict[str, Region] = {}

    def add_region(name: str) -> Region:
        r = Region(name, player, multiworld)
        regions[name] = r
        multiworld.regions.append(r)
        return r

    menu = add_region("Menu")

    # Story levels + stages
    for lv in C.LEVELS:
        add_region(lv)
        for stage in _stages_for_level(lv):
            add_region(f"{lv} {stage}")

    # Attach locations to their regions (respecting option toggles)
    enabled_categories = _enabled_categories(options)
    for name, loc in LOCATION_TABLE.items():
        if loc.category in OPTIONAL_CATEGORIES:
            opt = OPTIONAL_CATEGORIES[loc.category]
            if not getattr(options, opt):
                continue
        if loc.category == "sticker" and not options.sticker_checks:
            continue
        if loc.category == "rare" and not options.rare_sticker_checks:
            continue
        region = regions.get(loc.region, menu)
        ap_loc = KirbyRobobotLocation(player, name, loc.code_offset, region)
        region.locations.append(ap_loc)

    return regions


def _enabled_categories(options) -> set:
    cats = {"cube", "boss", "event"}
    if options.sticker_checks:
        cats.add("sticker")
    if options.rare_sticker_checks:
        cats.add("rare")
    return cats


def connect_regions(world, regions: Dict[str, Region]):
    player = world.player
    options = world.options
    menu = regions["Menu"]

    def connect(source: str, target: str, rule=None):
        if source not in regions or target not in regions:
            return
        regions[source].connect(regions[target], rule=rule)

    from .Locations import _GAME_DATA

    for lv in C.LEVELS:
        # Level 1 is where Kirby starts, so it's always reachable. Other levels
        # are gated by their "Access to LevelN" item. This guarantees a pool of
        # early-reachable locations so progression fill always has somewhere to
        # place the first items.
        if lv == "Level1":
            connect("Menu", lv, rule=None)
        else:
            connect("Menu", lv,
                    # Robobot gates the Areas itself: you need Code Cubes to beat
                    # an Area's boss before the next one opens. So Area access is
                    # a cube requirement, not a separate item.
                    rule=lambda state, lv=lv: _can_reach_area(state, player, lv))

        layout = _GAME_DATA["level_layout"][lv]
        normal = [f"Stage{n}" for n in layout["normal"]]
        boss = f"Stage{layout['boss']}"
        ex = f"Stage{layout['ex']}"

        for stage in normal:
            connect(lv, f"{lv} {stage}")
        # The boss sits behind this Area's Code Cube firewall, exactly as in
        # game. Without this rule logic believed the boss was reachable the
        # moment you entered the Area, so fill was free to put one of the very
        # cubes that opens the firewall behind the boss that the firewall
        # guards, which locks the seed outright.
        connect(lv, f"{lv} {boss}",
                rule=lambda state, lv=lv: _has_boss_cube_gate(state, player, lv))

        # EX stages are unlocked by Code Cubes, exactly as in vanilla there is
        # no separate key item. (An older revision had an "EX Key"; it was
        # redundant with the cube gate, and leaving it referenced here made every
        # EX stage permanently unreachable.)
        connect(lv, f"{lv} {ex}",
                rule=lambda state, lv=lv: _has_ex_cube_threshold(state, player, lv))

        for extra in layout.get("extra", []):
            connect(lv, f"{lv} Stage{extra}")

    # Sub-game hubs
def _can_reach_area(state, player, level: str) -> bool:
    """Can the player get to this Area?

    Robobot opens Area N+1 by beating Area N's boss, and that boss needs a quota
    of Area N's OWN Code Cubes. So reaching Area 4 means having satisfied the
    boss gates of Areas 1, 2 and 3 in turn.

    This used to sum cubes across every Area, which let a late Area's cubes count
    toward opening an early one. That's how a Patched Plains cube could end up
    logically locked behind Rhythm Route: the total looked satisfiable, so fill
    happily put an early requirement somewhere unreachable.
    """
    from . import Constants as _C
    try:
        want = int(level.replace("Level", ""))
    except ValueError:
        return True
    for a in range(1, want):
        lv = f"Level{a}"
        need = _C.AREA_CUBE_COUNTS_REQUIRED.get(lv, 0)
        if state.count(_C.area_cube_name(lv), player) < need:
            return False
    return True


def _cubes_in_ex_stage(level: str) -> int:
    """How many of this Area's cubes physically sit inside its own EX stage."""
    from .Locations import _GAME_DATA
    layout = _GAME_DATA["level_layout"][level]
    ex = f"Stage{layout['ex']}"
    return sum(1 for c in _GAME_DATA["code_cubes"]
               if c["level"] == level and c["stage"] == ex)


def _level_cube_counts(level: str):
    """(cubes in the level's normal stages, total cubes in the level)."""
    from .Locations import _GAME_DATA
    layout = _GAME_DATA["level_layout"][level]
    normals = {f"Stage{n}" for n in layout["normal"]}
    normal_cubes = sum(1 for c in _GAME_DATA["code_cubes"]
                       if c["level"] == level and c["stage"] in normals)
    total = sum(1 for c in _GAME_DATA["code_cubes"] if c["level"] == level)
    return normal_cubes, total


def _has_boss_cube_gate(state, player, level: str) -> bool:
    """Each Area's boss firewall needs that Area's own Code Cubes.

    The numbers come straight from the game's yaml/Scn/LvMap/IcCube.bin.cmp
    (the BossUnlock field per level): 4, 5, 6, 6, 7, 7. They used to be guessed
    at as a percentage of the Area's cubes, which happened to be close for some
    Areas and wrong for others.
    """
    from . import Constants as _C
    need = _C.AREA_CUBE_COUNTS_REQUIRED.get(level, 1)
    return state.count(_C.area_cube_name(level), player) >= need


def _has_ex_cube_threshold(state, player, level: str) -> bool:
    """Vanilla unlocks an Area's EX stage once you hold that Area's normal-stage
    Code Cubes. With per-Area cube items this is directly expressible.

    One catch: some of an Area's cubes physically sit inside that Area's own EX
    stage, so requiring every normal-stage cube leaves zero slack if fill places
    an Area's cube inside its own EX stage, the EX could never be opened. So we
    require the Area's normal-stage cube count minus the number that live in the
    EX stage, which keeps the vanilla feel while staying always satisfiable."""
    from . import Constants as _C
    normal_cubes, _total = _level_cube_counts(level)
    need = max(1, normal_cubes - _cubes_in_ex_stage(level))
    return state.count(_C.area_cube_name(level), player) >= need
