"""
KirbyRobobotClient.py Archipelago client for Kirby: Planet Robobot.

Runtime model (identical in spirit to A Link Between Worlds):
  * A game-agnostic CTRPluginFramework memory-pipe plugin runs on the console /
    Azahar and exposes UDP :45987 read/write of the game's RAM.
  * This client does ALL the game logic in Python: it polls the save/progress
    structure in RAM to detect collected cubes / stickers / clears (-> sends
    location checks), and writes to RAM to apply received items and gate
    progress (-> lock/unlock levels, grant abilities, etc).
  * No game code is modified at runtime; the ROM patch only tags collectibles
    and plants the AP header/seed for validation.

The exact RAM addresses live in MemoryMap.py. Until they're pinned on Azahar
(via tools/find_addresses.py), the client connects and validates but reports
that the memory map is incomplete instead of guessing.
"""
import asyncio
import struct
from typing import Dict, List, Set

import Utils
from CommonClient import (ClientCommandProcessor, CommonContext, get_base_parser,
                          gui_enabled, logger, server_loop)
from NetUtils import ClientStatus

from . import Constants as C
from . import MemoryMap as M
from .Interface import N3DSInterface, ConnectionLost
from .Locations import LOCATION_TABLE
from .Items import ITEM_TABLE

GAME_NAME = C.GAME_NAME


class KirbyRobobotCommandProcessor(ClientCommandProcessor):
    def _cmd_3ds(self, address: str = ""):
        """Point the client at the game. Use the IP shown on the game screen,
        e.g.  /3ds 111.222.3.44   (not 127.0.0.1 on Azahar see the note.)"""
        if not address:
            logger.info("Usage: /3ds <IP shown on the game screen>, "
                        "e.g. /3ds 111.222.3.44")
            return
        if address.strip() in ("127.0.0.1", "localhost"):
            logger.warning("127.0.0.1 usually does NOT work on Azahar reads and "
                           "writes go to the wrong place and everything silently "
                           "misbehaves. Use the IP the plugin prints on screen "
                           "(e.g. /3ds 111.222.3.44). Connecting anyway...")
        self.ctx.n3ds_address = address
        self.ctx.want_connect = True
        self.ctx.game_connected = False
        self.ctx.connect_warned = False
        self.ctx._last_connect_attempt = 0.0   # retry right away
        logger.info("Connecting to the game at %s:45987 ...", address)

    def _cmd_armorlog(self):
        """Report every ability the Robobot Armor is asked about.

        Turn this on, then scan an enemy that gives a mode you own, and note the
        id. Then drop that mode with X and try to scan the star back, and note
        what comes up. If the star reports a different id than the enemy did,
        that's why it can't be re-absorbed. If nothing is reported at all, the
        star never reaches the copy check and the problem is further upstream."""
        ctx = self.ctx
        ctx.armor_log = not getattr(ctx, "armor_log", False)
        ctx._armor_last = None
        logger.info("Armor copy logging is now %s.", "ON" if ctx.armor_log else "OFF")

    def _cmd_tracker(self):
        """Show what you can go and get right now, and what each remaining
        location is still waiting on."""
        ctx = self.ctx
        if not ctx.slot_data:
            logger.info("Connect to the multiworld first.")
            return
        for line in tracker_lines(ctx):
            logger.info(line)

    def _cmd_watchsave(self):
        """Arm or disarm save watching.

        Turn this on just before the final fight. From then on the client keeps a
        copy of your save file and reports any byte that changes, with its offset
        and old and new values. Beating the game has to write something
        somewhere, and none of the stage rows move, so this finds it. Paste the
        lines it prints and the goal can key off the right byte.

        Leave it off during normal play, it's noisy."""
        ctx = self.ctx
        ctx.save_watch = not getattr(ctx, "save_watch", False)
        ctx._save_snapshot = None
        logger.info("Save watching is now %s.", "ON" if ctx.save_watch else "OFF")
        if ctx.save_watch:
            logger.info("Play up to and through the ending. Every change will be "
                        "logged as offset=old->new relative to the save file.")


class KirbyRobobotContext(CommonContext):
    game = C.GAME_NAME
    command_processor = KirbyRobobotCommandProcessor
    items_handling = 0b111        # full remote items

    def __init__(self, server_address, password):
        super().__init__(server_address, password)
        self.iface = N3DSInterface()
        # No default target. On Azahar, 127.0.0.1 usually HALF-works: the pipe
        # connects but reads/writes land in the wrong place, so checks, stickers,
        # lives and the ability gate all silently misbehave. Require the player to
        # point at the IP the plugin prints on the game screen (/3ds 192.168.x.x).
        self.n3ds_address = None
        self.want_connect = False
        self._told_how_to_connect = False
        self.game_connected = False
        self.checked_locally: Set[int] = set()
        self.received_locations: Set[int] = set()
        self.last_received_index = 0
        self.goal_sent = False
        self.goal_is_boss_count = False             # slot_data: goal
        self.story_boss_count = 6                   # slot_data
        self._bosses_seen = None
        self.save_watch = False                     # /watchsave toggle
        self.armor_log = False                      # /armorlog toggle
        self._armor_last = None
        self._save_snapshot = None
        # --- gating state ---
        self.unlocked_abilities: Set[str] = set()   # copy abilities received
        self.unlocked_armor: Set[str] = set()       # armor + modes received
        self.cubes_owed = 0                         # (legacy, unused with per-area)
        self.area_cubes_owed = {}                    # level_id -> received cube count
        self._cube_table_last = b''                  # last per-Area gate table written
        self._last_connect_attempt = 0.0
        self.connect_warned = False
        # value -> ability name, built from MemoryMap.ABILITY_KIND
        self.ability_value_to_name = {v: k for k, v in M.ABILITY_KIND.items()}
        # collectible / item application state
        self.stickers_owed = []
        self.stickers_written = set()
        # album indices AP has granted us (rare sticker items received). These
        # should show in the album ONLY once their own location check is done;
        # while the check is still pending we keep the album slot clear so the
        # physical pickup stays collectable in its level.
        self.stickers_granted: Set[int] = set()
        self.stickers_hidden: Set[int] = set()      # granted stickers cleared right now
        self._sticker_map_streak = 0                # consecutive map polls seen
        self._heartbeat_seen = False                # ROM heartbeat detected?
        self._dbg_in_level = None                   # last in_level decision
        self.cubes_owed = 0
        self.item_queue = []          # consumables waiting: (kind, subKind)
        self._heal_req_posted = False
        self._item_posted = None
        self.hp_max_seen = 0
        # gating / deathlink
        self.death_link_on = False
        self.ability_gate_on = False
        self.armor_gate_on = False
        self.rare_stickers_on = True                # yaml: rare_sticker_checks
        self.normal_stickers_on = False             # yaml: sticker_checks
        self.open_all_stages = True   # default on; slot_data confirms
        self.death_owed = False
        self.was_dead = False
        self._hp_seen_alive = False
        self._hp_last_good = None
        self._hp_want_rescan = False
        self.ignore_next_death = False
        self._last_ability = None
        self._ability_warned = set()
        # loop bookkeeping (must exist or the watcher throws and dies silently)
        self.first_read_done = False
        self._poll_count = 0
        self._error_reported = False
        self._dbg_body = False
        self._dbg_notready = False

    async def server_auth(self, password_requested: bool = False):
        if password_requested and not self.password:
            await super().server_auth(password_requested)
        await self.get_username()
        await self.send_connect()

    def on_package(self, cmd: str, args: dict):
        if cmd == "Connected":
            self.slot_data = args.get("slot_data", {})
            logger.info("Connected to multiworld. Goal: %s", self.slot_data.get("goal"))
            # goal 1 is story_boss_count; anything else finishes at Star Dream.
            self.goal_is_boss_count = self.slot_data.get("goal") == 1
            self.story_boss_count = self.slot_data.get("story_boss_count", 6)
            if self.goal_is_boss_count:
                logger.info("Goal is %d Story boss(es).", self.story_boss_count)
            if self.slot_data.get("ability_gating"):
                self.ability_gate_on = True
                logger.info("Ability gating is on.")
            self.open_all_stages = bool(
                self.slot_data.get("open_all_stages", True))
            if self.slot_data.get("armor_gating"):
                self.armor_gate_on = True
                logger.info("Armor mode gating is on.")
            # Sticker handling only touches the album for the kinds the yaml
            # actually turned into locations. With a kind switched off there's
            # nothing to check, so its stickers are left completely alone.
            self.rare_stickers_on = bool(
                self.slot_data.get("rare_sticker_checks", True))
            self.normal_stickers_on = bool(
                self.slot_data.get("sticker_checks", False))
            if self.slot_data.get("death_link"):
                self.death_link_on = True
                Utils.async_start(self.update_death_link(True))
                logger.info("DeathLink is on.")

    def on_deathlink(self, data: dict):
        """Someone else died so does Kirby."""
        self.death_owed = True
        super().on_deathlink(data)

    def run_gui(self):
        from kvui import GameManager

        ctx = self

        class KRManager(GameManager):
            # A second log pane becomes the tracker tab. Archipelago's client
            # UI builds one tab per logging pair, so a tracker that lives in the
            # window costs nothing extra and needs no separate download.
            logging_pairs = [("Client", "Archipelago"), ("Tracker", "Tracker")]
            base_title = "Archipelago Kirby: Planet Robobot Client"

            def build(self):
                root = super().build()
                # Redraw the tracker a moment after connecting, and then
                # whenever something arrives.
                from kivy.clock import Clock
                Clock.schedule_interval(lambda _dt: self.refresh_tracker(), 2.0)
                return root

            def refresh_tracker(self):
                """Rewrite the tracker tab if anything has changed.

                Comparing against the last drawn text means the pane is not
                cleared and rebuilt every couple of seconds, which would fight
                with scrolling while you are reading it.
                """
                if not ctx.slot_data:
                    return
                try:
                    lines = tracker_lines(ctx)
                except Exception as exc:
                    lines = ["The tracker could not be drawn: %r" % (exc,)]
                text = "\n".join(lines)
                if text == getattr(self, "_tracker_text", None):
                    return
                self._tracker_text = text
                log = logging.getLogger("Tracker")
                for h in list(log.handlers):
                    buf = getattr(h, "text_widget", None)
                    if buf is not None:
                        try:
                            buf.text = ""
                        except Exception:
                            pass
                for line in lines:
                    log.info(line)

        self.ui = KRManager(self)
        self.ui_task = asyncio.create_task(self.ui.async_run(), name="UI")


