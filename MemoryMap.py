"""
MemoryMap.py RAM addresses for Kirby: Planet Robobot (title 0004000000183600).

The client reads/writes these via the UDP memory pipe. Values marked CONFIRMED
come from static analysis of code.bin; values marked NEEDS_RUNTIME must be pinned
once on Azahar (see tools/find_addresses.py, which automates the search). This
mirrors how the ALBW client stores a handful of fixed addresses (SAVES_LOCATION
= 0x711de8 etc.) discovered empirically.

code.bin loads at 0x00100000 and spans to 0x0070b000. The save/progress globals
live in the .data/.bss tail (~0x006eb000-0x0070b000, plus bss just past the file),
the same relative position where ALBW's save globals sit.
"""

# The Title ID of the running game. Kirby: Planet Robobot is 0004000000183600.
# (An earlier value here was wrong; the memory-pipe plugin still connected because
# it falls back to the running process when the id doesn't match, which hid the
# mistake but the LayeredFS folder was named after the wrong game, so every ROM
# patch we made was silently ignored.)
TITLE_ID_NA = 0x0004000000183600
TITLE_ID_GLO = 0x0004000000183600  # European; cheat-code source (layout matches NA)
CODE_LOAD_BASE = 0x00100000
CODE_END = 0x0070B000  # end of code.bin image; .bss follows

# --- Save data location (from Action Replay cheat codes, GLO version) ----------
# AR "D3" codes use ABSOLUTE FCRAM addresses, which means the in-RAM save copy
# sits at a FIXED address on a given title/version likely no pointer chase
# needed. These are the GLO (European) addresses; the NA layout is the same but
# the absolute base may differ, so find_addresses.py verifies/relocates on NA.
#
#   GLO save slots (3 files), each 0x1174 bytes:
#     File01 @ 0x302EED58   File02 @ 0x302EFECC   File03 @ 0x302F1040
#   Within a slot:
#     +0x000  Team Kirby Clash "Quest" levels (4 words = the 4 classes)
#     +0x082  Sticker array: 200 entries x 2 bytes; nonzero (0x0101) = owned
SAVE_SLOT_SIZE = 0x1174
SAVE_SLOTS_GLO = [0x302EED58, 0x302EFECC, 0x302F1040]

# NA equivalents CONFIRMED by find_addresses.py on Azahar (round 1):
# the NA save is at the SAME address as GLO (0x302EED58), sticker signature 1.00.
SAVE_SLOTS = [0x302EED58, 0x302EFECC, 0x302F1040]
ACTIVE_SLOT = 0                   # which file the player is using (client picks)

