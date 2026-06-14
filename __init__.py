"""Kirby: Squeak Squad - Archipelago world (CalDrac-data build)."""
from typing import ClassVar
from worlds.AutoWorld import World, WebWorld
from worlds.LauncherComponents import Component, components, Type, launch_subprocess, icon_paths


icon_paths["kss_icon"] = f"ap:{__name__}/icon.png"


def _launch_client(*args):
    from worlds.kirby_squeak_squad.client import launch
    launch_subprocess(launch, name="KirbySqueakSquadClient", args=args)


components.append(Component(
    "Kirby Squeak Squad Client",
    func=_launch_client,
    component_type=Type.CLIENT,
    icon="kss_icon",
))
from .items import ITEM_TABLE, item_name_to_id, KSSItem, ITEM_BASE_ID
from .locations import location_name_to_id
from .regions import create_regions
from .rules import set_rules
from .options import KirbySqueakSquadOptions
from . import patcher as _patcher
import os

class KSSWeb(WebWorld):
    theme = "ice"

class KirbySqueakSquadWorld(World):
    """Kirby: Squeak Squad treasure-shuffle randomizer."""
    game = "Kirby Squeak Squad"
    web = KSSWeb()
    options_dataclass = KirbySqueakSquadOptions
    options: KirbySqueakSquadOptions
    item_name_to_id: ClassVar = item_name_to_id
    location_name_to_id: ClassVar = location_name_to_id

    def generate_early(self) -> None:
        # pick the random starting color once (per seed) so fill_slot_data is stable.
        self.start_color = None
        if self.options.random_starting_color:
            self.start_color = self.random.randint(0, 18)  # 19 render colors

    def create_item(self, name: str) -> KSSItem:
        cls, _ = ITEM_TABLE[name]
        return KSSItem(name, cls, item_name_to_id[name], self.player)

    def create_items(self) -> None:
        from .items import FILLER_NAMES
        pool = []
        for name, (_cls, qty) in ITEM_TABLE.items():
            for _ in range(qty):
                pool.append(self.create_item(name))
        if self.options.ability_checks:
            # 23 ability-acquired locations were added; balance with 23 more filler
            for i in range(23):
                pool.append(self.create_item(FILLER_NAMES[i % len(FILLER_NAMES)]))
        self.multiworld.itempool += pool

    def create_regions(self) -> None:
        create_regions(self)

    def set_rules(self) -> None:
        set_rules(self)

    def fill_slot_data(self) -> dict:
        data = {
            "goal": self.options.goal.value,
            "chest_goal_count": int(self.options.chest_goal_count.value),
            "death_link": int(self.options.death_link.value),
        }
        if getattr(self, "start_color", None) is not None:
            data["start_color"] = int(self.start_color)
        return data

    def generate_output(self, output_directory: str) -> None:
        """Emit the .apkss patch into the room download for this player."""
        placements = _patcher.build_placements(self)
        data = _patcher.create_patch(
            placements,
            slot_name=self.multiworld.get_player_name(self.player),
            seed=str(self.multiworld.seed))
        fname = f"AP_{self.multiworld.seed_name}_P{self.player}_{self.multiworld.get_player_name(self.player)}.apkss"
        with open(os.path.join(output_directory, fname), "wb") as f:
            f.write(data)