async def _ensure_game(ctx: KirbyRobobotContext) -> bool:
    """Connect to the memory pipe. Says clearly what's happening a silent retry
    loop is why 'connected but nothing sends' is so confusing."""
    if ctx.game_connected:
        return True
    if not ctx.want_connect or not ctx.n3ds_address:
        if not ctx._told_how_to_connect:
            ctx._told_how_to_connect = True
            logger.info("Not connected to the game yet. Once Kirby: Planet "
                        "Robobot is running in Azahar (past the title screen), "
                        "run:  /3ds <IP shown on the game screen>  "
                        "e.g. /3ds 111.222.3.44")
        return False

    import time
    now = time.time()
    if now - ctx._last_connect_attempt < 5.0:
        return False
    ctx._last_connect_attempt = now

    ok = await ctx.iface.connect(ctx.n3ds_address, M.TITLE_ID_NA)
    if ok:
        ctx.game_connected = True
        ctx.connect_warned = False
        logger.info("Connected to the game at %s. Checks will now send.",
                    ctx.n3ds_address)
        return True

    if not ctx.connect_warned:
        ctx.connect_warned = True
        logger.warning("Can't reach the game at %s:45987.", ctx.n3ds_address)
        logger.warning("  * The game must be RUNNING in Azahar, past the title screen.")
        logger.warning("  * Use the IP the plugin prints on the game screen, e.g.:")
        logger.warning("        /3ds 111.222.3.44")
        logger.warning("  (Retrying quietly in the background.)")
    return False


_LOC_BY_ID = {d.code_offset: (name, d) for name, d in LOCATION_TABLE.items()}

# "Rare Sticker: Ultra Sword" -> the album index that sticker occupies, so a
# received rare-sticker item puts the right sticker in the player's album.
# Item name -> album index, for both rare and normal stickers, so a received
# sticker item puts that exact sticker in the player's album.
_RARE_ITEM_TO_ALBUM = {}
for _n, _d in LOCATION_TABLE.items():
    if _d.sticker_index is None:
        continue
    if _d.category == "rare":
        # "Rare Sticker: Fluff (2-2)" -> item "Rare Sticker: Fluff"
        _RARE_ITEM_TO_ALBUM[_n.rsplit(" (", 1)[0]] = _d.sticker_index
    elif _d.category == "sticker":
        # "Sticker: Kracko" -> item of the same name
        _RARE_ITEM_TO_ALBUM[_n] = _d.sticker_index
_ITEM_BY_ID = {d.code_offset: (name, d) for name, d in ITEM_TABLE.items()}


async def resolve_cube_base(ctx: KirbyRobobotContext, slot_index: int = 0):
    """Walk the game's own getCubeStruct() chain to find the cube byte array.

        G    = [0x0070a7f0]
        A    = [G + 4]
        C    = [A + 0x2A628 + 4]
        base = C + slot*0x1174 + 0x2738

    Returns None if the scene isn't loaded yet (e.g. on the title screen)."""
    off = M.SlotOffsets
    try:
        G = await ctx.iface.read_u32(off.CUBE_GLOBAL)
        if not G:
            return None
        A = await ctx.iface.read_u32(G + 4)
        if not A:
            return None
        C = await ctx.iface.read_u32(A + off.CUBE_CHAIN_OFF + 4)
        if not C:
            return None
        return C + slot_index * M.SAVE_SLOT_SIZE + off.CUBE_BASE_OFF
    except Exception:
        return None


async def read_cube_bytes(ctx: KirbyRobobotContext, n_stages: int = 40) -> bytes:
    """Read the raw per-stage cube rows (8 bytes each)."""
    base = await resolve_cube_base(ctx, M.ACTIVE_SLOT)
    if base is None:
        return b""
    off = M.SlotOffsets
    size = off.CUBE_FIRST_OFF + n_stages * off.CUBE_STAGE_STRIDE
    try:
        return await ctx.iface.read(base, size)
    except Exception:
        return b""


def cube_collected(rows: bytes, stage_index: int, cube_index: int) -> bool:
    """Mirror IsIcCubeGet: byte at base + stage*8 + idx + 8; nonzero = collected."""
    off = M.SlotOffsets
    pos = off.CUBE_FIRST_OFF + stage_index * off.CUBE_STAGE_STRIDE + cube_index
    if pos >= len(rows):
        return False
    return rows[pos] != 0