class SlotOffsets:
    # Confirmed from cheat codes:
    STICKER_ARRAY = 0x82          # 200 x u16, nonzero = sticker owned
    STICKER_COUNT = 200
    QUEST_CLASSES = 0x00          # 4 words (Team Kirby Clash classes)
    # CUBES decoded from IsIcCubeGet (0x0016e97c / 0x0016e9a0, via firubii) and
    # VERIFIED live on Azahar (slot 0 read 15 cubes: 9 in level 1 + 6 in level 2,
    # exactly matching the player's save).
    #
    #   IsIcCubeGet(stage, idx):
    #       base = getCubeStruct()                     # fn 0x0040a700
    #       return *(s8*)(base + stage*8 + idx + 8)    # nonzero = collected
    #
    #   getCubeStruct():   # 0x0040a700 -> 0x00105ed8 -> 0x004be794
    #       G    = [0x0070a7f0]
    #       A    = [G + 4]
    #       C    = [A + 0x2A628 + 4]
    #       base = C + slot*0x1174 + 0x2738
    #
    # Layout (verified): 8 bytes per stage; bytes 0..2 are the 3 Code Cubes
    # (nonzero = collected); bytes 5..7 are other per-stage flags (NOT cubes).
    # Stage index = (level-1) * STAGES_PER_LEVEL + stage_in_level.
    # Cubes never appeared in our save dumps because they live at slot + 0x2738,
    # beyond the 0x1174 bytes we were reading.
    CUBE_GLOBAL = 0x0070A7F0
    CUBE_CHAIN_OFF = 0x2A628       # A + this, then [+4] -> C
    CUBE_BASE_OFF = 0x2738         # base = C + slot*SLOT_SIZE + this
    CUBE_STAGE_STRIDE = 8          # bytes per stage
    CUBE_FIRST_OFF = 8             # base + stage*8 + idx + 8
    CUBES_PER_STAGE = 3            # bytes 0..2 of each stage row
    STAGES_PER_LEVEL = 6           # verified: level1 = stages 0-5, level2 = 6-11

    IC_CUBE_BITS = None            # not a bitfield (see above)
    IC_CUBE_COUNT = None
    STAGE_CLEARED_BITS = None      # 0x4EC is a counter, not a bitfield
    # Per-stage clear flags structure CONFIRMED from code.bin (native
    # IsStageCleared @ 0x27B72C): cleared = *(STAGE_ARRAY + real_index*8 + 7),
    # i.e. 8-byte rows, byte 5=opened, 6=unlocked, 7=cleared. The real_index is
    # sequential per stage (Area1=0..5, Area2=6..11, Area3=12..18, Area4=19..25,
    # Area5=26..32, Area6=33..41), decoded via the game's index tables. The only
    # runtime unknown is STAGE_ARRAY (the array's offset inside the save slot),
    # solved live by tools/kpr_solve_stages.py.
    STAGE_ARRAY_BASE = None        # (unused; the array is at a fixed address,
                                   #  see STAGE_ARRAY_ADDR below)
    STAGE_ROW_STRIDE = 8
    STAGE_CLEARED_BYTE = 7
    STAGE_INDEX = {
        1: [0, 1, 2, 3, 4, 5],
        2: [6, 7, 8, 9, 10, 11],
        3: [12, 13, 14, 15, 16, 17, 18],
        4: [19, 20, 21, 22, 23, 24, 25],
        5: [26, 27, 28, 29, 30, 31, 32],
        6: [33, 34, 35, 36, 37, 38, 39, 40, 41],
    }
    STAGES_CLEARED_COUNTER = 0x4EC # CONFIRMED: +1 per stage clear (u32)
    UNLOCKED_LEVEL_BITS = None
    LEVEL_MASK_CANDIDATE = 0x550   # 0x07 = 3 levels unlocked (unconfirmed)
    ABILITY_ROOM_OPEN = None
    GAME_CLEARED = None

# The whole save region to snapshot when diffing (covers all 3 slots + header).
SAVE_REGION = (0x302EE000, 0x302F21B4)

# --- Legacy pointer-based fields (kept for the general scanner path) -----------
AP_HEADER = None
SAVE_PTR_GLOBAL = None
SAVE_PTR_SEARCH_RANGE = (0x006EB000, 0x0070B000)

class SaveOffsets:
    IC_CUBE_BITS = None
    IC_CUBE_COUNT = None
    STICKER_BITS = SlotOffsets.STICKER_ARRAY
    STAGE_CLEARED_BITS = None
    UNLOCKED_LEVEL_BITS = None
    ABILITY_ROOM_OPEN = None
    GAME_CLEARED = None

SCENE_STATE_PTR = None
PLAYER_ABILITY = None

# --- Confirmed enums (static) -------------------------------------------------
# Cmn.StoryLevelKind values, from code.bin analysis / world map order.
STORY_LEVEL_KIND = {
    "Level1": 0, "Level2": 1, "Level3": 2,
    "Level4": 3, "Level5": 4, "Level6": 5,
}

# Native accessor addresses (CONFIRMED present in code.bin; used by the
# find_addresses tool to locate the save global by breakpoint/trace, and for
# documentation). Virtual addresses.
NATIVE_ACCESSORS = {
    "IcCubeGetCountAll": 0x00143D94,   # string ref; function nearby
    "IsIcCubeGet": 0x00143C75,
    "saveInfo": 0x00249342,
}


