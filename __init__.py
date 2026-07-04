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

class KSSWeb(WebWorld):
    theme = "ice"

# The 18 unlockable spray paints, in StartingSpray option order (option value 2..19).
# Pink (the default) is not a collectible and is intentionally absent.
SPRAY_NAMES = ["Yellow", "Red", "Green", "Snow", "Carbon", "Ocean", "Sapphire", "Grape",
               "Emerald", "Orange", "Chocolate", "Cherry", "Chalk", "Shadow", "Ivory",
               "Citrus", "White", "Lavender"]

class KirbySqueakSquadWorld(World):
    """Kirby: Squeak Squad treasure-shuffle randomizer."""
    game = "Kirby Squeak Squad"
    web = KSSWeb()
    options_dataclass = KirbySqueakSquadOptions
    options: KirbySqueakSquadOptions
    item_name_to_id: ClassVar = item_name_to_id
    location_name_to_id: ClassVar = location_name_to_id

    def generate_early(self) -> None:
        # resolve the starting spray once (per seed) so the item pool and grant are stable.
        # None = Pink only; otherwise the chosen (or a random) spray is granted at start.
        self.start_spray = None
        spray = self.options.starting_spray.value
        if spray == 1:                       # random
            self.start_spray = self.random.choice(SPRAY_NAMES)
        elif spray >= 2:                     # a specific color
            self.start_spray = SPRAY_NAMES[spray - 2]

    def create_item(self, name: str) -> KSSItem:
        cls, _ = ITEM_TABLE[name]
        return KSSItem(name, cls, item_name_to_id[name], self.player)

    def create_items(self) -> None:
        from .items import FILLER_NAMES
        pool = []
        for name, (_cls, qty) in ITEM_TABLE.items():
            n = qty
            if self.start_spray and name == self.start_spray:
                n -= 1   # one copy is granted as starting inventory instead of placed
            for _ in range(n):
                pool.append(self.create_item(name))
        if self.start_spray:
            # grant the spray directly (starting inventory) -> owned, no location check consumed
            self.multiworld.push_precollected(self.create_item(self.start_spray))
        # Pad with filler so the item count exactly matches the real (non-event) location count.
        # This auto-balances every adjustment (stage-clear locations, ability checks, starting
        # spray) instead of hand-counting, so an added location can't desync the pool again.
        real_locs = sum(1 for loc in self.multiworld.get_locations(self.player)
                        if loc.address is not None)
        for i in range(real_locs - len(pool)):
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
        return data