def tracker_lines(ctx):
    """The tracker view: what is open, what is not, and why not.

    The judgement comes from Logic, the same module generation uses, so this
    cannot claim a location is reachable when the seed disagreed. What the
    client adds is the live picture: which items have actually arrived and which
    locations have already been sent.
    """
    from . import Logic
    from .Locations import LOCATION_TABLE

    opts = {
        "ability_gating": bool(ctx.slot_data.get("ability_gating")),
        "armor_gating": bool(ctx.slot_data.get("armor_gating")),
        "goal": ctx.slot_data.get("goal", 0),
        "story_boss_count": ctx.slot_data.get("story_boss_count", 6),
    }

    items = {}
    for net in getattr(ctx, "items_received", []):
        nm = ctx.item_names.lookup_in_game(net.item) if hasattr(ctx, "item_names") else None
        if nm:
            items[nm] = items.get(nm, 0) + 1

    # Only judge locations this seed actually has. The table describes every
    # location the world can produce, but the yaml decides which exist, so
    # evaluating the table wholesale would list checks that were never in play.
    in_seed = set(ctx.checked_locations) | set(ctx.missing_locations)
    table = {}
    for code in in_seed:
        nm = _LOC_BY_ID.get(code, (None, None))[0]
        if nm and nm in LOCATION_TABLE:
            table[nm] = LOCATION_TABLE[nm]
    if not table:
        return ["Waiting for the multiworld to send the location list."]

    checked = set()
    for code in ctx.checked_locations:
        nm = _LOC_BY_ID.get(code, (None, None))[0]
        if nm:
            checked.add(nm)

    done, open_now, blocked = Logic.evaluate(table, items, opts, checked)

    def count(n):
        return items.get(n, 0)

    lines = []
    lines.append("%d checked, %d available now, %d not yet reachable"
                 % (len(done), len(open_now), len(blocked)))
    goal_txt = ("beat %s Story boss(es)" % opts["story_boss_count"]
                if opts["goal"] == 1 else "defeat Star Dream")
    lines.append("Goal: %s -- %s" % (
        goal_txt,
        "reachable" if Logic.goal_met(opts, count) else "not yet reachable"))
    lines.append("")

    if open_now:
        lines.append("Available now:")
        by_area = {}
        for nm in open_now:
            d = table[nm]
            by_area.setdefault(getattr(d, "level", None) or "Other", []).append(nm)
        for lv in sorted(by_area, key=lambda x: str(x)):
            label = C.area_name(lv) if lv in C.LEVELS else str(lv)
            lines.append("  %s (%d)" % (label, len(by_area[lv])))
            for nm in by_area[lv][:40]:
                lines.append("     %s" % nm)
            if len(by_area[lv]) > 40:
                lines.append("     ... and %d more" % (len(by_area[lv]) - 40))
        lines.append("")

    if blocked:
        lines.append("Waiting on something:")
        shown = 0
        for nm in blocked:
            miss = Logic.missing_for(nm, table[nm], items, opts)
            if not miss:
                continue
            lines.append("  %s" % nm)
            lines.append("     needs: %s" % ", ".join(miss))
            shown += 1
            if shown >= 60:
                lines.append("  ... and %d more" % (len(blocked) - shown))
                break
    return lines


async def _read_in_stage(ctx: KirbyRobobotContext) -> bool:
    """Are we inside a stage right now?

    The patched ROM writes a heartbeat every frame from a function that only
    runs while Kirby exists in a stage, so this is a direct answer rather than a
    guess. We zero the word after reading it, so the next poll only sees it set
    if the game wrote it again.

    On a ROM without the patch nothing ever writes it, so until we've seen a
    single heartbeat we fall back to hunting for Kirby's health block. That
    search is the unreliable part (the address moves between sessions and the
    scan can miss, which left the client thinking you were never in a stage), so
    once one heartbeat arrives we trust it and stop scanning.
    """
    addr = getattr(M, "IN_STAGE_HEARTBEAT", None)
    if addr is not None:
        try:
            beat = struct.unpack("<I", await ctx.iface.read(addr, 4))[0]
        except Exception:
            beat = 0
        if beat:
            ctx._heartbeat_seen = True
            try:
                await ctx.iface.write(addr, struct.pack("<I", 0))
            except Exception:
                pass
            return True
        if ctx._heartbeat_seen:
            return False
    return await resolve_hp_addr(ctx) is not None



async def watch_armor_copy(ctx: KirbyRobobotContext):
    """Report each armor copy check: the ability asked about and the answer.

    The answer is read back out of the game rather than inferred here, so this
    says what the game actually decided. An earlier version reported the
    client's own record of which modes had been received and labelled it as the
    gate's verdict, which was misleading whenever the two disagreed.
    """
    if not getattr(ctx, "armor_log", False):
        return
    addr = getattr(M, "ARMOR_COPY_LOG", None)
    if addr is None:
        return
    try:
        raw = struct.unpack("<I", await ctx.iface.read(addr, 4))[0]
        res = struct.unpack("<I", await ctx.iface.read(M.ARMOR_COPY_RESULT, 4))[0]
    except Exception:
        return
    if raw == 0:
        return
    try:
        await ctx.iface.write(addr, struct.pack("<I", 0))
        await ctx.iface.write(M.ARMOR_COPY_RESULT, struct.pack("<I", 0))
    except Exception:
        pass
    val = raw - M.ARMOR_COPY_BIAS
    name = None
    for nm, kind in C.ABILITY_VALUES.items():
        if kind == val:
            name = nm
            break
    if res == 0:
        answer = "no answer recorded"
    else:
        answer = "ALLOWED" if (res - 1) else "REFUSED"
    logger.info("Armor copy check: id %d (%s) -> game answered %s "
                "(client has it as received=%s)",
                val, name or "unknown id", answer,
                name in ctx.unlocked_armor if name else None)


async def watch_save_diff(ctx: KirbyRobobotContext):
    """Report any byte that changes in the save area, while watching is armed.

    This exists because finishing the game leaves no mark on any stage row we
    know about, so whatever flag it does set has to be found by watching rather
    than guessed at.

    The window covers both structures that matter and the gap between them: the
    stage array (which sits below the save files) through the end of the first
    save file. Each change is reported with its absolute address and, where it
    lands in something we recognise, what that byte means.
    """
    if not getattr(ctx, "save_watch", False):
        return
    base = min(M.STAGE_ARRAY_ADDR, M.SAVE_SLOTS[M.ACTIVE_SLOT])
    top = M.SAVE_SLOTS[M.ACTIVE_SLOT] + M.SAVE_SLOT_SIZE
    size = top - base
    CHUNK = 0x200
    buf = bytearray()
    try:
        off = 0
        while off < size:
            n = min(CHUNK, size - off)
            buf += await ctx.iface.read(base + off, n)
            off += n
    except Exception:
        return
    cur = bytes(buf)
    prev = getattr(ctx, "_save_snapshot", None)
    ctx._save_snapshot = cur
    if prev is None or len(prev) != len(cur):
        logger.info("Save watching: baseline taken (0x%X bytes from 0x%08X).",
                    len(cur), base)
        return
    diffs = [(i, prev[i], cur[i]) for i in range(len(cur)) if prev[i] != cur[i]]
    if not diffs:
        return

    def describe(addr):
        sa = M.STAGE_ARRAY_ADDR
        span = M.stage_array_span()[1] if hasattr(M, "stage_array_span") else 0
        if sa <= addr < sa + span:
            rel = addr - sa
            row, byte = divmod(rel, M.STAGE_ROW_SIZE)
            what = {M.STAGE_OPENED_BYTE: "opened",
                    M.STAGE_UNLOCKED_BYTE: "unlocked",
                    M.STAGE_CLEAR_BYTE: "cleared"}.get(byte, "byte %d" % byte)
            return "stage row %d %s" % (row, what)
        slot = M.SAVE_SLOTS[M.ACTIVE_SLOT]
        if slot <= addr < slot + M.SAVE_SLOT_SIZE:
            return "save file +0x%04X" % (addr - slot)
        return "between the two"

    logger.info("Save changed at %d byte(s):", len(diffs))
    for i, a, b in diffs[:24]:
        addr = base + i
        logger.info("   0x%08X = %02X -> %02X   (%s)", addr, a, b, describe(addr))
    if len(diffs) > 24:
        logger.info("   ... and %d more", len(diffs) - 24)


def _sticker_kind_enabled(ctx: KirbyRobobotContext, category: str) -> bool:
    """Is this kind of sticker actually part of the seed?

    Nothing should touch a sticker whose kind the yaml left switched off. With
    Stickersanity off there are no normal sticker checks to earn, so a normal
    sticker you pick up is just yours: no check to send, and nothing to clear
    out of the album.
    """
    if category == "rare":
        return bool(getattr(ctx, "rare_stickers_on", True))
    if category == "sticker":
        return bool(getattr(ctx, "normal_stickers_on", False))
    return False


