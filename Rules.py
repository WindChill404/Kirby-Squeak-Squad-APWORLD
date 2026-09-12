"""
Rules.py Access rules and win condition for Kirby: Planet Robobot.
"""
from BaseClasses import CollectionState
from worlds.generic.Rules import forbid_item

from . import Constants as C
from .Regions import (_has_ex_cube_threshold, _has_boss_cube_gate,
                      _can_reach_area)
from . import Logic


def _ability_rule(need, player):
    """Turn a requirement into a state test.

    A named ability asks for that item. The ANY_ABILITY sentinel asks only that
    you hold at least one copy ability, which is what a puzzle wants when it
    needs Kirby armed but doesn't care with what.
    """
    if need == C.ANY_ABILITY:
        return lambda state: state.has_any(C.ALL_ABILITY_ITEMS, player)
    return lambda state: state.has(need, player)


def set_rules(world):
    player = world.player
    options = world.options
    multiworld = world.multiworld

    # Location-specific rules that go beyond simple region access.
    from .Locations import LOCATION_TABLE

    def loc_rule(name, rule):
        try:
            multiworld.get_location(name, player).access_rule = rule
        except KeyError:
            pass

    # Star Dream is the goal rather than a location: finishing the game is
    # reported straight from the save flags it sets, so there is nothing here to
    # gate.


    # Vanilla Code Cube gate: each level's boss ("firewall") needs enough cubes.
    # The game enforces this itself, so we only need it in logic that keeps
    # progression faithful to Robobot and means no boss-unlock hacking.
    # Every location's requirements come from Logic, which the tracker in the
    # client also reads. Keeping one description means the tracker cannot tell
    # the player a location is open when generation thought otherwise.
    opts = {
        "ability_gating": bool(options.ability_gating),
        "armor_gating": bool(options.armor_gating),
        "goal": int(options.goal),
        "story_boss_count": int(options.story_boss_count.value),
    }

    def _adapter(state):
        return (lambda n: state.has(n, player),
                lambda n: state.count(n, player))

    for loc_name, d in LOCATION_TABLE.items():
        reqs = Logic.location_requirements(loc_name, d, opts)
        if not reqs:
            continue

        def rule(state, reqs=reqs):
            has, count = _adapter(state)
            return Logic.satisfied(reqs, has, count)

        loc_rule(loc_name, rule)

        # An item may not be placed at a location that needs that same item.
        # The any-ability marker names no particular item, so nothing to forbid.
        for need in reqs:
            if need == C.ANY_ABILITY or need.startswith(
                    (Logic.AREA_PREFIX, Logic.BOSS_PREFIX, Logic.EX_PREFIX)):
                continue
            try:
                forbid_item(multiworld.get_location(loc_name, player),
                            need, player)
            except KeyError:
                pass

    # An Area's boss is opened by that Area's own Code Cubes, so putting one of
    # those cubes behind that same boss makes the boss partly guard its own key.
    # Logic no longer allows that to deadlock, but it still reads badly in play,
    # so the Area's cubes are kept off its boss and EX clears entirely.
    for lv in C.LEVELS:
        cube = C.area_cube_name(lv)
        for suffix in ("Boss Clear", "EX Stage Clear"):
            nm = f"{C.area_name(lv)} {suffix}"
            try:
                forbid_item(multiworld.get_location(nm, player), cube, player)
            except KeyError:
                pass

    multiworld.completion_condition[player] = lambda state: _goal_met(state, world)


def _story_bosses_defeatable(state, player) -> int:
    """How many Area bosses the player could actually beat with what they hold.

    Reaching an Area is not the same as beating its boss: the boss sits behind
    that Area's own Code Cube firewall. Counting only reachability said you
    could beat Patched Plains' boss the moment the game started, with no cubes
    at all, which made a low boss count goal look satisfied before it was.
    """
    count = 0
    for lv in C.LEVELS:
        if _can_reach_area(state, player, lv) and _has_boss_cube_gate(state, player, lv):
            count += 1
    return count


def _goal_met(state: CollectionState, world) -> bool:
    player = world.player
    goal = world.options.goal

    if goal == 0:  # story_star_dream
        return _can_reach_area(state, player, "Level6")
    if goal == 1:  # story_boss_count
        needed = world.options.story_boss_count.value
        return _story_bosses_defeatable(state, player) >= needed
    return False