# --- Live (non-save) state, for ability gating --------------------------------
# Kirby's current copy ability lives in the live player object, not the save.
# tools/kpr_find_ability.py pointer-chases from CUBE_GLOBAL and diffs while the
# ability changes, reporting the object + field offset and the numeric value of
# each named ability. Once filled in, the client enforces gating by writing
# ABILITY_NONE whenever Kirby holds an ability the player hasn't received.
# --- Kirby's live copy ability -----------------------------------------------
# Found by tracing the object graph from the scene root (tools/kpr_trace_path.py).
# These are HEAP objects, so the address changes every session we re-walk the
# path each time rather than hardcoding an address.
#
#   p = [0x0070a7f0]; for off in ABILITY_CHASE: p = [p + off]
#   ability_byte = p + ABILITY_FIELD_OFF          (a u8, Cmn.StepAbilityKind)
#
# The walk is validated on every use: if any hop is null/out of range, or the
# value isn't a valid ability, we do nothing that tick. Writes additionally
# require the value to have been stable across two polls, so a bad walk can
# never scribble over unrelated memory.
# Kirby's live copy ability sits at a FIXED address the same one turned up in
# two separate scans, in different sessions. (Robobot places a lot of its state
# statically; the save data behaves the same way.) So no pointer chasing.
#
# Two addresses track the ability correctly. Only one of them is likely to be the
# field the game *acts* on; the other is probably a copy the HUD reads. Writing to
# a display copy would change the icon while Kirby kept the ability, so we don't
# guess tools/kpr_test_write.py writes to each and asks what actually happened.
# Live testing showed what these two actually are:
#   0x31913128 reads Kirby's ability, but only until you change rooms, after
#                which it's stale (and reads nonsense like 36 or 255 mid-cutscene)
#   0x31a9b7fc NOT Kirby's ability at all. It's the ability of the *star that
#                pops out when you press X*. Set it to Poison while holding
#                Cutter and a Poison star comes out Kirby keeps Cutter.
# Neither is usable. Both are symptoms of the same thing: this state belongs to
# the Hero object, which is recreated on every room load.
ABILITY_CANDIDATES = [0x31913128, 0x31a9b7fc]   # kept for reference only

# Set this to whichever candidate makes Kirby genuinely drop the ability.
# Until then gating stays off rather than writing somewhere we can't justify.
ABILITY_ADDR = None

ABILITY_CHASE = None       # not needed the address is fixed
ABILITY_FIELD_OFF = None

# --- Ability gating via ROM patch (the firubii approach) ---------------------
# We patch Scn.Step.Hero.Common.StateDrink.TryToChangeState (in StepHero.bin) to
# check a gate table before letting Kirby copy an ability. The patched bytecode
# reads gate[abilityKind] from this fixed scratch address; if it's 0, the copy is
# refused. The client keeps the table in sync with what Archipelago has unlocked.
#
# This sidesteps the Hero-object problem entirely: the decision happens inside
# the game, where the ability is in scope, instead of us chasing a moving object.
# Where the ability gate table lives. This one is *checked*, not assumed the
# first attempt used 0x00600000, which turned out to be live game code (reading it
# back gave real ARM instructions), so the client would have been overwriting the
# game's own instructions.
#
# 0x302F21B4 is the byte right after the last save slot
# (0x302F1040 + 0x1174), and it passed every test that matters: it's empty, it
# isn't code, it's writable, and the part I skipped last time the game leaves
# it alone during play. It also sits *outside* the save structures, so the table
# never ends up in the player's save file.
#
# 40 entries x 4 bytes = 160 bytes, ending at 0x302F2254 with room to spare.
ABILITY_GATE_ADDR = 0x302F21B4

# Where the client tells the game how many Code Cubes Archipelago has given you.
# The patched Scn.LvMap.Utility::IsBossStageAvailable uses THIS value (the count
# of Code Cubes Archipelago has given you) in place of your physically collected
# count when deciding whether an Area's boss firewall opens. So the boss gate is
# driven purely by received cubes collecting cubes in-game still sends their
# checks, but only AP-granted cubes open the gate.
# Per-Area received-cube counts, read by the patched IsBossStageAvailable.
# Six u32, indexed by StoryLevelKind (Level1..Level6 -> 0..5).
# Armor copy gating uses its OWN table: sharing one table with base Kirby meant
# receiving an armor mode also unlocked that ability for normal copying.
ARMOR_GATE_ADDR = 0x302F2280
CUBE_TABLE_ADDR = 0x302F2300
CUBE_GRANT_ADDR = None      # superseded by CUBE_TABLE_ADDR
ABILITY_NONE = 0          # Cmn.StepAbilityKind.Normal Kirby with no ability
ABILITY_MAX = 32          # highest valid StepAbilityKind (Leaf)