async def read_save_state(ctx: KirbyRobobotContext):
    """Read what we need from the game.

    Each read is guarded on its own. An earlier version let a single failed read
    throw, which the watcher's catch-all then swallowed so one unreadable value
    silently stopped every check, for the whole session. Now a read that fails
    just leaves that piece out, and the rest still works."""
    if not M.is_ready():
        return None
    slot = M.SAVE_SLOTS[M.ACTIVE_SLOT]
    off = M.SlotOffsets
    state = {"slot": slot}

    # Are we actually inside a stage? Kirby's HP only reads like health while
    # he exists: outside a stage that word holds 0x7FBFFFFF, which the health
    # test rejects outright. Measured on a live game, so this is the signal
    # rather than a guess.
    #
    # The scene-root pointer was tried for this and was useless: it resolves on
    # the area map too, so it answered True permanently.
    try:
        state["in_level"] = await _read_in_stage(ctx)
    except Exception:
        state["in_level"] = False

    ctx._dbg_in_level = state["in_level"]

    # Stickers (the save sits at a fixed address, so this is a plain read).
    try:
        state["sticker_arr"] = await ctx.iface.read(slot + off.STICKER_ARRAY,
                                                    off.STICKER_COUNT * 2)
    except Exception as e:
        state["sticker_arr"] = b""
        if not getattr(ctx, "_dbg_sticker_err", False):
            ctx._dbg_sticker_err = True
            logger.warning("Couldn't read the sticker album: %r", e)

    try:
        state["stages_cleared"] = await ctx.iface.read_u32(
            slot + off.STAGES_CLEARED_COUNTER)
    except Exception:
        state["stages_cleared"] = None

    # Cubes live outside the save slot, behind the game's own pointer chain.
    # Per-stage clear flags. Fixed address in the save block, so a plain read.
    try:
        _sa, _slen = M.stage_array_span()
        state["stage_rows"] = await ctx.iface.read(_sa, _slen)
    except Exception:
        state["stage_rows"] = b""

    try:
        state["cube_rows"] = await read_cube_bytes(ctx)
    except Exception as e:
        state["cube_rows"] = b""
        if not getattr(ctx, "_dbg_cube_err", False):
            ctx._dbg_cube_err = True
            logger.warning("Couldn't read the Code Cubes: %r", e)

    # The bytes that flip when the game is beaten. One short read covers all of
    # them, and it's cheap enough to do every poll.
    try:
        state["clear_flags"] = await ctx.iface.read(
            slot + M.GAME_CLEARED_FIRST, M.GAME_CLEARED_SPAN)
    except Exception:
        state["clear_flags"] = b""

    if off.GAME_CLEARED is not None:
        try:
            state["game_cleared"] = (await ctx.iface.read(slot + off.GAME_CLEARED, 1))[0]
        except Exception:
            pass

    sa = state.get("sticker_arr") or b""
    cr = state.get("cube_rows") or b""
    # If we got nothing at all, the game isn't in a readable state yet.
    if not sa and not cr:
        return None
    return state


def _bit(buf: bytes, index: int) -> bool:
    return (buf[index >> 3] & (1 << (index & 7))) != 0


def detect_checks(ctx: KirbyRobobotContext, state) -> List[int]:
    """Map live game state to AP location ids that are now satisfied."""
    found = []
    off = M.SlotOffsets

    # --- Code Cubes (VERIFIED) -----------------------------------------------
    # base + stage_index*8 + slot_index + 8 ; nonzero = collected.
    # Cubes the CLIENT wrote (because AP gave us a Code Cube item) are skipped
    # a received item must never come back as a check for itself.
    rows = state.get("cube_rows") or b""
    if rows:
        for _name, d in _LOC_BY_ID.values():
            if d.category != "cube":
                continue
            if d.stage_index is None or d.slot_index is None:
                continue
            if d.slot_index >= off.CUBES_PER_STAGE:
                continue
            if cube_collected(rows, d.stage_index, d.slot_index):
                found.append(d.code_offset)

    # --- Rare Stickers (VERIFIED) --------------------------------------------
    # 200 x u16 array at save+0x82; nonzero (0x0101) = owned. Each rare placement
    # awards a fixed album index, taken from the game's own Sticker/Config.bin
    # (stepRareKind) and cross-checked against a live save + the walkthrough.
    sarr = state.get("sticker_arr") or b""
    if sarr:
        for _name, d in _LOC_BY_ID.values():
            if d.category != "rare":
                continue
            if not _sticker_kind_enabled(ctx, d.category):
                continue
            si = d.sticker_index
            if si is None or si * 2 + 1 >= len(sarr):
                continue
            # A granted rare we haven't earned yet is owned in the album only
            # because we put it there so it's usable. Its real check is handled
            # in grant_pending_stickers when the game awards it at stage end, so
            # don't let our own write trip it here.
            if si in ctx.stickers_granted and d.code_offset not in ctx.checked_locally:
                continue
            if int.from_bytes(sarr[si * 2: si * 2 + 2], "little") != 0:
                found.append(d.code_offset)

    return found


async def _chase(ctx: KirbyRobobotContext, chain, field_off, base=None):
    """Walk a pointer chain from a static global to a live field.

    `base` is the static address to start from (its stored value is the first
    object). Defaults to the cube/scene global, but HP uses its own base
    (0x0070A80C) found by the backward pointer scan.

    Every hop is checked. These are heap objects that move every session (and can
    vanish between stages), so a failed walk is normal and simply means "not right
    now" never an error."""
    if base is None:
        base = M.SlotOffsets.CUBE_GLOBAL
    try:
        p = await ctx.iface.read_u32(base)
        if not _plausible_ptr(p):
            return None
        for off in chain:
            p = await ctx.iface.read_u32(p + off)
            if not _plausible_ptr(p):
                return None
        return p + field_off
    except Exception:
        return None


def _plausible_ptr(v: int) -> bool:
    return v != 0 and ((0x03000000 <= v < 0x04000000)
                       or (0x08000000 <= v < 0x10000000)
                       or (0x30000000 <= v < 0x38000000))


async def write_ability_gate(ctx: KirbyRobobotContext):
    """Keep the in-game ability gate table in sync with what AP has unlocked.

    Our StepHero patch reads gate[abilityKind] before letting Kirby copy an
    enemy. We write that 33-byte table to a fixed scratch address. Kind values
    come straight from the game's Cmn.StepAbilityKind enum.

    This only matters when the ability-gating ROM patch is installed; writing the
    table is harmless otherwise (it's an unused address in vanilla)."""
    # Either gate can be on independently, and they use different tables, so we
    # can't bail just because base ability gating is off: armor gating alone
    # still needs its table written (that was why armor modes stayed denied no
    # matter what you were sent).
    if not (ctx.ability_gate_on or ctx.armor_gate_on):
        return
    # One 32-bit word per ability kind, marking what is LOCKED:
    #   0 = allowed, Kirby may copy this
    #   1 = locked, refuse it and fall back to Normal
    #
    # POLARITY CONTRACT, verified against the shipped bytecode rather than
    # assumed. Both gates compile to:
    #     ldsra4 rN, [table + kind*4]
    #     jmpneg rN, +k          ; jmpneg branches when the value is ZERO
    #     ldsrzr <kind reg> = 0  ; only reached when the value is NONZERO
    # so a zero word skips the forced downgrade (allowed) and a non-zero word
    # runs it (locked).
    #
    # jmpneg's meaning was confirmed from vanilla HitPointUtil.CalcInfoHPRate,
    # where "ltf32 r7, r4, r5" is followed by "jmpneg r7" and the true branch
    # falls through: the jump is taken on zero/false.
    #
    # This way round matters: the scratch area starts as zeros, so an unwritten
    # table means "everything allowed" and the game simply behaves normally. The
    # inverted version blocked every swallow, including Normal.
    import struct as _struct
    n = 40   # every StepAbilityKind value (max 32), with room to spare

    def build(allowed):
        t = bytearray(4 * n)          # all zero = all allowed
        for nm, v in M.ABILITY_KIND.items():
            if nm in allowed:
                continue              # received: leave at 0 (allowed)
            if 0 <= v < n:
                _struct.pack_into("<I", t, v * 4, 1)
        return bytes(t)

    # Base Kirby and the Robobot Armor get SEPARATE tables. They used to share
    # one, which meant being sent "Armor Mode: Fire" also let plain Kirby copy
    # Fire from an enemy. Armor modes should only affect the armor.
    #
    try:
        if ctx.ability_gate_on and M.ABILITY_GATE_ADDR is not None:
            await ctx.iface.write(M.ABILITY_GATE_ADDR,
                                  build(set(ctx.unlocked_abilities)))
        if ctx.armor_gate_on and getattr(M, "ARMOR_GATE_ADDR", None) is not None:
            await ctx.iface.write(M.ARMOR_GATE_ADDR,
                                  build(set(ctx.unlocked_armor)))
    except Exception:
        pass


