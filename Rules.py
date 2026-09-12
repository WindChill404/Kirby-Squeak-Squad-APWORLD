"""Completion rule for Kirby: Squeak Squad."""
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from . import KirbySqueakSquadWorld


def set_rules(world: "KirbySqueakSquadWorld") -> None:
    p, mw = world.player, world.multiworld
    if world.options.goal.value == 1:
        # chests_and_daroach: reaching Ice Island (Daroach) is the logic proxy;
        # the exact "N chests + Daroach beaten" is enforced live by the client.
        mw.completion_condition[p] = lambda state: state.can_reach("IceIsland", "Region", p)
    else:
        # beat_game: claim the Strawberry Shortcake in Gamble Galaxy.
        mw.completion_condition[p] = lambda state: state.has("Victory", p)
