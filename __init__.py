"""
Kirby: Planet Robobot Archipelago World.

A romfs-level integration for the 3DS game. Locations are the in-stage
collectibles (Code Cubes, Stickers, Rare Stickers) plus stage/boss clears and
optional sub-game clears; items are level access, abilities, armor, EX keys,
cubes, and stickers. The generated patch rewrites the ROM's Mint level data so
each collectible reports to Archipelago instead of granting its vanilla effect,
and injects an AP bridge module that talks to the client.
"""
from typing import Any, ClassVar, Dict, List

from BaseClasses import ItemClassification, Region, Tutorial
from worlds.AutoWorld import WebWorld, World
from worlds.LauncherComponents import (Component, Type, components,
                                       launch_subprocess, SuffixIdentifier)

from . import Constants as C
from .Items import (ITEM_NAME_TO_ID, ITEM_TABLE, KirbyRobobotItem)
from .Locations import (LOCATION_NAME_TO_ID, LOCATION_TABLE, OPTIONAL_CATEGORIES)
from .Options import KirbyRobobotOptions
from .Regions import create_regions, connect_regions
from .Rules import set_rules
from .Rom import KirbyRobobotSettings


def _launch_client(*args):
    """Launcher entry point.

    LauncherComponents.launch_subprocess passes extra CLI args (the patch file
    path, when a .apkr is opened/dragged) through its own `args` parameter it
    must be forwarded explicitly, otherwise the path is silently dropped and the
    client never sees the patch."""
    from .KirbyRobobotClient import launch
    launch_subprocess(launch, name="KirbyRobobotClient", args=args)


# Give the launcher entry its own icon rather than the generic one. Older
# Archipelago releases don't expose icon_paths, so fall back to the default
# instead of refusing to load.
_ICON = None
try:
    from worlds.LauncherComponents import icon_paths
    icon_paths["kirby_robobot"] = f"ap:{__name__}/data/kpr_client_icon.png"
    _ICON = "kirby_robobot"
except Exception:
    pass

if _ICON:
    components.append(Component(
        "Kirby Planet Robobot Client", func=_launch_client, component_type=Type.CLIENT,
        file_identifier=SuffixIdentifier(".apkr"), icon=_ICON))
else:
    components.append(Component(
        "Kirby Planet Robobot Client", func=_launch_client, component_type=Type.CLIENT,
        file_identifier=SuffixIdentifier(".apkr")))


class KirbyRobobotWeb(WebWorld):
    theme = "ice"
    tutorials = [Tutorial(
        "Multiworld Setup Guide",
        "A guide to setting up Kirby: Planet Robobot for Archipelago.",
        "English", "setup_en.md", "setup/en",
        ["you"])]


