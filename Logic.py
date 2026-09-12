"""One description of what each location needs.

Both sides of this world ask the same question, "can I get that yet", and they
have to answer it identically. Generation asks it to decide where items may go;
the tracker tab in the client asks it to tell the player what to go and do. If
those two ever disagree the tracker is worse than useless, because it sends
people to locations the seed never intended them to reach.

So the answer lives here once. Rules.py turns what this returns into access
rules for the generator, and the tracker feeds it the items you have actually
received. Neither carries its own copy of the reasoning.

Requirements are returned as plain item names, plus two markers that mean more
than "hold this item":

  ANY_ABILITY  hold at least one copy ability, no particular one
  area:<Level> that Area has to be reachable at all
  boss:<Level> that Area's Code Cube firewall has to be open
  ex:<Level>   that Area's EX stage has to be open
"""

from . import Constants as C

ANY_OF_PREFIX = "anyof:"
AREA_PREFIX = "area:"
BOSS_PREFIX = "boss:"
EX_PREFIX = "ex:"


def _stage_no(stage: str):
    try:
        return int(stage.replace("Stage", ""))
    except (ValueError, AttributeError):
        return None


def location_requirements(loc_name, d, opts):
    """Everything a location needs, as a list of requirement tokens.

    opts is a plain dict so this works from slot data in the client as readily
    as from the options object during generation.
    """
    reqs = []
    lv = getattr(d, "level", None)
    # Stage clears carry their Area as a number rather than a level string, so
    # recover it. Without this every requirement below was skipped for them, and
    # boss and EX clears came out with no requirements at all.
    if lv is None and getattr(d, "area", None):
        lv = "Level%d" % d.area
    st = getattr(d, "stage", None)
    cat = getattr(d, "category", None)
    slot = getattr(d, "slot_index", None)
    ability_gating = bool(opts.get("ability_gating"))
    armor_gating = bool(opts.get("armor_gating"))

    if lv:
        reqs.append(AREA_PREFIX + lv)

    # The boss of an Area sits behind that Area's own cube firewall.
    if cat == "boss" and lv:
        reqs.append(BOSS_PREFIX + lv)

    # Stage clears name the Area and a stage number rather than carrying level
    # and stage fields, so the boss and EX ones are recognised by name.
    if cat == "stage_clear" and lv:
        if loc_name.endswith("Boss Clear"):
            reqs.append(BOSS_PREFIX + lv)
        elif loc_name.endswith("EX Stage Clear"):
            for r in _ex_prereqs(lv, opts):
                if r not in reqs:
                    reqs.append(r)

    # Anything physically inside an EX stage needs that EX stage open.
    if lv and st is not None:
        from .Locations import _GAME_DATA
        layout = _GAME_DATA["level_layout"].get(lv)
        if layout and _stage_no(st) == layout["ex"]:
            # Anything inside an EX stage, cube or Rare Sticker alike, waits on
            # the same thing the EX stage itself does.
            for r in _ex_prereqs(lv, opts):
                if r not in reqs:
                    reqs.append(r)

    if armor_gating:
        if cat == "cube" and lv and st and slot is not None:
            need = C.armor_item_for_cube(lv, st, slot + 1)
            if need:
                reqs.append(need)
        if lv and st:
            mode = C.STAGE_ARMOR_REQUIREMENT.get((lv, st))
            if mode:
                reqs.append(f"Armor Mode: {mode}")
        if cat == "rare" and lv and st:
            need = C.armor_item_for_rare_sticker(lv, st)
            if need:
                reqs.append(need)
        # Stage clears for a mode-built stage, matched by name.
        if cat == "stage_clear" and lv:
            for (mlv, mst), mode in C.STAGE_ARMOR_REQUIREMENT.items():
                n = _stage_no(mst)
                if mlv == lv and n is not None and \
                        loc_name == f"{C.area_name(mlv)} Stage {n} Clear":
                    reqs.append(f"Armor Mode: {mode}")

    # Some spots take any one of several things. 1-2's third cube wants
    # something that cuts, and Sword or Cutter serve equally, as a copy ability
    # or as an armor mode. Demanding one specific item there made the cube look
    # locked when you could plainly get it.
    if cat == "cube" and lv and st and slot is not None:
        alts = C.CUBE_EITHER_REQUIREMENT.get((lv, st, slot + 1))
        if alts:
            # Each gated group is satisfied separately. 1-2's third cube wants
            # something that cuts on foot AND something that cuts in the armor,
            # so with both gates on you need one from each list, not one
            # between them.
            abil = [f"Ability: {n}" for k, n in alts if k == "ability"]
            armr = [f"Armor Mode: {n}" for k, n in alts if k == "armor"]
            if ability_gating and abil:
                reqs.append(ANY_OF_PREFIX + "|".join(abil))
            if armor_gating and armr:
                reqs.append(ANY_OF_PREFIX + "|".join(armr))

    if ability_gating:
        if cat == "cube" and lv and st and slot is not None:
            need = C.ability_item_for_cube(lv, st, slot + 1)
            if need:
                reqs.append(need)
        if cat == "rare" and lv and st:
            need = C.ability_item_for_rare_sticker(lv, st)
            if need:
                reqs.append(need)

    return reqs


