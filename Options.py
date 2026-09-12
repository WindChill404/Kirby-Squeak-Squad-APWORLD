"""
Options.py Player options for Kirby: Planet Robobot.
"""
from dataclasses import dataclass

from Options import (Choice, DefaultOnToggle, PerGameCommonOptions,
                     Range, StartInventoryPool, Toggle)


class Goal(Choice):
    """The victory condition for your game.

    story_star_dream: Defeat Star Dream at the end of Story Mode.
    story_boss_count: Defeat a set number of Story Mode bosses (see story_boss_count).
    """
    display_name = "Goal"
    option_story_star_dream = 0
    option_story_boss_count = 1
    default = 0


class StoryBossCount(Range):
    """If Goal is story_boss_count, how many Story Mode bosses must be defeated."""
    display_name = "Story Boss Count"
    range_start = 1
    range_end = 6
    default = 6







class StickerChecks(Toggle):
    """Stickersanity: add every normal Sticker as its own location (one per
    sticker in the album).

    WARNING: this adds a large number of locations and, because normal stickers
    are collected passively as you play, they end up available across most of
    the game at once. That can make for difficult or strange logic, since the
    generator has many always-open locations to work with and the usual sense of
    progression through the stickers does not apply. Turn this on only if you
    want that. Rare Stickers are a separate, smaller set (see
    rare_sticker_checks) and are on by default.
    """
    display_name = "Stickersanity"


class RareStickerChecks(DefaultOnToggle):
    """Include the 35 in-stage Rare Sticker pickups as locations."""
    display_name = "Rare Sticker Location Checks"




class OpenAllStages(DefaultOnToggle):
    """Open every normal stage in an Area as soon as you can reach the Area, so
    you can play them in any order. Boss doors still need their Code Cubes, and
    EX stages keep their own unlock rules."""
    display_name = "Open all stages"


class AbilityGating(Toggle):
    """Only let Kirby keep copy abilities you've received."""
    display_name = "Ability Gating"


class ArmorGating(Toggle):
    """Also gate copy abilities while in the Robobot Armor."""
    display_name = "Armor Mode Gating"


class DeathLink(Toggle):
    """When you die, everyone dies. When anyone dies, you die."""
    display_name = "Death Link"


class KirbyColor(Choice):
    """Recolor Kirby's body. Cosmetic only chosen once at generation and baked
    into the patched ROM. 'pink' leaves the game stock. Textures are from the
    community KPR retexture pack (native Robobot format)."""
    display_name = "Kirby Color"
    option_pink = 0            # vanilla, no texture shipped
    option_red = 1
    option_yellow = 2
    option_green = 3
    option_chalk = 4
    option_shadow = 5
    option_snow = 6
    option_carbon = 7
    option_ocean = 8
    option_sapphire = 9
    option_grape = 10
    option_emerald = 11
    option_orange = 12
    option_chocolate = 13
    option_cherry = 14
    option_citrus = 15
    option_white = 16
    option_lavender = 17
    option_ivory = 18
    option_white_and_black = 19
    option_dedede = 20
    option_waddle_dee = 21
    option_meta_knight = 22
    option_carbon_pink = 23
    option_carbon_blue = 24
    option_apple = 25
    option_raspberry = 26
    option_elfilin = 27
    option_galacta = 28
    option_inverted = 29
    option_black_and_white = 30
    option_mirror = 31
    option_suplex = 32
    option_daredevil = 33
    default = 0


@dataclass
class KirbyRobobotOptions(PerGameCommonOptions):
    goal: Goal
    story_boss_count: StoryBossCount
    sticker_checks: StickerChecks
    rare_sticker_checks: RareStickerChecks
    open_all_stages: OpenAllStages
    ability_gating: AbilityGating
    armor_gating: ArmorGating
    death_link: DeathLink
    kirby_color: KirbyColor
    start_inventory_from_pool: StartInventoryPool