async def grant_pending_cubes(ctx: KirbyRobobotContext, state=None):
    """Open boss doors based purely on the Code Cubes Archipelago has sent.

    Walkability is a SAVE FLAG, not a live check. Each stage has an 8-byte row:
    bytes 0-4 are cube state, byte 5 is "opened" (you can walk to it on the area
    map), byte 6 is "unlocked" (you can enter it), byte 7 is "cleared". The game
    only writes byte 5 during the short cutscene after you finish a stage, which
    is exactly why receiving cubes while sitting on the stage-select screen never
    opened anything, no matter how many arrived.

    So we set those two bytes ourselves the moment the Area's requirement is met.
    Nothing waits for a cutscene, and vanilla cubes are deliberately ignored: the
    count that matters is what AP gave you.

    We also open every non-boss stage in Areas you can reach, so stages can be
    played in any order. Boss stages stay shut until their cubes arrive, and EX
    stages aren't in this array at all so they keep their own gating.
    """
    if not M.stages_ready():
        return
    srows = (state or {}).get("stage_rows") or b""
    if not srows:
        try:
            base, ln = M.stage_array_span()
            srows = await ctx.iface.read(base, ln) or b""
        except Exception:
            return
    if not srows:
        return

    want_open = []          # (row_index, byte_offset)

    for area, idxs in M.STAGE_ARRAY_INDEX.items():
        boss_idx = M.BOSS_STAGE_INDEX.get(area)
        ex_idx = M.EX_STAGE_INDEX.get(area)

        # Normal stages only. The boss needs its cubes, and the EX stage keeps
        # vanilla's own unlock rules, so neither counts as "normal" here.
        if ctx.open_all_stages:
            for i in idxs:
                if i == boss_idx or i == ex_idx:
                    continue
                want_open.append(i)

        # Boss stage: only once AP has sent enough cubes for THIS Area.
        if boss_idx is None:
            continue
        need = C.AREA_CUBE_COUNTS_REQUIRED.get(f"Level{area}")
        have = ctx.area_cubes_owed.get(f"Level{area}", 0)
        if need is not None and have >= need:
            want_open.append(boss_idx)

    want = set(want_open)
    for area, idxs in M.STAGE_ARRAY_INDEX.items():
        boss_idx = M.BOSS_STAGE_INDEX.get(area)
        for i in idxs:
            row = i * M.STAGE_ROW_SIZE
            # Boss doors are the one thing we actively CLOSE as well as open. A
            # save that already had them open (from playing before, or from an
            # earlier build of this client) would otherwise let you walk
            # straight past the gate forever, since we'd see the byte was
            # already set and leave it alone.
            enforce_shut = (i == boss_idx and i not in want)
            for b in (M.STAGE_OPENED_BYTE, M.STAGE_UNLOCKED_BYTE):
                pos = row + b
                if pos >= len(srows):
                    continue
                cur = srows[pos]
                if i in want and cur == 0:
                    val = b"\x01"
                elif enforce_shut and cur != 0:
                    val = b"\x00"
                else:
                    continue
                try:
                    await ctx.iface.write(M.STAGE_ARRAY_ADDR + pos, val)
                except Exception:
                    pass


async def _request_item(ctx: KirbyRobobotContext, kind: int,
                        sub_kind: int = 0) -> bool:
    """Hand one item to the game through its own pickup path.

    Writes the sub-kind first (it only matters for food, and must be in place
    before the request is seen), then the kind. The patch builds a real pickup
    record and runs OnCatch, then clears the request word, so a zero back is
    confirmation that the game took it rather than a guess.

    There's no in-level check here on purpose. The patch only acts while Kirby
    exists in a stage, and it leaves the request word untouched until then, so
    an item handed over on the world map simply waits and applies the moment a
    stage loads. Checking ourselves would only add the guesswork we're trying
    to avoid.
    """
    req = M.ITEM_REQUEST
    try:
        pending = struct.unpack("<I", await ctx.iface.read(req, 4))[0]
    except Exception:
        return False
    posted = getattr(ctx, "_item_posted", None)
    if posted is not None:
        # We're waiting on the one we already posted.
        if pending == 0:
            ctx._item_posted = None
            return True
        return False
    if pending != 0:
        return False                    # a request is mid-flight, wait
    try:
        await ctx.iface.write(M.ITEM_SUBKIND, struct.pack("<I", sub_kind))
        await ctx.iface.write(req, struct.pack("<I", kind))
        ctx._item_posted = kind
    except Exception:
        pass
    return False


async def grant_pending_items(ctx: KirbyRobobotContext, state=None):
    """Drain the consumable queue, one item per confirmed hand-off.

    Everything the player receives that Kirby physically picks up in game, a
    1UP, any food, an Energy Drink, a Maxim Tomato, an Invincible Candy, goes
    through here in the order it arrived. Each is handed over as the real item,
    so it comes with its own animation, jingle and effect.
    """
    queue = getattr(ctx, "item_queue", None)
    if not queue:
        return
    kind, sub = queue[0]
    if await _request_item(ctx, kind, sub):
        queue.pop(0)


async def resolve_hp_addr(ctx: KirbyRobobotContext):
    """Find Kirby's live HP word.

    Confirmed by scanning a running game: HP sits at the start of a trio of
    consecutive words, current / max / the value the bar draws. At full health
    all three read 450 (health is fixed point, so 45.0 HP is stored as 450).
    When Kirby leaves a stage the word reads 0x7FBFFFFF, so an out-of-level read
    is easy to reject rather than mistake for health.

    The test deliberately checks MAX, not just current. An enemy was found with
    the same trio shape but a max of 200, and a current-value-only test happily
    locked onto it, which is how heals ended up going somewhere harmless.
    Kirby's max is 45 (450), so anything below 300 is somebody else.

    Order: the pointer chain, then the last address that worked, then a bounded
    sweep near it (only when a heal is actually waiting, since it costs reads).
    """
    if not M.hp_ready():
        return None

    async def trio(a):
        try:
            raw = await ctx.iface.read(a, 8)
            if not raw or len(raw) < 8:
                return None
            return struct.unpack("<2I", raw[:8])
        except Exception:
            return None

    async def is_kirby_hp(a):
        t = await trio(a)
        if t is None:
            return False
        cur, mx = t
        if cur == 0x7FBFFFFF or mx == 0x7FBFFFFF:
            return False              # not in a stage
        # Kirby's max is exactly 450 (45 health, fixed point x10). A looser
        # range let a 300-max object masquerade as Kirby, and everything
        # measured from that anchor was then wrong. Other creatures have health
        # bars, so "plausible" isn't good enough.
        if mx != M.KIRBY_MAX_HP:
            return False
        return 0 < cur <= mx

    addr = await _chase(ctx, M.HP_CHASE, M.HP_FIELD_OFF, base=M.HP_STATIC_BASE)
    if addr is not None and await is_kirby_hp(addr):
        ctx._hp_last_good = addr
        return addr

    # A known-good address from a real session. The Hero object is reallocated
    # per session so this won't stay correct forever, but it gives the sweep
    # below somewhere sensible to start when the chain can't be walked at all.
    last = getattr(ctx, "_hp_last_good", None) or M.HP_KNOWN_ADDR
    if last is not None:
        if await is_kirby_hp(last):
            return last
        # A short sweep runs every poll: the Hero object shifts a little between
        # rooms, and without this the client decides Kirby doesn't exist, which
        # silently stops heals and un-hides rare stickers. A wider one runs only
        # when a heal is actually waiting, since it costs a few hundred reads.
        span = 0x1000 if getattr(ctx, "_hp_want_rescan", False) else 0x100
        ctx._hp_want_rescan = False
        for delta in range(-span, span + 1, 4):
            if delta and await is_kirby_hp(last + delta):
                ctx._hp_last_good = last + delta
                return last + delta
        ctx._hp_last_good = None
    return None