# --- Lives -------------------------------------------------------------------
# Same idea. The native API is getRestPlayer()/setRestPlayer()/incRestPlayer().
LIVES_CHASE = [0x4, 0x68, 0x8, 0x4, 0x54, 0x8, 0x8, 0x1c]
LIVES_FIELD_OFF = 0xcc
LIVES_MAX = 99            # sanity bound; anything above this means a bad walk

# --- HP ----------------------------------------------------------------------
# Fixed-point with one decimal place: full health (45) is stored as 450.
# Not located yet the scan looked only at aligned offsets and assumed a max of
# exactly 450, which may not hold (Robobot Armor changes Kirby's max HP).
# Traced live: 400 -> 320 -> 400 across (full health -> hit -> healed), i.e.
# 40.0 -> 32.0 -> 40.0 health. A clean round maximum, a sensible chip hit
# (a fifth of the bar), and the shortest of the candidate paths.
# TURNED OFF. Live testing showed this reads an HP-*shaped* value but writing to
# it does nothing, and it goes stale the moment you move to another room. That's
# the giveaway: HP lives on the Hero object, which the game destroys and rebuilds
# on every room load, death and cutscene. No fixed address can survive that it
# needs a pointer path to Kirby himself, re-walked each time (see below).
HP_STATIC_BASE = 0x0070A80C   # HP chain starts here (scene global + 0x1C)
# CONFIRMED chase, traced live from the verified real HP address. The previous
# six-hop chase was stale: it resolved to a real object holding a plausible HP
# value, so healing "succeeded" in the log while the health bar never moved. This
# path was found by walking outward from the static root to the address that was
# proven to be real HP (writing it changes actual health, and damage continues
# counting down from the written value).
HP_CHASE = [0x450, 0x78, 0x14, 0x468]
HP_FIELD_OFF = 0x440
# Note on visuals: writing HP does NOT repaint the health bar straight away. The
# game only redraws it on the next damage or heal event, so a heal can look like
# it did nothing until Kirby next takes a hit. The value itself is correct.
HP_SCALE = 10             # stored value / 10 = displayed health (fixed-point,
                          #   ones place is the decimal: 400 stored = 40.0 shown)
# Max HP is NOT fixed. It was 40.0 (stored 400) when the pointer chain above was
# traced, but HP-up pickups (and possibly armor) raise it, and firubii measured
# 45. So the client must read the live value rather than assume a constant a
# Maxim Tomato should top off to whatever the current max is. HP_MAX below is only
# a fallback/plausibility anchor, not the authoritative cap.
HP_MAX = 450              # upper reference only; real max is read live (see client)
# Kirby's max health is 45, stored fixed point as 450. A scan of a live game
# turned up an enemy with the same current/max/display shape but a max of 200,
# so requiring a Kirby-sized MAX is what keeps heals off other creatures.
# Kirby's HP as measured in a live session. Heap objects move between runs, so
# this is only a starting point for the local sweep, never trusted on its own:
# every read is still checked against the current/max signature.
HP_KNOWN_ADDR = 0x31A96218

# Invincibility timer, found by watching memory through a candy pickup: it read
# 1336 the instant the candy was collected and counted down to zero. At 60fps
# that's about 22 seconds, which matches how long the candy lasts, and it sits in
# the same region as Kirby's other state.
#
# Like HP this moves between sessions, so it's a starting hint rather than gospel
# and the client sanity-checks what it reads.
# Invincibility duration, held as a distance from Kirby's health rather than an
# absolute address, since the heap moves every session.
#
# Measured properly in one sitting: Kirby at 0x31A91534 with the timer at
# 0x31A99484, ticking down at about 60 a second while a candy was active. An
# earlier figure of 0x326C was wrong because it subtracted addresses taken from
# two DIFFERENT sessions.
#
# Writing this alone does nothing. The value just sits there: the game only
# counts it down while a separate "invincible" switch is set, and that switch has
# not been located yet, so candies stay queued rather than silently doing
# nothing. See tools/kpr_candyflag.py.
CANDY_TIMER_OFFSET = 0x7F50
CANDY_TIMER_FULL = 1258          # about 21 seconds at 60fps
# The switch. Setting this to 1 makes Kirby sparkle and starts the duration
# ticking; testing each candidate one at a time showed it works alone, while the
# neighbouring byte at +0x7F4D does nothing.
#
# A real candy also fills a small array of pointers at +0x7F64 with objects the
# game allocates (the music handle and the rainbow palette effect, most likely).
# Those can't be fabricated by writing numbers, so a granted candy protects Kirby
# without the fanfare.
# Testing showed this only makes Kirby sparkle: he still took damage with it
# set, so it's the visual half of the effect and not the protection. Left here
# as a record rather than used.
CANDY_SPARKLE_OFFSET = 0x7F4C
CANDY_SWITCH_OFFSET = None