def satisfied(reqs, has, count):
    """Are all of these requirements met?

    has(name) answers whether an item is held; count(name) how many. Passing
    them in keeps this usable both from an Archipelago CollectionState and from
    the client's plain record of what has arrived.
    """
    for r in reqs:
        if r.startswith(ANY_OF_PREFIX):
            if not any(has(x) for x in r[len(ANY_OF_PREFIX):].split("|")):
                return False
        elif r == C.ANY_ABILITY:
            if not any(has(a) for a in C.ALL_ABILITY_ITEMS):
                return False
        elif r.startswith(AREA_PREFIX):
            if not can_reach_area(r[len(AREA_PREFIX):], count):
                return False
        elif r.startswith(BOSS_PREFIX):
            if not has_boss_gate(r[len(BOSS_PREFIX):], count):
                return False
        elif r.startswith(EX_PREFIX):
            if not has_ex_threshold(r[len(EX_PREFIX):], count):
                return False
        elif not has(r):
            return False
    return True


def can_reach_area(level, count):
    """Robobot opens Area N+1 by beating Area N's boss, and that boss needs a
    quota of Area N's own cubes. So reaching Area 4 means having satisfied the
    firewalls of Areas 1, 2 and 3 in turn."""
    try:
        want = int(level.replace("Level", ""))
    except ValueError:
        return True
    for a in range(1, want):
        lv = f"Level{a}"
        if count(C.area_cube_name(lv)) < C.AREA_CUBE_COUNTS_REQUIRED.get(lv, 0):
            return False
    return True


def has_boss_gate(level, count):
    need = C.AREA_CUBE_COUNTS_REQUIRED.get(level, 1)
    return count(C.area_cube_name(level)) >= need


def _ex_prereqs(level, opts):
    """What an EX stage really waits on.

    The game opens an EX stage once you have physically collected every Code
    Cube in the Area. Cubes arriving from the multiworld are not collected, so
    counting received cube items was the wrong measure entirely. What matters is
    whether you can actually go and get every one of that Area's cubes, which
    means holding whatever those cubes are gated behind.

    So an EX stage inherits the requirements of every cube in its Area that
    isn't inside the EX stage itself. Those cubes never depend on the EX, so
    this cannot loop.
    """
    from .Locations import LOCATION_TABLE, _GAME_DATA
    ex_no = _GAME_DATA["level_layout"][level]["ex"]
    out = []
    for nm, d in LOCATION_TABLE.items():
        if getattr(d, "category", None) != "cube":
            continue
        if getattr(d, "level", None) != level:
            continue
        if _stage_no(getattr(d, "stage", None)) == ex_no:
            continue
        for r in location_requirements(nm, d, opts):
            if r.startswith(EX_PREFIX):
                continue
            if r not in out:
                out.append(r)
    return out


def _ex_need(level):
    """An EX stage opens once every Code Cube in its Area has been collected,
    apart from the ones sitting inside the EX stage itself, which you obviously
    cannot have yet. This used to subtract the EX's own cubes from the total
    rather than simply leaving them out, which asked for several fewer than the
    game does and let logic believe an EX stage was open early."""
    from .Locations import _GAME_DATA
    ex = f"Stage{_GAME_DATA['level_layout'][level]['ex']}"
    return max(1, sum(1 for c in _GAME_DATA["code_cubes"]
                      if c["level"] == level and c["stage"] != ex))


def has_ex_threshold(level, count):
    return count(C.area_cube_name(level)) >= _ex_need(level)


def goal_met(opts, count, bosses_beatable=None):
    """Whether the seed's goal is satisfied.

    story_boss_count counts Areas whose boss you could actually beat, which
    means reaching the Area and opening its firewall. story_star_dream needs
    Access Ark reachable.
    """
    goal = opts.get("goal", 0)
    if goal == 1:
        want = int(opts.get("story_boss_count", 6) or 1)
        n = 0
        for lv in C.LEVELS:
            if can_reach_area(lv, count) and has_boss_gate(lv, count):
                n += 1
        return n >= want
    return can_reach_area("Level6", count)


def evaluate(location_table, items, opts, checked=()):
    """Sort every location into checked, in logic, or still out of reach.

    items maps item name to how many you hold. Returns three lists of location
    names, in table order so the display stays stable.
    """
    def has(n):
        return items.get(n, 0) > 0

    def count(n):
        return items.get(n, 0)

    done, open_now, blocked = [], [], []
    for name, d in location_table.items():
        if name in checked:
            done.append(name)
        elif satisfied(location_requirements(name, d, opts), has, count):
            open_now.append(name)
        else:
            blocked.append(name)
    return done, open_now, blocked


def missing_for(loc_name, d, items, opts):
    """What is still standing between you and this location, for display."""
    def has(n):
        return items.get(n, 0) > 0

    def count(n):
        return items.get(n, 0)

    out = []
    for r in location_requirements(loc_name, d, opts):
        if r.startswith(ANY_OF_PREFIX):
            opt = r[len(ANY_OF_PREFIX):].split("|")
            if not any(has(x) for x in opt):
                out.append("any of: " + ", ".join(opt))
        elif r == C.ANY_ABILITY:
            if not any(has(a) for a in C.ALL_ABILITY_ITEMS):
                out.append("any copy ability")
        elif r.startswith(AREA_PREFIX):
            lv = r[len(AREA_PREFIX):]
            if not can_reach_area(lv, count):
                out.append(f"reach {C.area_name(lv)}")
        elif r.startswith(BOSS_PREFIX):
            lv = r[len(BOSS_PREFIX):]
            if not has_boss_gate(lv, count):
                need = C.AREA_CUBE_COUNTS_REQUIRED.get(lv, 1)
                out.append("%d %s (have %d)"
                           % (need, C.area_cube_name(lv), count(C.area_cube_name(lv))))
        elif r.startswith(EX_PREFIX):
            lv = r[len(EX_PREFIX):]
            if not has_ex_threshold(lv, count):
                out.append("%d %s for the EX stage (have %d)"
                           % (_ex_need(lv), C.area_cube_name(lv),
                              count(C.area_cube_name(lv))))
        elif not has(r):
            out.append(r)
    return out