async def handle_death_link(ctx: KirbyRobobotContext, state=None):
    """DeathLink, both ways.

    The HP pointer chain walks several heap hops and CANNOT be trusted blindly:
    during a room transition the Hero object is torn down and rebuilt, so the
    chain briefly resolves to unrelated memory. If that memory happens to read 0
    we would announce a death that never happened, which is why DeathLinks were
    firing on room changes and at seemingly random moments.

    So a death is only believed when we're actually in a level AND we have seen a
    believable HP value on this object first. A 0 that appears without ever having
    seen Kirby alive is treated as "the object isn't there", not "Kirby died"."""
    if not ctx.death_link_on:
        return
    if state is not None and not state.get("in_level"):
        # Outside a stage there's no Kirby to be dead. Reset so re-entering a
        # level doesn't immediately look like a death.
        ctx.was_dead = False
        ctx._hp_seen_alive = False
        return
    if not M.hp_ready():
        return
    addr = await resolve_hp_addr(ctx)
    if addr is None:
        ctx._hp_seen_alive = False
        return
    try:
        hp = struct.unpack("<I", await ctx.iface.read(addr, 4))[0]
    except Exception:
        ctx._hp_seen_alive = False
        return
    if hp > M.HP_MAX_PLAUSIBLE:
        ctx._hp_seen_alive = False
        return

    if ctx.death_owed:
        ctx.death_owed = False
        if hp > 0:
            try:
                await ctx.iface.write(addr, struct.pack("<I", 0))
                ctx.ignore_next_death = True
            except Exception:
                pass
        return

    if hp > 0:
        # A believable living value: from here a 0 means something real.
        ctx._hp_seen_alive = True
        ctx.was_dead = False
        return

    # hp == 0. Only a real death if we watched Kirby be alive on this object.
    if not getattr(ctx, "_hp_seen_alive", False):
        return
    if not ctx.was_dead:
        ctx.was_dead = True
        ctx._hp_seen_alive = False
        if ctx.ignore_next_death:
            ctx.ignore_next_death = False
        else:
            await ctx.send_death(death_text="Kirby ran out of health.")


async def grant_pending_stickers(ctx: KirbyRobobotContext, state):
    """Keep AP-granted stickers usable, and still let their in-game check fire.

    A sticker AP sends is yours to use. But the game only registers a sticker,
    and only sends its check, when it comes up as NEW on the sticker screen at
    the end of a stage, and "new" means its album slot is empty at that moment.
    So the slot has to read empty from the time a stage starts until that screen
    has had its say.

    That screen runs after the stage-clear checks and before you're returned to
    the area's stage select, which is a long way after Kirby stops existing. An
    earlier version stopped holding the slot clear a few seconds after it last
    saw Kirby, so by the time the stickers came up the slot had been put back to
    owned, the sticker showed as already-held rather than new, and no check went
    out. Holding is no longer tied to how recently Kirby was seen.

    So, per granted sticker:

      Resting: the slot reads owned, so the sticker is usable from the moment it
      arrives.

      Armed: the first time we see we're in a stage the slot is cleared, and it
      stays cleared. It doesn't matter whether Kirby is still around after that,
      which is what lets it survive the whole end-of-stage sequence.

      Earned: when the slot comes back set, the game awarded it on the sticker
      screen. That's the check, and the slot is left owned from then on.

    If a stage is left without the sticker being awarded, holding is released
    after a long idle stretch so the sticker goes back to being usable.

    Normal stickers work the same way, so finding one still counts even if AP
    already sent it.
    """
    if not ctx.stickers_granted:
        return
    off = M.SlotOffsets
    slot = M.SAVE_SLOTS[M.ACTIVE_SLOT]
    arr = state.get("sticker_arr") or b""
    if not arr:
        return

    # How long without any sign of being in a stage before we decide a sticker
    # wasn't collected and hand it back for use. This has to comfortably outlast
    # the stage-clear, results and sticker-screen sequence, so it's minutes.
    GIVE_UP_POLLS = 400
    in_stage = bool(state.get("in_level"))
    if in_stage:
        ctx._sticker_map_streak = 0
    else:
        ctx._sticker_map_streak += 1
    idle = ctx._sticker_map_streak

    # Only stickers of a kind the yaml turned into locations are managed here.
    # With a kind switched off it has no checks to earn, so there is no reason
    # to clear it out of the album: a sticker sent as plain filler should just
    # be yours to use, exactly as if you had found it.
    idx_to_loc = {}
    managed = set()
    for _n, d in _LOC_BY_ID.values():
        if d.sticker_index is None:
            continue
        if not _sticker_kind_enabled(ctx, d.category):
            continue
        idx_to_loc[d.sticker_index] = d.code_offset
        managed.add(d.sticker_index)

    # Stickers of a switched-off kind are simply put in the album and left
    # there, since nothing needs to be earned for them.
    for idx in sorted(ctx.stickers_granted - managed):
        if idx * 2 + 1 >= len(arr):
            continue
        if arr[idx*2:idx*2+2] != b"\x01\x01":
            try:
                await ctx.iface.write(slot + off.STICKER_ARRAY + idx * 2, b"\x01\x01")
            except Exception:
                pass

    newly_found = []
    for idx in sorted(ctx.stickers_granted & managed):
        if idx * 2 + 1 >= len(arr):
            continue
        loc = idx_to_loc.get(idx)
        checked = loc is not None and (
            loc in ctx.checked_locally or loc in ctx.checked_locations)
        entry = int.from_bytes(arr[idx*2:idx*2+2], "little")
        armed = idx in ctx.stickers_hidden

        # Armed slots are held empty, so one that reads set was set by the game:
        # the sticker came up new on the sticker screen and was awarded.
        if not checked and loc is not None and armed and entry != 0:
            newly_found.append(loc)
            ctx.checked_locally.add(loc)
            ctx.stickers_hidden.discard(idx)
            checked = True
            armed = False

        if checked:
            want = b"\x01\x01"            # earned: owned for good
        elif armed and idle < GIVE_UP_POLLS:
            want = b"\x00\x00"            # armed: keep the slot empty
        elif in_stage:
            want = b"\x00\x00"            # in a stage: clear it so it can be found
        else:
            want = b"\x01\x01"            # resting: owned and usable
            ctx.stickers_hidden.discard(idx)

        if arr[idx*2:idx*2+2] != want:
            try:
                await ctx.iface.write(slot + off.STICKER_ARRAY + idx * 2, want)
            except Exception:
                pass

        # Arm only once the slot has actually read back empty, so our own write
        # can never be mistaken for the game's award.
        if not checked and in_stage and entry == 0:
            ctx.stickers_hidden.add(idx)

    if newly_found:
        for loc in newly_found:
            nm = _LOC_BY_ID.get(loc, (None, None))[0]
            logger.info("Sticker check earned in game: %s", nm or loc)
        await ctx.send_msgs([{"cmd": "LocationChecks",
                              "locations": list(newly_found)}])