# The real fix is to make the game run its own candy code. Every pickup goes
# through one function that switches on an item kind number, and the candy's
# branch does the whole job: protection, music, palette. The patched ROM logs
# that number to this address so we can find out which one it is.
ITEM_KIND_LOG = 0x302F2410

# Write 1 here and the patch runs the game's real Invincible Candy code on the
# next frame, then clears it. Item kind 9 is the candy, found by logging what
# each pickup reported. Poking memory only ever produced sparkles; this is the
# genuine effect.
# Item kinds, confirmed by logging real pickups: 0 = yellow star, 1 = 1UP,
# 2 = Maxim Tomato, 3 = ordinary food, 4/5/12 = coloured stars, 6 = Code Cube,
# 7 = normal sticker, 8 = rare sticker, 9 = Invincible Candy, 10 = Energy Drink,
# 11 = assist star, 18 = a used assist star reward.
#
# Write one of these kinds here and on the next frame the patch builds a real
# pickup record and hands it to the game's own OnCatch, exactly as though Kirby
# had touched the item. It then clears the word, which is our confirmation.
#
# Because a genuine pickup record is used rather than a copied handler, ordinary
# food works too: its heal amount comes from the record's subKind field.
ITEM_REQUEST = 0x302F2418
ITEM_SUBKIND = 0x302F241C   # food sub-kind, written before the request

# In-stage heartbeat. The patch writes 1 here every frame from inside
# MoveUtil.UpdateMoveTarget, which only runs while Kirby exists in a stage, so
# this answers "am I in a stage" outright instead of hunting for Kirby's health
# in RAM. The client zeroes it after each read, so seeing it set again means the
# game wrote it again.
IN_STAGE_HEARTBEAT = 0x302F2420
ITEM_KIND_1UP = 1
ITEM_KIND_MAXIM = 2
ITEM_KIND_FOOD = 3
ITEM_KIND_CANDY = 9
ITEM_KIND_ENERGY = 10

CANDY_REQUEST = ITEM_REQUEST

# Kirby's max health, exactly: 45 shown in game, stored fixed point x10. Matching
# on a RANGE instead of this value caused a 300-max object to be mistaken for
# Kirby, and every address derived from it pointed at unrelated memory.
KIRBY_MAX_HP = 450

HP_MAX_MIN = 300
HP_MAX_PLAUSIBLE = 600    # sanity bound (60.0). A real HP read is <= max (<=450);
                          #   above this means the pointer walk landed on garbage.

# Cmn.StepAbilityKind, straight from the game's own enum in mint/Default.bin.
# Player-facing name -> the value the game stores.
from . import Constants as _C
ABILITY_KIND = dict(_C.ABILITY_VALUES)


def ability_gating_ready() -> bool:
    """Live once we know which of the two addresses the game actually acts on."""
    return ABILITY_ADDR is not None and bool(ABILITY_KIND)


def lives_ready() -> bool:
    return LIVES_CHASE is not None and LIVES_FIELD_OFF is not None


def hp_ready() -> bool:
    """HP is fixed-point (45 health stored as 450) and now located via HP_CHASE
    from HP_STATIC_BASE, so Food / Energy Drink / Maxim Tomato can heal."""
    return HP_CHASE is not None and HP_FIELD_OFF is not None


def is_ready() -> bool:
    """True once we can locate the save and read cubes.

    Both are now solved: the save is at a fixed FCRAM address, and cubes are read
    by walking the game's own getCubeStruct() chain (see SlotOffsets above), which
    was verified live against a known 15-cube save."""
    return SAVE_SLOTS is not None and SlotOffsets.CUBE_GLOBAL is not None


