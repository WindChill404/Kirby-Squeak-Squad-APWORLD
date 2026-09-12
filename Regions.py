"""Regions for Kirby: Squeak Squad. Boss badges gate worlds; scrolls gate ability chests."""
from typing import TYPE_CHECKING
from BaseClasses import Region, ItemClassification
from worlds.generic.Rules import set_rule
from .locations import (location_name_to_id, LOCATION_REGION, LOCATION_POWERS,
                        ALL_LOCATIONS, KSSLocation, VICTORY_EVENT, ACQUIRED_ABILITY,
                        ACQUIRED_LOCATIONS)
from .items import KSSItem
if TYPE_CHECKING:
    from . import KirbySqueakSquadWorld

GAME_REGIONS = ['CushyCloud', 'CushyCloudEX', 'GambleGalaxy', 'IceIsland', 'IceIslandEX', 'JamJungle', 'JamJungleEX', 'NatureNotch', 'NatureNotchEX', 'PrismPlains', 'PrismPlainsEX', 'SecretSea', 'SecretSeaEX', 'VocalVolcano', 'VocalVolcanoEX']
EDGES = [
    ('PrismPlains', 'NatureNotch', ['King DeDeDe Badge']),
    ('PrismPlains', 'PrismPlainsEX', ['Prism Plains Key']),
    ('NatureNotch', 'NatureNotchEX', ['Nature Notch Key']),
    ('NatureNotch', 'CushyCloud', ['Mrs Moley Badge']),
    ('CushyCloud', 'CushyCloudEX', ['Cushy Cloud Key']),
    ('CushyCloud', 'JamJungle', ['Mecha-Kracko Badge']),
    ('JamJungle', 'JamJungleEX', ['Jam Jungle Key']),
    ('JamJungle', 'VocalVolcano', ['Yadgaine Badge']),
    ('VocalVolcano', 'VocalVolcanoEX', ['Vocal Volcano Key']),
    ('VocalVolcano', 'IceIsland', ['Bohboh Badge']),
    ('IceIsland', 'IceIslandEX', ['Ice Island Key']),
    ('IceIsland', 'SecretSea', ['Star Seal 1', 'Star Seal 2', 'Star Seal 3', 'Star Seal 4', 'Star Seal 5', 'Daroach Badge']),
    ('SecretSea', 'SecretSeaEX', ['Star Seal 1', 'Star Seal 2', 'Star Seal 3', 'Star Seal 4', 'Star Seal 5', 'Daroach Badge', 'Secret Sea Key']),
    ('SecretSea', 'GambleGalaxy', ['Star Seal 1', 'Star Seal 2', 'Star Seal 3', 'Star Seal 4', 'Star Seal 5', 'Daroach Badge', 'Meta Knight Badge'])
]
ENTRY_REGION = "PrismPlains"

def _abilities_for(powers):
    return ["Progressive " + p for p in powers]

def create_regions(world: "KirbySqueakSquadWorld") -> None:
    p, mw = world.player, world.multiworld
    regions = {}
    menu = Region("Menu", p, mw); mw.regions.append(menu)
    for name in GAME_REGIONS:
        rg = Region(name, p, mw); regions[name] = rg; mw.regions.append(rg)
    for loc in ALL_LOCATIONS:
        rg = regions[LOCATION_REGION[loc]]
        L = KSSLocation(p, loc, location_name_to_id[loc], rg)
        rg.locations.append(L)
        powers = LOCATION_POWERS.get(loc, [])
        if powers:
            # A chest's power list is OR: ANY one of the listed abilities opens it
            # (e.g. any ranged ability trips a far switch). Use has_any, not has_all --
            # has_all would over-gate and, on the 8-11 ability lists, be unsatisfiable
            # in-game (Kirby holds at most 6 abilities at once).
            progs = _abilities_for(powers)
            set_rule(L, lambda state, s=tuple(progs): state.has_any(s, p))
    if getattr(world.options, "ability_checks", 0):
        for loc in ACQUIRED_LOCATIONS:
            rg = regions[LOCATION_REGION[loc]]
            L = KSSLocation(p, loc, location_name_to_id[loc], rg)
            rg.locations.append(L)
            prog = "Progressive " + ACQUIRED_ABILITY[loc]
            set_rule(L, lambda state, a=prog: state.has(a, p))
    gg = regions["GambleGalaxy"]
    vic = KSSLocation(p, VICTORY_EVENT, None, gg)
    vic.place_locked_item(KSSItem("Victory", ItemClassification.progression, None, p))
    gg.locations.append(vic)
    menu.connect(regions[ENTRY_REGION])
    for frm, to, req in EDGES:
        regions[frm].connect(regions[to],
            rule=(lambda state, r=tuple(req): state.has_all(r, p)) if req else None)
