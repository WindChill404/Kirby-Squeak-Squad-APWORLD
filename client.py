"""Kirby: Squeak Squad - Archipelago client (registers as a launcher button).

Bridges the BizHawk connector Lua to the AP server via files in %TEMP%:
    kss_checks.txt (Lua -> here) location BIT INDEX per line
    kss_items.txt  (here -> Lua) item NAME per line
    kss_goal.txt   (Lua -> here) "1" at goal
"""
import os
import asyncio
import tempfile

import Utils
from NetUtils import ClientStatus
from CommonClient import (
    CommonContext, server_loop, gui_enabled, ClientCommandProcessor,
    get_base_parser, logger,
)

GAME_NAME = "Kirby Squeak Squad"

# Build a local item-id -> name map from the apworld's own table. Received items
# are always THIS game's items, so this resolves every name without relying on
# AP's cross-game datapackage lookup (which fails when your item is found in
# another player's world).
_ID_TO_NAME = {}
try:
    from .items import item_name_to_id as _M
    _ID_TO_NAME = {v: k for k, v in _M.items()}
except Exception:
    try:
        from worlds.kirby_squeak_squad.items import item_name_to_id as _M
        _ID_TO_NAME = {v: k for k, v in _M.items()}
    except Exception:
        _ID_TO_NAME = {}
LOCATION_BASE_ID = 5_000_100
STAGECLEAR_BASE_ID = 5_000_300
ACQUIRED_BASE_ID = 5_000_400
STAGECLEAR_VBASE = 200
ACQUIRED_VBASE = 400
CHEST_LOC_LO, CHEST_LOC_HI = 5_000_100, 5_000_219   # chest locations
DAROACH_LOC = 5_000_356                              # Ice Island boss stage clear

TEMP = os.environ.get("TEMP") or tempfile.gettempdir()
CHECKS_FILE = os.path.join(TEMP, "kss_checks.txt")
ITEMS_FILE  = os.path.join(TEMP, "kss_items.txt")
GOAL_FILE   = os.path.join(TEMP, "kss_goal.txt")
DEATH_OUT_FILE = os.path.join(TEMP, "kss_death_out.txt")  # connector -> here: Kirby died (send)
DEATH_IN_FILE  = os.path.join(TEMP, "kss_death_in.txt")   # here -> connector: remote death (receive)
COLOR_FILE     = os.path.join(TEMP, "kss_color.txt")      # here -> connector: starting color index


class KSSCommandProcessor(ClientCommandProcessor):
    def _cmd_kss(self):
        """Show the bridge file paths."""
        logger.info(f"checks: {CHECKS_FILE}")
        logger.info(f"items:  {ITEMS_FILE}")
        logger.info(f"goal:   {GOAL_FILE}")

    def _cmd_received(self):
        """List the collectibles you've received from Archipelago so far."""
        from collections import Counter
        ctx = self.ctx
        if not getattr(ctx, "items_received", None):
            logger.info("No items received yet.")
            return
        counts = Counter(ctx._item_name(i) for i in ctx.items_received)
        logger.info(f"Received {len(ctx.items_received)} item(s):")
        for nm in sorted(counts):
            c = counts[nm]
            logger.info(f"  {nm}" + (f" x{c}" if c > 1 else ""))

    def _cmd_chests(self):
        """Show how many chests you've collected (and goal progress)."""
        ctx = self.ctx
        checked = getattr(ctx, "checked_locations", set()) or set()
        n_chests = sum(1 for loc in checked if CHEST_LOC_LO <= loc <= CHEST_LOC_HI)
        logger.info(f"Chests collected: {n_chests} / 119")
        if ctx.goal_mode == 1:
            daroach = DAROACH_LOC in checked
            logger.info(f"Goal (chests_and_daroach): need {ctx.goal_count} chests + Daroach.")
            logger.info(f"  progress: {min(n_chests, ctx.goal_count)}/{ctx.goal_count} chests, "
                        f"Daroach {'beaten' if daroach else 'not yet'}")
        else:
            logger.info("Goal is beat_game; chest count above is informational.")


