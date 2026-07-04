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


class AbilityChecks(Toggle):
    """Add a check for the first time you use each copy ability you've received.

    Adds 23 ability-acquired locations (one per ability) and 23 more filler items
    to match. Off = no ability-use checks.
    """
    display_name = "Ability Acquired Checks"


class StartingSpray(Choice):
    """Which spray paint Kirby owns from the start. Granted directly -- no location check is
    consumed for it.

    Pink is Kirby's default and is always available. Choose a color to also OWN that spray from
    the start (it shows in your collection and you can apply / re-apply it freely from the spray
    menu), or pick 'random' to be granted a random spray each seed. 'none' = Pink only.

    Unlike the old Random Starting Color, this grants the real spray instead of a cosmetic tint,
    so it sticks and doesn't fight the spray menu.
    """
    display_name = "Starting Spray"
    option_none = 0
    option_random = 1
    option_yellow = 2
    option_red = 3
    option_green = 4
    option_snow = 5
    option_carbon = 6
    option_ocean = 7
    option_sapphire = 8
    option_grape = 9
    option_emerald = 10
    option_orange = 11
    option_chocolate = 12
    option_cherry = 13
    option_chalk = 14
    option_shadow = 15
    option_ivory = 16
    option_citrus = 17
    option_white = 18
    option_lavender = 19
    default = 0


@dataclass
class KirbySqueakSquadOptions(PerGameCommonOptions):
    death_link: DeathLink
    goal: Goal
    chest_goal_count: ChestGoalCount
    ability_checks: AbilityChecks
    starting_spray: StartingSpray
