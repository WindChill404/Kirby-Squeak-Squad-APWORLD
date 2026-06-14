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


class RandomStartingColor(Toggle):
    """Tint Kirby a random color each seed (cosmetic only).

    Picks one of Kirby's render colors per seed and holds it while you're in a stage.
    This is purely visual and safe (it only writes the live render byte, never your
    save). Two quirks: the game repaints Kirby from his saved color on some menus
    (most noticeably the collection screen), so the tint briefly reverts there and
    snaps back on the next gameplay frame; and spray paints can't change your color
    while this is on.
    """
    display_name = "Random Starting Color"


@dataclass
class KirbySqueakSquadOptions(PerGameCommonOptions):
    death_link: DeathLink
    goal: Goal
    chest_goal_count: ChestGoalCount
    ability_checks: AbilityChecks
    random_starting_color: RandomStartingColor