class KirbyRobobotWorld(World):
    """Kirby: Planet Robobot on the Nintendo 3DS.

    Kirby storms the Access Ark to stop the Haltmann Works Company. Collect Code
    Cubes, wield 27 copy abilities and the Robobot Armor, and unlock every mode.
    """
    game = C.GAME_NAME
    web = KirbyRobobotWeb()
    options_dataclass = KirbyRobobotOptions
    options: KirbyRobobotOptions

    # ROM path / ctrtool / mod_path settings, saved in host.yaml.
    settings_key = "kirby_robobot_options"
    settings: "ClassVar[KirbyRobobotSettings]"

    item_name_to_id = ITEM_NAME_TO_ID
    location_name_to_id = LOCATION_NAME_TO_ID

    required_client_version = (0, 4, 5)

    def create_item(self, name: str) -> KirbyRobobotItem:
        data = ITEM_TABLE[name]
        return KirbyRobobotItem(name, data.classification, data.code_offset, self.player)

    def create_regions(self) -> None:
        regions = create_regions(self)
        connect_regions(self, regions)

    def create_items(self) -> None:
        from .Items import (ITEM_TABLE as _IT)
        from BaseClasses import ItemClassification as _IC
        pool: List[KirbyRobobotItem] = []

        # Only real locations take items event locations (e.g. "Collect All
        # 100 Code Cubes") are filled with their own event item, so counting them
        # here would overfill the pool.
        total_locations = len([
            loc for loc in self.multiworld.get_locations(self.player)
            if loc.address is not None
        ])

        # Build the non-cube, non-filler core first so we know how much room the
        # Code Cubes have to work with.
        # Stickers are filler by design, but they are still specific
        # collectibles that have to exist once each. Only the generic
        # consumables are held back, since those are what pads the pool out to
        # the location count. Skipping every filler item is what stopped a
        # single sticker from ever being sent.
        def _is_pool_collectible(nm):
            return nm.startswith("Rare Sticker:") or nm.startswith("Sticker:")

        core_count = 0
        for name, data in ITEM_TABLE.items():
            if (data.classification == ItemClassification.filler
                    and not _is_pool_collectible(name)):
                continue
            if not self._item_enabled(name):
                continue
            for _ in range(data.count):
                pool.append(self.create_item(name))
                core_count += 1

        # Code Cubes: always create 100 so every "collect all cubes" and EX-unlock
        # interaction is representable, but classify them so the fill has room.
        # When EX stages need cubes (ex_stage_handling location/both) the first
        # N cubes per level are progression; the rest are useful. When EX stages
        # use keys only, cubes are useful collectibles (still real items).

        # If the pool already exceeds locations (tight configs), demote surplus
        # progression-skip cubes to useful so fill isn't over-constrained. Real
        # AP fill handles useful items as non-blocking.
        # Pad or trim to match location count using filler consumables.
        if len(pool) < total_locations:
            while len(pool) < total_locations:
                pool.append(self.create_item(self.get_filler_item_name()))
        elif len(pool) > total_locations:
            pool = _trim_pool(pool, total_locations)

        self.multiworld.itempool += pool

    def set_rules(self) -> None:
        set_rules(self)

    def fill_slot_data(self) -> Dict[str, Any]:
        return {
            "goal": self.options.goal.value,
            "story_boss_count": self.options.story_boss_count.value,
            "death_link": bool(self.options.death_link.value),
            "open_all_stages": bool(self.options.open_all_stages.value),
            "ability_gating": bool(self.options.ability_gating.value),
            "armor_gating": bool(self.options.armor_gating.value),
            "rare_sticker_checks": bool(self.options.rare_sticker_checks.value),
            "sticker_checks": bool(self.options.sticker_checks.value),
            "kirby_color": self.options.kirby_color.current_key,
        }

    def generate_output(self, output_directory: str) -> None:
        # Build the patch: mapping of location-id -> placed item, plus options.
        from .Patch import write_patch
        write_patch(self, output_directory)

    # --- helpers -------------------------------------------------------------
    def _item_enabled(self, name: str) -> bool:
        opts = self.options
        # An item only belongs in the pool if its matching checks are enabled.
        # Otherwise you could be *sent* a Rare Sticker that has no location to be
        # found at, which is exactly the "received it but can't check it" problem.
        if name.startswith("Rare Sticker:"):
            return bool(opts.rare_sticker_checks.value)
        if name.startswith("Sticker:"):
            return bool(opts.sticker_checks.value)
        return True

    def get_filler_item_name(self) -> str:
        # Real in-game pickups. Ordinary foods (1/5 heal) are by far the most
        # common thing you find in Robobot, then 1-Ups, then the stronger heals:
        # Energy Drink (1/2) and Maxim Tomato (full).
        from .Items import FOOD_ITEMS, ONE_UP, ENERGY_DRINK, MAXIM_TOMATO
        pool = FOOD_ITEMS + [ONE_UP, ENERGY_DRINK, MAXIM_TOMATO]
        weights = ([6] * len(FOOD_ITEMS)) + [20, 8, 4]
        return self.random.choices(pool, weights=weights, k=1)[0]


def _trim_pool(pool, target):
    """Trim the pool to `target`, dropping filler first, then useful items
    (e.g. surplus Code Cubes / rare stickers), never progression."""
    prog = [i for i in pool if i.advancement]
    useful = [i for i in pool
              if not i.advancement
              and i.classification == ItemClassification.useful]
    filler = [i for i in pool
              if not i.advancement
              and i.classification == ItemClassification.filler]

    result = list(prog)
    # Add back useful up to remaining room.
    room = max(0, target - len(result))
    result += useful[:room]
    room = max(0, target - len(result))
    result += filler[:room]
    return result