async def apply_item(ctx: KirbyRobobotContext, item_id: int):
    """Apply a received item.

    Robobot items split into three kinds:
      * Code Cubes -> must be written into the game, because the vanilla boss and
        EX gates read the game's own cube count. Written cubes are tracked so they
        never echo back as checks.
      * Copy abilities / armor -> permissions, enforced live (see the gate below).
    Nothing here ever writes a flag we then report as one of the player's checks."""
    entry = _ITEM_BY_ID.get(item_id)
    if not entry:
        return
    name, _data = entry

    # Per-Area Code Cube ("<Area Name> Code Cube"). Track a per-Area received
    # count; the boss firewall for that Area is gated on its own cubes.
    area_lv = C.AREA_CUBE_ITEM_TO_LEVEL.get(name)
    if area_lv is not None:
        ctx.area_cubes_owed[area_lv] = ctx.area_cubes_owed.get(area_lv, 0) + 1
        logger.info("Received a %s (%d for %s from Archipelago).",
                    name, ctx.area_cubes_owed[area_lv], C.area_name(area_lv))
        return

    # A received rare sticker item. We record it as granted, but do NOT write it
    # into the album yet. The poll loop shows it in the album only once its own
    # location check is complete; until then the album slot is kept clear so the
    # physical pickup in its level stays collectable (otherwise the game removes
    # the pickup and the check becomes impossible the Ultra Sword problem).
    rare_idx = _RARE_ITEM_TO_ALBUM.get(name)
    if rare_idx is not None:
        ctx.stickers_granted.add(rare_idx)
        return

    # Pool item names are "Ability: Ice"; the gate table (ABILITY_KIND) is keyed
    # by the bare name "Ice", so strip the prefix before recording the unlock.
    if name.startswith("Ability: "):
        bare = name[len("Ability: "):]
        if bare in C.COPY_ABILITIES:
            ctx.unlocked_abilities.add(bare)
        return
    if name in C.COPY_ABILITIES:          # tolerate a bare name too, just in case
        ctx.unlocked_abilities.add(name)
        return

    # Robobot Armor modes. The gate table that decides which modes the armor may
    # copy is keyed by the bare mode name, so record that. Without this the table
    # is built from an empty set and every mode reads locked, so scanning an
    # enemy in the armor gives nothing even after you've received the mode.
    if name.startswith("Armor Mode: "):
        ctx.unlocked_armor.add(name[len("Armor Mode: "):])
        return

    # Consumables are handed to the game as genuine pickups. We queue the item
    # kind (and, for food, its sub-kind) and the patch feeds it through the same
    # path as touching one, so each arrives with its real effect. They apply the
    # moment Kirby is in a stage, and wait in order if he isn't.
    if name == "1-Up":
        ctx.item_queue.append((M.ITEM_KIND_1UP, 0))
        return
    if name in C.FOOD_ITEMS:
        ctx.item_queue.append((M.ITEM_KIND_FOOD, C.food_sub_kind(name)))
        return
    if name == C.ENERGY_DRINK:
        ctx.item_queue.append((M.ITEM_KIND_ENERGY, 0))
        return
    if name == C.MAXIM_TOMATO:
        ctx.item_queue.append((M.ITEM_KIND_MAXIM, 0))
        return
    if name == C.INVINCIBLE_CANDY:
        ctx.item_queue.append((M.ITEM_KIND_CANDY, 0))
        return

    if not M.is_ready():
        return
    slot = M.SAVE_SLOTS[M.ACTIVE_SLOT]
    off = M.SlotOffsets



async def game_watcher(ctx: KirbyRobobotContext):
    """The main loop.

    Ordering matters here. Items received from the multiworld are recorded as
    soon as they arrive, *regardless* of what the game is doing the player may
    be on a menu, mid-cutscene, or not even booted yet. Anything that needs the
    game (writing cubes, dropping abilities) is queued and applied whenever the
    game is actually reachable. An earlier version applied items only while the
    save was readable, which is why nothing ever arrived."""
    while not ctx.exit_event.is_set():
        await asyncio.sleep(0.5)
        if not ctx.server or not ctx.slot:
            continue
        try:
            # 1) Record received items. This is pure bookkeeping and must happen
            #    even with no game connected, so nothing is ever missed.
            new_items = ctx.items_received[ctx.last_received_index:]
            for net_item in new_items:
                if getattr(net_item, "location", None) is not None \
                        and getattr(net_item, "player", None) == ctx.slot:
                    ctx.received_locations.add(net_item.location)
                await apply_item(ctx, net_item.item)
                ctx.last_received_index += 1

            # 2) Everything below needs the game.
            if not await _ensure_game(ctx):
                continue
            if not M.is_ready():
                pass
                continue

            # The boss-gate table must be written even if the save isn't
            # readable yet: until we write it, that scratch word holds whatever
            # was there before, and the patched gate compares against it.
            await grant_pending_cubes(ctx)

            state = await read_save_state(ctx)
            if state is None:
                ctx._poll_count += 1
                continue

            # 3) First successful read: say so, and warn if this looks like a
            #    save with pre-existing vanilla progress (which will dump a lot
            #    of checks at once usually a sign of not starting fresh).
            # 4) Hand over whatever the multiworld has given us. This happens
            #    BEFORE we scan for checks: a gift we haven't applied yet must
            #    never be mistaken for something the player found.
            await grant_pending_stickers(ctx, state)
            await grant_pending_items(ctx, state)
            await handle_death_link(ctx, state)
            await write_ability_gate(ctx)

            # 5) Now look for anything the player actually collected.
            await _process_collectibles(ctx, state)

            # 7) Goal.
            await watch_save_diff(ctx)
            await watch_armor_copy(ctx)
            if not ctx.goal_sent and _goal_satisfied(ctx, state):
                ctx.goal_sent = True
                await ctx.send_msgs([{"cmd": "StatusUpdate",
                                      "status": ClientStatus.CLIENT_GOAL}])
        except ConnectionLost:
            ctx.game_connected = False
            logger.info("Lost connection to the game; will retry.")
        except Exception as e:
            # Don't swallow this. A quiet exception here used to mean the client
            # sat there doing nothing while looking perfectly connected, which is
            # a horrible thing to debug. Say it once, loudly, then carry on.
            if not ctx._error_reported:
                ctx._error_reported = True
                logger.error("Something went wrong while reading the game: %r", e)
                logger.exception("Details:")
                logger.error("Checks may not send. Please report this.")


