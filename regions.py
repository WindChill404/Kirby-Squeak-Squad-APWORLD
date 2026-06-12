"""Regions for Kirby: Squeak Squad. Boss badges gate worlds; scrolls gate ability chests."""
from typing import TYPE_CHECKING
from BaseClasses import Region, ItemClassification
from worlds.generic.Rules import set_rule
from .locations import (location_name_to_id, LOCATION_REGION, LOCATION_POWERS,
                        ALL_LOCATIONS, KSSLocation, VICTORY_EVENT)
from .items import KSSItem
if TYPE_CHECKING:
    from . import KirbySqueakSquadWorld

GAME_REGIONS = ['CushyCloud', 'CushyCloudEX', 'GambleGalaxy', 'IceIsland', 'IceIslandEX', 'JamJungle', 'JamJungleEX', 'NatureNotch', 'NatureNotchEX', 'PrismPlains', 'PrismPlainsEX', 'SecretSea', 'SecretSeaEX', 'VocalVolcano', 'VocalVolcanoEX']
EDGES = [
    ('PrismPlains', 'NatureNotch', ['King DeDeDe badge']),
    ('PrismPlains', 'PrismPlainsEX', ['Prism Plains key']),
    ('NatureNotch', 'NatureNotchEX', ['Nature Notch key']),
    ('NatureNotch', 'CushyCloud', ['Mrs Moley badge']),
    ('CushyCloud', 'CushyCloudEX', ['Cushy Cloud key']),
    ('CushyCloud', 'JamJungle', ['Mecha-Kracko badge']),
    ('JamJungle', 'JamJungleEX', ['Jam Jungle key']),
    ('JamJungle', 'VocalVolcano', ['Yadgaine badge']),
    ('VocalVolcano', 'VocalVolcanoEX', ['Vocal Volcano key']),
    ('VocalVolcano', 'IceIsland', ['Bohboh badge']),
    ('IceIsland', 'IceIslandEX', ['Ice Island key']),
    ('IceIsland', 'SecretSea', ['Star seal 1', 'Star seal 2', 'Star seal 3', 'Star seal 4', 'Star seal 5', 'Daroach badge']),
    ('SecretSea', 'SecretSeaEX', ['Star seal 1', 'Star seal 2', 'Star seal 3', 'Star seal 4', 'Star seal 5', 'Daroach badge', 'Secret Sea key']),
    ('SecretSea', 'GambleGalaxy', ['Star seal 1', 'Star seal 2', 'Star seal 3', 'Star seal 4', 'Star seal 5', 'Daroach badge', 'Meta Knight badge'])
]
ENTRY_REGION = "PrismPlains"

def _scrolls_for(powers):
    return [p + " scroll" for p in powers]

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
            scrolls = _scrolls_for(powers)
            set_rule(L, lambda state, s=tuple(scrolls): state.has_all(s, p))
    gg = regions["GambleGalaxy"]
    vic = KSSLocation(p, VICTORY_EVENT, None, gg)
    vic.place_locked_item(KSSItem("Victory", ItemClassification.progression, None, p))
    gg.locations.append(vic)
    menu.connect(regions[ENTRY_REGION])
    for frm, to, req in EDGES:
        regions[frm].connect(regions[to],
            rule=(lambda state, r=tuple(req): state.has_all(r, p)) if req else None)