# --- Armor gating (IN PROGRESS) ----------------------------------------------
# The armor's ability copy flows through ArmoredCommon.StateEat.procAnim, which
# calls ArmoredCommon.StateCopyPre.ChangeState(Obj, int) the second int arg is
# the ability kind. THIS is the correct gate target (not the StateCopy/StateCopyPre
# constructor we patched before, which is why armor gating didn't work). Next step:
# gate ChangeState check the ability-kind arg against the unlock table and block
# the state change (or zero the kind to Normal) when locked.


# --- Stage clear flags (CONFIRMED live) --------------------------------------
# Found by differential scan and verified against a real save: clearing a stage
# flips byte 7 of that stage's 8-byte row. The array sits at a FIXED address in
# the save block, 0xA54 bytes before save slot 0, so no pointer chasing is needed.
#
#   cleared = *(STAGE_ARRAY_ADDR + real_index*8 + 7)
#
# Row layout (from code.bin IsStageCleared @ 0x27B72C, confirmed by Angie):
#   bytes 0..4 = code cube collection state
#   byte 5     = stage opened   (walkable to on the map)
#   byte 6     = stage unlocked (enterable)
#   byte 7     = stage cleared
STAGE_ARRAY_ADDR = 0x302EE304
STAGE_ROW_SIZE = 8
STAGE_CLEAR_BYTE = 7
# firubii's layout for each 8-byte stage row:
#   bytes 0-4 : code cube collection state
#   byte 5    : OPENED   (you can walk to it on the area map)
#   byte 6    : UNLOCKED (you can enter and play it)
#   byte 7    : CLEARED
# Walkability is this save flag, not a live check: the game only writes it
# during the little cutscene after you finish a stage, which is why receiving
# cubes on the stage-select screen never opened anything.
STAGE_OPENED_BYTE = 5
STAGE_UNLOCKED_BYTE = 6

# Each Area's rows run: normal stages, then the BOSS, then the EX stage. For
# Areas 1-5 that makes the boss second-to-last and EX last. Getting this wrong
# left the boss counted as a normal stage, so "open all stages" threw the boss
# door open while locking EX instead.
#
# Access Ark (Area 6) is the exception: after its boss and EX come two more
# stages (the game's own "extra" entries, rows 40 and 41). So its boss is NOT
# second-to-last; it sits at row 38 with EX at 39. Assuming the last-two layout
# there pointed the gate at the two trailing stages and left the real boss and
# EX ungated, which is why only the Access Ark boss and EX were open when they
# shouldn't have been.
#
# Normal-stage counts from the layout: Patched Plains and Resolution Road have
# four, Overload Ocean through Rhythm Route and Access Ark have five, each plus
# a boss and an EX (and Access Ark plus two extra stages).
BOSS_STAGE_INDEX = {1: 4, 2: 10, 3: 17, 4: 24, 5: 31, 6: 38}
EX_STAGE_INDEX = {1: 5, 2: 11, 3: 18, 4: 25, 5: 32, 6: 39}

# Rows that can only be cleared by finishing the game. Star Dream is the final
# fight of the Access Ark boss stage rather than its own map stage, so which of
# these the ending writes isn't obvious; the goal accepts a clear on any.
# Bytes in the save file that flip from 0 to 1 the moment Star Dream goes down,
# found by watching the whole save area while finishing the game. Beating the
# game writes nothing at all to the stage rows, which is why every earlier
# attempt to spot a "cleared" row failed no matter which row it watched.
#
# Five separate flags land together at the kill. Any of them is enough to say
# the game is finished, and reading all five means the goal still fires if the
# game books the ending slightly differently on another route.
GAME_CLEARED_FLAGS = (0x028E, 0x02A4, 0x02A6, 0x02A8, 0x02B6)

# Smallest and largest of the above, so the client can pull them in one read.
GAME_CLEARED_FIRST = min(GAME_CLEARED_FLAGS)
GAME_CLEARED_SPAN = max(GAME_CLEARED_FLAGS) - GAME_CLEARED_FIRST + 1