async def _process_collectibles(ctx: KirbyRobobotContext, state):
    """Send checks for newly-collected cubes/stickers, then remove them from the
    game.

    This is the heart of the randomizer. In vanilla, picking up a Code Cube
    gives you a Code Cube. Here it must only *send the check* the actual item
    comes from the multiworld. So once we've seen a pickup, we clear the flag the
    game just set. The player's cube count then reflects only what AP gave them,
    which is what makes the vanilla boss gate meaningful.

    A cube we wrote ourselves (from a received item) is never touched, and never
    reported as a check.
    """
    off = M.SlotOffsets
    to_send = []

    # --- Code Cubes ---
    rows = state.get("cube_rows") or b""
    if rows:
        for _n, d in _LOC_BY_ID.values():
            if d.category != "cube" or d.stage_index is None:
                continue
            if d.code_offset in ctx.checked_locations:
                continue          # the server already has this one
            if not cube_collected(rows, d.stage_index, d.slot_index):
                continue
            # Nothing writes cubes any more (the boss gate reads a separate
            # table), so a collected cube is always a real one the player found.
            if d.code_offset not in ctx.checked_locally:
                to_send.append(d.code_offset)
                ctx.checked_locally.add(d.code_offset)

    # --- Per-stage clears ---
    # byte 7 of each stage's 8-byte row in the save's stage array. Confirmed
    # against a live save, so a set byte means the player really cleared it.
    srows = state.get("stage_rows") or b""
    if srows:
        for _n, d in _LOC_BY_ID.values():
            if d.category != "stage_clear" or d.area is None or d.stage_no is None:
                continue
            try:
                idx = M.STAGE_ARRAY_INDEX[d.area][d.stage_no - 1]
            except (KeyError, IndexError):
                continue
            # NOTE: deliberately not called `off`. That name is the SlotOffsets
            # alias used further down for the sticker album, and shadowing it
            # here broke every check after this block.
            row_off = idx * M.STAGE_ROW_SIZE + M.STAGE_CLEAR_BYTE
            if row_off >= len(srows):
                continue
            if srows[row_off] == 0:
                continue
            if (d.code_offset not in ctx.checked_locally
                    and d.code_offset not in ctx.checked_locations):
                to_send.append(d.code_offset)
                ctx.checked_locally.add(d.code_offset)

    # --- Stickers (rare and normal) ---
    # An album entry turning on means the player physically picked that sticker
    # up, which is the check. The sticker itself is NOT theirs to keep: the only
    # stickers you can use are the ones Archipelago sent you, so a found one is
    # cleared back out of the album right after its check is sent.
    #
    # Stickers AP granted are skipped here entirely. Their entry is set by us, so
    # "turned on" says nothing about finding the placement, and clearing them
    # would take away something you were given. grant_pending_stickers owns those
    # slots: it hides them inside levels so the real pickup still spawns, and
    # notices when the game writes the entry back.
    sarr = state.get("sticker_arr") or b""
    if sarr:
        sbase = M.SAVE_SLOTS[M.ACTIVE_SLOT] + off.STICKER_ARRAY
        for _n, d in _LOC_BY_ID.values():
            if d.category not in ("rare", "sticker") or d.sticker_index is None:
                continue
            # A kind the yaml switched off has no checks, so leave it alone
            # entirely. This block used to run over every sticker location in
            # the table regardless, which meant normal stickers were cleared
            # back out of the album even with Stickersanity off.
            if not _sticker_kind_enabled(ctx, d.category):
                continue
            si = d.sticker_index
            if si in ctx.stickers_granted:
                continue                  # ours: handled elsewhere
            if si * 2 + 1 >= len(sarr):
                continue
            if int.from_bytes(sarr[si*2:si*2+2], "little") == 0:
                continue

            if (d.code_offset not in ctx.checked_locally
                    and d.code_offset not in ctx.checked_locations):
                to_send.append(d.code_offset)
                ctx.checked_locally.add(d.code_offset)

            # Found, not granted: you earned the check, not the sticker.
            try:
                await ctx.iface.write(sbase + si * 2, b"\x00\x00")
            except Exception:
                pass

    if to_send:
        new = [l for l in to_send if l not in ctx.checked_locations]
        if new:
            await ctx.send_msgs([{"cmd": "LocationChecks", "locations": new}])


def _bosses_defeated(state) -> int:
    """How many Story Mode Area bosses have been beaten.

    Read straight from the stage array, counting the clear byte on each Area's
    boss row. Access Ark's boss is not the last row of its Area, so the row
    numbers come from BOSS_STAGE_INDEX rather than being counted from the end.
    """
    rows = state.get("stage_rows") or b""
    if not rows or not M.stages_ready():
        return 0
    beaten = 0
    for area in sorted(M.BOSS_STAGE_INDEX):
        idx = M.BOSS_STAGE_INDEX[area]
        pos = idx * M.STAGE_ROW_SIZE + M.STAGE_CLEAR_BYTE
        if pos < len(rows) and rows[pos] != 0:
            beaten += 1
    return beaten


def _goal_satisfied(ctx: KirbyRobobotContext, state) -> bool:
    """Has the player finished what their goal asked for?

    Two goals, and they finish at different moments.

    story_boss_count is done as soon as the requested number of Area bosses have
    been beaten, which is counted from the boss rows of the stage array. This
    used to be ignored entirely: whatever the yaml asked for, the client only
    ever watched for the end of the game, so a one boss goal still made you play
    all the way to Star Dream.

    story_star_dream is done when Star Dream goes down. That writes nothing to
    the stage rows, which is why watching them never worked however many rows
    were tried, but it does set several flags in the save file. Those all start
    at zero and only turn on at the kill, so checking them cannot fire early.
    """
    if ctx.goal_is_boss_count:
        want = max(1, int(ctx.story_boss_count or 1))
        beaten = _bosses_defeated(state)
        if beaten != getattr(ctx, "_bosses_seen", None):
            ctx._bosses_seen = beaten
            logger.info("Story bosses defeated: %d of %d needed.", beaten, want)
        if beaten >= want:
            return True

    flags = state.get("clear_flags") or b""
    if flags:
        for off in M.GAME_CLEARED_FLAGS:
            i = off - M.GAME_CLEARED_FIRST
            if 0 <= i < len(flags) and flags[i] != 0:
                logger.info("Goal reached: save flag +0x%04X is set.", off)
                return True
    return bool(state.get("game_cleared"))


def _patch_from_apkr(patch_file: str):
    """Build the playable LayeredFS folder from the player's own ROM.

    The ROM path is asked for ONCE (a file picker) and saved into host.yaml, so
    every later patch is fully automatic. All problems are reported loudly in the
    client window a silent failure here is worse than a noisy one."""
    import json
    import os
    import tempfile
    import zipfile

    def say(msg, *a):
        # Goes to the client window AND the console.
        logger.info(msg, *a)

    def fail(msg, *a):
        logger.error("PATCHING FAILED: " + msg, *a)

    try:
        import settings
        from . import Rom

        say("Reading patch: %s", os.path.basename(patch_file))
        with zipfile.ZipFile(patch_file) as z:
            plan = json.loads(z.read("plan.json"))

        # Resolve the ROM. Touching rom_file opens a file picker the first time
        # and saves the answer to host.yaml.
        say("Locating your Kirby: Planet Robobot ROM...")
        grp = settings.get_settings()["kirby_robobot_options"]
        rom_path = str(grp.rom_file)
        if not rom_path or not os.path.exists(rom_path):
            fail("ROM not found at %r. Fix `rom_file` under "
                 "`kirby_robobot_options` in host.yaml.", rom_path)
            return
        say("  ROM: %s", rom_path)

        out_dir = os.path.dirname(os.path.abspath(patch_file))
        plan_path = os.path.join(tempfile.mkdtemp(), "plan.json")
        with open(plan_path, "w") as f:
            json.dump(plan, f)

        say("Extracting and patching (this takes ~20-60s, please wait)...")
        folder = Rom.patch_rom(plan_path, rom_path, out_dir)

        say("=" * 60)
        say("DONE. Your patched game is here:")
        say("  %s", folder)
        say("Copy the 00040000001BB800 folder into Azahar's load/mods/ folder.")
        say("(Set `mod_path` in host.yaml to have this copied automatically.)")
        say("=" * 60)

    except Exception as e:
        fail("%s", e)
        logger.exception("Full details:")


def launch(*args_list):
    async def main():
        Utils.init_logging("KirbyRobobotClient")
        parser = get_base_parser()
        parser.add_argument("patch_file", default="", type=str, nargs="?",
                            help="Path to a .apkr patch file.")
        args = parser.parse_args(args_list if args_list else None)

        if args.patch_file and args.patch_file.endswith(".apkr"):
            try:
                _patch_from_apkr(args.patch_file)
            except Exception as e:
                logger.exception("Failed to build patched ROM: %s", e)

        ctx = KirbyRobobotContext(args.connect, args.password)
        ctx.server_task = asyncio.create_task(server_loop(ctx), name="ServerLoop")
        if gui_enabled:
            ctx.run_gui()
        ctx.run_cli()

        watcher = asyncio.create_task(game_watcher(ctx), name="GameWatcher")
        await ctx.exit_event.wait()
        watcher.cancel()
        await ctx.shutdown()

    import colorama
    colorama.init()
    asyncio.run(main())
    colorama.deinit()


if __name__ == "__main__":
    launch()