class KSSContext(CommonContext):
    game = GAME_NAME
    command_processor = KSSCommandProcessor
    items_handling = 0b111

    def __init__(self, server_address, password):
        super().__init__(server_address, password)
        self._checks_sent = set()
        self._items_written = 0
        self._goal_done = False
        self.goal_mode = 0          # 0 beat_game, 1 chests_and_daroach
        self.goal_count = 70
        self.death_link_on = False
        self._last_death_out = None
        self._death_in_n = 0
        try:
            open(ITEMS_FILE, "w").close()
        except OSError:
            pass

    def on_deathlink(self, data):
        # a remote death arrived: tell the connector to kill Kirby (it applies the
        # in-place death-commit cluster so Kirby dies normally).
        try:
            self._death_in_n += 1
            with open(DEATH_IN_FILE, "w", encoding="utf-8") as f:
                f.write(str(self._death_in_n))
        except OSError:
            pass
        super().on_deathlink(data)

    async def server_auth(self, password_requested: bool = False):
        if password_requested and not self.password:
            await super().server_auth(password_requested)
        await self.get_username()
        await self.send_connect()

    def on_package(self, cmd, args):
        if cmd == "Connected":
            slot_data = args.get("slot_data") or {}
            self.goal_mode = int(slot_data.get("goal", 0))
            self.goal_count = int(slot_data.get("chest_goal_count", 70))
            # death link: enable the tag and prime the local-death cursor
            self.death_link_on = bool(slot_data.get("death_link", 0))
            if self.death_link_on:
                try:
                    with open(DEATH_OUT_FILE, "r", encoding="utf-8") as f:
                        self._last_death_out = f.read().strip()
                except OSError:
                    self._last_death_out = None
                Utils.async_start(self.update_death_link(True))
            if "start_color" in slot_data:
                try:
                    with open(COLOR_FILE, "w", encoding="utf-8") as f:
                        f.write(str(int(slot_data["start_color"])))
                except OSError:
                    pass
            if self.goal_mode == 1:
                logger.info(f"Goal: collect {self.goal_count} chests and beat Daroach "
                            f"(Ice Island boss).")
            else:
                logger.info("Goal: beat the game (claim the Strawberry Shortcake).")
            logger.info("Connected. Open chests in-game to send checks.")
        elif cmd == "ReceivedItems":
            self._write_items()

    def _item_name(self, item):
        # received items are always OUR game's items -> resolve from local table
        name = _ID_TO_NAME.get(item.item)
        if name is not None:
            return name
        try:
            return self.item_names.lookup_in_game(item.item, self.game)
        except Exception:
            return f"Unknown({item.item})"

    def _write_items(self):
        if not self.items_received:
            return
        try:
            with open(ITEMS_FILE, "a", encoding="utf-8") as f:
                for item in self.items_received[self._items_written:]:
                    f.write(self._item_name(item) + "\n")
            self._items_written = len(self.items_received)
        except OSError as e:
            logger.error(f"item write failed: {e}")

    def read_checks(self):
        # 0..119 chest; 200+(10*w+sub) stage clear; 400+ability_idx ability-acquired
        out = []
        try:
            with open(CHECKS_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    idx = int(line)
                    if idx in self._checks_sent:
                        continue
                    self._checks_sent.add(idx)
                    if idx >= ACQUIRED_VBASE:
                        out.append(ACQUIRED_BASE_ID + (idx - ACQUIRED_VBASE))
                    elif idx >= STAGECLEAR_VBASE:
                        out.append(STAGECLEAR_BASE_ID + (idx - STAGECLEAR_VBASE))
                    else:
                        out.append(LOCATION_BASE_ID + idx)
        except (OSError, ValueError):
            pass
        return out

    def goal_reached(self):
        if self._goal_done:
            return True
        if self.goal_mode == 1:
            # chests_and_daroach: N chest checks AND the Ice Island boss cleared
            checked = getattr(self, "checked_locations", set())
            n_chests = sum(1 for loc in checked
                           if CHEST_LOC_LO <= loc <= CHEST_LOC_HI)
            daroach = DAROACH_LOC in checked
            if n_chests >= self.goal_count and daroach:
                self._goal_done = True
            return self._goal_done
        # beat_game: cake opened (connector writes the goal file)
        try:
            with open(GOAL_FILE, "r", encoding="utf-8") as f:
                if f.read().strip() == "1":
                    self._goal_done = True
        except OSError:
            pass
        return self._goal_done


async def game_watcher(ctx: KSSContext):
    while not ctx.exit_event.is_set():
        await asyncio.sleep(1.0)
        if ctx.server and ctx.slot is not None:
            locs = ctx.read_checks()
            if locs:
                await ctx.send_msgs([{"cmd": "LocationChecks", "locations": locs}])
            ctx._write_items()
            # death link: forward a local death to the server
            if ctx.death_link_on:
                try:
                    with open(DEATH_OUT_FILE, "r", encoding="utf-8") as f:
                        v = f.read().strip()
                except OSError:
                    v = None
                if v and v != ctx._last_death_out:
                    ctx._last_death_out = v
                    await ctx.send_death(f"{ctx.player_names.get(ctx.slot, 'Kirby')} lost a life.")
            if ctx.goal_reached() and not ctx.finished_game:
                await ctx.send_msgs([{"cmd": "StatusUpdate",
                                      "status": ClientStatus.CLIENT_GOAL}])
                ctx.finished_game = True
                logger.info("Goal complete -> reported to server.")


def launch(*args):
    """Entry point used by the AP launcher button."""
    Utils.init_logging("KSSClient")

    async def _main():
        parser = get_base_parser()
        ns = parser.parse_args(args)
        ctx = KSSContext(ns.connect, ns.password)
        ctx.server_task = asyncio.create_task(server_loop(ctx), name="server loop")
        if gui_enabled:
            ctx.run_gui()
        ctx.run_cli()
        asyncio.create_task(game_watcher(ctx), name="game watcher")
        await ctx.exit_event.wait()
        await ctx.shutdown()

    import colorama
    colorama.init()
    asyncio.run(_main())
    colorama.deinit()