# Also written when the game is beaten, kept for reference rather than used:
#   +0x045C, +0x045D   a clear time (read 60 and 11 on the run that found these)
#   +0x04E8            a count that goes up by one
#   +0x0474, +0x047C   live counters that tick constantly during play, ignore
#
# Post-game unlocks, recorded now in case they're ever wanted as locations:
# Every time the Robobot Armor decides whether it may copy something, the patch
# writes the ability id it was asked about here. Used by /armorlog to find out
# what id a dropped ability star reports, which is the open question behind the
# star not being re-scannable.
# What the armor's copy check actually RETURNED, plus one so that zero still
# means "no call since the client last looked". The earlier log only echoed the
# client's own view of which modes were received, which is not the same thing as
# what the game decided, and that sent the search down a wrong path.
ARMOR_COPY_RESULT = 0x302F242C

ARMOR_COPY_LOG = 0x302F2424
# The patch writes the ability id plus this bias, so a value of zero always
# means "no check since the client last looked" even for ability id zero.
ARMOR_COPY_BIAS = 0x1000

META_KNIGHTMARE_UNLOCK = 0x0442
THE_ARENA_UNLOCK = 0x0444

END_GAME_ROWS = (38, 40, 41, 42)


def stage_row_addr(index: int) -> int:
    """Address of one stage's 8-byte row."""
    return STAGE_ARRAY_ADDR + index * STAGE_ROW_SIZE
STAGE_OPENED_BYTE = 5
STAGE_UNLOCKED_BYTE = 6

# Sequential per-stage indices, decoded from the game's own index tables.
# Boss and EX stages are included as ordinary stages here.
STAGE_ARRAY_INDEX = {
    1: [0, 1, 2, 3, 4, 5],
    2: [6, 7, 8, 9, 10, 11],
    3: [12, 13, 14, 15, 16, 17, 18],
    4: [19, 20, 21, 22, 23, 24, 25],
    5: [26, 27, 28, 29, 30, 31, 32],
    6: [33, 34, 35, 36, 37, 38, 39, 40, 41],
}


def stage_clear_addr(area: int, stage: int):
    """Absolute address of the 'cleared' byte for area/stage (both 1-based)."""
    try:
        idx = STAGE_ARRAY_INDEX[area][stage - 1]
    except (KeyError, IndexError):
        return None
    return STAGE_ARRAY_ADDR + idx * STAGE_ROW_SIZE + STAGE_CLEAR_BYTE


# Star Dream is its own stage, StoryStageKind L7S1 = row 42. The game treats it
# as a seventh "area" reached by beating the Access Ark boss, so finishing the
# story means THIS row is cleared, not Access Ark's boss row.
STAR_DREAM_INDEX = 42


def stage_array_span():
    """(start, length) covering every stage row, for one bulk read.

    Includes Star Dream's row, which sits past the six Areas. The span used to
    stop at row 41, so the row that actually marks the story as finished was
    never even read.
    """
    last = max(i for v in STAGE_ARRAY_INDEX.values() for i in v)
    last = max(last, STAR_DREAM_INDEX)
    return STAGE_ARRAY_ADDR, (last + 1) * STAGE_ROW_SIZE


def stages_ready() -> bool:
    return STAGE_ARRAY_ADDR is not None


# --- In-game heal request (repaints the bar) ---------------------------------
# Writing HP directly works but never repaints the health bar: the HUD is only
# refreshed by the game's own heal/damage routines. So instead of poking HP, the
# StepHero patch watches this scratch word every movement frame and, when it is
# non-zero, runs the game's OWN heal sequence (the same calls ItemCollReact.
# OnCatch makes when you eat food) followed by CalcInfoHPRate and the HUD push.
# The bar therefore updates instantly, exactly as if Kirby had eaten something.
# The patch clears the word afterwards, so each request fires once.
HEAL_REQUEST_ADDR = 0x302F2400
# Modes written to HEAL_REQUEST_ADDR:
#   1 = restore to full, then refresh the bar (Maxim Tomato)
#   2 = refresh the bar only; the client has already written the HP value itself
#       (used for partial heals like ordinary food and Energy Drink, since the
#        game's own heal call always tops you all the way up)
HEAL_MODE_FULL = 1
HEAL_MODE_REPAINT = 2   # non-zero asks the game to refresh the bar
HEAL_FULL_ADDR = 0x302F2404      # non-zero also runs the game's full-restore
