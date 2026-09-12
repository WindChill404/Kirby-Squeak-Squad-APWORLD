"""
Patch.py Generates the Kirby: Planet Robobot patch artifact.

Because 3DS ROMs are large and can't be redistributed, the apworld produces a
small ".apkr" file describing the seed. At play time the client (or the setup
step) takes the player's own ROM, extracts romfs, runs the bundled `kpr_patch`
tool to neutralize collectibles + write the AP plan sidecar + inject the bridge
Mint module, then repacks a Luma LayeredFS folder.

Here at generation time we only need to emit the .apkr patch data (the plan).
"""
import json
import os
from typing import Dict

from worlds.Files import APProcedurePatch, APTokenMixin

from . import Constants as C
from .Items import ITEM_TABLE
from .Locations import LOCATION_TABLE

CURRENT_VERSION = "0.1.0"


class KirbyRobobotProcedurePatch(APProcedurePatch, APTokenMixin):
    game = C.GAME_NAME
    hash = None  # NA Robobot ROM hash can be pinned here once verified
    patch_file_ending = ".apkr"
    result_file_ending = ".3ds"  # produced LayeredFS folder / cci

    procedure = [
        ("apply_kpr_plan", ["plan.json"]),
    ]

    @classmethod
    def get_source_data(cls) -> bytes:
        return b""


def write_patch(world, output_directory: str) -> None:
    player = world.player
    multiworld = world.multiworld

    # Build the location -> placed item plan.
    placements = []
    patch_locations = []
    for loc in multiworld.get_locations(player):
        loc_data = LOCATION_TABLE.get(loc.name)
        if loc_data is None:
            continue
        item = loc.item
        item_id = (item.code if item and item.code is not None else 0)
        placements.append({
            "LocId": loc_data.code_offset,
            "ItemId": item_id,
            "Flags": 0,
        })
        # Only in-stage collectibles carry ROM coordinates to neutralize.
        if loc_data.file is not None:
            patch_locations.append({
                "File": loc_data.file,
                "Index": loc_data.index,
                "Wuid": loc_data.wuid,
                "ApLocId": loc_data.code_offset,
            })

    plan = {
        "version": CURRENT_VERSION,
        "player_name": multiworld.player_name[player],
        "seed": multiworld.seed_name,
        "goal": world.options.goal.value,
        "options": world.fill_slot_data(),
        "Locations": patch_locations,
        "Placements": placements,
    }

    patch = KirbyRobobotProcedurePatch(player=player,
                                       player_name=multiworld.player_name[player])
    patch.write_file("plan.json", json.dumps(plan).encode("utf-8"))

    out_name = multiworld.get_out_file_name_base(player) + patch.patch_file_ending
    patch.write(os.path.join(output_directory, out_name))
