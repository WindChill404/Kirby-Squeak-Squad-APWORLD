from dataclasses import dataclass
from Options import Toggle, Choice, Range, PerGameCommonOptions


class DeathLink(Toggle):
    """When you die, everyone dies; when anyone dies, you die."""
    display_name = "Death Link"


class Goal(Choice):
    """Win condition.

    beat_game: reach Gamble Galaxy and claim the Strawberry Shortcake (beat the game).
    chests_and_daroach: collect a set number of chests (chest_goal_count) AND beat
        Daroach, the Ice Island boss (the stage-6 boss).
    """
    display_name = "Goal"
    option_beat_game = 0
    option_chests_and_daroach = 1
    default = 0


class ChestGoalCount(Range):
    """For the chests_and_daroach goal: how many chests you must collect."""
    display_name = "Chest Goal Count"
    range_start = 1
    range_end = 119
    default = 70


@dataclass
class KirbySqueakSquadOptions(PerGameCommonOptions):
    death_link: DeathLink
    goal: Goal
    chest_goal_count: ChestGoalCount
