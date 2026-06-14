"""
Kirby: Squeak Squad — Archipelago ROM patcher (CalDrac-data build)

Writes each AP-placed item's byte into the chest's ROM address. Item bytes and
addresses come from CalDrac's randomizer data (kss_chest_data.py), where:
    itemId == collectibles bit index == AP location offset.

Roles:
  GENERATION (imported by the .apworld generate_output):
      build_placements(world) -> [placement dicts]
      create_patch(placements, slot_name, seed) -> bytes (.apkss)
  PLAYER (run locally):
      apply_patch(rom_path, patch_path, output_path)

A placement only patches the ROM when the placed item is THIS game's collectible
(it has a game byte). Foreign/other-player items are left for the client to
deliver in-game; their chest keeps vanilla contents.
"""

import io, json, zipfile
from typing import Dict, List, Optional

try:
    from .kss_chest_data import GAME_ITEM_BYTES, LOCATION_ADDR
except ImportError:
    from kss_chest_data import GAME_ITEM_BYTES, LOCATION_ADDR

GAME_NAME = "Kirby Squeak Squad"
PATCH_VERSION = 3
LOCATION_BASE_ID = 5_000_100   # AP location id = base + bit_index(offset)


def _offset_from_location_id(loc_id: int) -> int:
    return loc_id - LOCATION_BASE_ID


def build_placements(world) -> List[dict]:
    """Generation side: one entry per real (addressed) location."""
    out = []
    for loc in world.multiworld.get_locations(world.player):
        if loc.address is None:        # events (Victory) have no address
            continue
        offset = _offset_from_location_id(loc.address)
        item = loc.item
        same_game = bool(item and item.player == world.player)
        out.append({
            "location_offset": offset,
            "ap_location_id":  loc.address,
            "ap_item_name":    item.name if item else None,
            "ap_item_player":  item.player if item else None,
            # byte to write only when it's our own collectible:
            "game_item_id":    GAME_ITEM_BYTES.get(item.name) if same_game else None,
        })
    return out


def create_patch(placements: List[dict], slot_name: str, seed: str) -> bytes:
    meta = {"game": GAME_NAME, "version": PATCH_VERSION,
            "slot_name": slot_name, "seed": seed}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("meta.json",  json.dumps(meta, indent=2))
        z.writestr("items.json", json.dumps(placements, indent=2))
    return buf.getvalue()


def apply_patch(rom_path: str, patch_path: str, output_path: str) -> None:
    with open(rom_path, "rb") as f:
        rom = bytearray(f.read())
    with zipfile.ZipFile(patch_path) as z:
        meta  = json.loads(z.read("meta.json"))
        items = json.loads(z.read("items.json"))
    if meta.get("game") != GAME_NAME:
        raise ValueError(f"Patch is for {meta.get('game')!r}, not {GAME_NAME!r}")

    patched = 0
    for e in items:
        gid = e.get("game_item_id")
        off = e.get("location_offset")
        if gid is None or off is None:
            continue                       # foreign item -> leave vanilla
        addr = LOCATION_ADDR.get(off)
        if addr is None:
            continue
        rom[addr] = gid & 0xFF             # single-byte write (CalDrac method)
        patched += 1
    with open(output_path, "wb") as f:
        f.write(rom)
    print(f"Patched {patched} chest(s). ROM written to {output_path}")


if __name__ == "__main__":
    import argparse
    a = argparse.ArgumentParser(description="Apply a Kirby Squeak Squad .apkss patch.")
    a.add_argument("rom"); a.add_argument("patch"); a.add_argument("out")
    n = a.parse_args()
    apply_patch(n.rom, n.patch, n.out)
