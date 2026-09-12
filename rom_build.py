"""
rom_build.py Build the LayeredFS folder the emulator loads.

WHAT LAYEREDFS ACTUALLY WANTS

LayeredFS overlays *individual files* on top of the game's own romfs. A file you
put in the mod folder replaces the game's copy; everything you don't put there is
read from the game as normal. So the mod folder should contain **only the files
we changed** nothing else.

We were shipping the player's entire `map/` and `mint/` trees: hundreds of
unmodified files, a couple of hundred megabytes, in order to change three of
them. That's not just wasteful, it's a plausible reason nothing was loading at
all and if any part of that copy went wrong, the three files that mattered were
buried somewhere in the middle of it.

So now we ship exactly what we modify:

    romfs/mint/LvMap.bin.cmp             the Code Cube boss gate
    romfs/mint/StepHero.bin.cmp          the copy-ability gate (only when enabled)
    romfs/msg/US_English/TitleMenu.msbt  a visible "yes, the mod loaded" marker

Nothing else needs to be there, because nothing else changes: all the
randomizer's real work happens live in the client, over the memory pipe.
"""
import json
import os
import shutil
from typing import List

TITLE_ID_NA = "0004000000183600"   # fallback; we read the real one from the ROM


def _tools_dir() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools")


def build_layeredfs(plan_path: str, romfs_dir: str, out_dir: str,
                    which_bridges: List[str] = None,
                    title_id: str = None) -> str:
    """Write the LayeredFS title folder. Returns its path.

    title_id : the Title ID of the player's own ROM. Getting this wrong means the
               emulator quietly ignores the whole mod it looks in a folder named
               for a different game, finds nothing, and says nothing about it.
    """
    tid = title_id or TITLE_ID_NA
    title_root = os.path.join(out_dir, tid)
    romfs_out = os.path.join(title_root, "romfs")
    if os.path.isdir(title_root):
        shutil.rmtree(title_root, ignore_errors=True)
    os.makedirs(romfs_out, exist_ok=True)

    try:
        with open(plan_path) as f:
            plan = json.load(f)
    except Exception:
        plan = {}
    options = plan.get("options", {}) or {}

    placed = []

    def place(src_name: str, rel_dest: str, src_subdir: str = "tools") -> bool:
        # Read the bundled file through the package loader, NOT the filesystem.
        # An .apworld is a zip: os.path.exists() on a file inside it is False and
        # shutil.copy can't reach it, so a plain file copy silently fails and you
        # get an empty mod folder. pkgutil.get_data goes through the zip importer,
        # so it works whether the apworld is a folder or a zip.
        rel = src_subdir + "/" + src_name
        data = None
        # 1) The normal path: read through the package loader (works from a zip).
        try:
            import pkgutil
            data = pkgutil.get_data(__package__, rel)
        except Exception:
            data = None
        # 2) Ask this module's own loader directly (also zip-safe), in case the
        #    package name didn't resolve.
        if data is None:
            try:
                loader = globals().get("__loader__")
                if loader is not None and hasattr(loader, "get_data"):
                    base = os.path.dirname(__file__)
                    data = loader.get_data(os.path.join(base, rel))
            except Exception:
                data = None
        # 3) Fall back to a real file (running from an unpacked folder on disk).
        if data is None:
            src = os.path.join(os.path.dirname(__file__), src_subdir, src_name)
            if os.path.exists(src):
                with open(src, "rb") as fh:
                    data = fh.read()
        if not data:
            return False
        dest = os.path.join(romfs_out, rel_dest)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as fh:
            fh.write(data)
        placed.append(rel_dest.replace(os.sep, "/"))
        return True

    # 1) Boss gate: the patched IsBossStageAvailable compares each Area's cube
    #    requirement against a per-Area count the client keeps at CUBE_TABLE_ADDR,
    #    instead of the cubes physically collected. Writing cubes into the save
    #    was tried instead and was wrong: it greyed out cubes, destroyed their
    #    checks, inflated the counter, and still didn't open the gate.
    # 1) Boss gates are NOT patched any more.
    #
    #    Walkability to a boss stage is a save flag (byte 5 of that stage's row),
    #    which the game only writes during the cutscene after you clear a stage.
    #    Patching IsBossStageAvailable therefore did nothing useful: the door
    #    stayed shut however many cubes arrived, because nothing re-ran the check.
    #    The client now sets that flag directly once an Area's AP cube count is
    #    met, so doors open immediately, even from the stage-select screen.

    # (old note kept for context)
    #
    #    The old LvMap patch replaced the player's cube count with a single
    #    number the client wrote to a scratch word. Once Code Cubes became
    #    per-Area items nothing wrote that word any more, so the gate was reading
    #    zero: received cubes didn't count, and cubes you physically collected
    #    stopped counting too, so no firewall opened at all.
    #
    #    Instead the client writes received cubes straight into the game's own
    #    per-Area cube storage, so vanilla's gate logic runs untouched and each
    #    Area's boss counts exactly the cubes it should.

    # 2) A marker you can see immediately: the file-select "Back" button reads
    #    "AP:D". If it still says "Back", the mod isn't loading and nothing else
    #    here will work either which is worth knowing before you play for an
    #    hour wondering why the gates behave normally.
    place("TitleMenu_indicator.msbt",
          os.path.join("msg", "US_English", "TitleMenu.msbt"))

    # 3) The StepHero patch. ALWAYS placed, because it carries the heal hook (the
    #    client asks the game to heal so the health bar refreshes immediately),
    #    not just the copy-ability gates. Which variant depends on the toggles:
    #      neither gate on: heal hook only
    #      ability only   : heal + base copy gates
    #      armor involved : heal + base copy gates + armor copy gates
    #
    #    There is also a "log" flavour of each variant. It writes the kind of
    #    every item Kirby picks up to a scratch word, which is how we find out
    #    which number the Invincible Candy is. Harmless to ship: it's a single
    #    store per pickup and changes nothing the game does.
    ag = options.get("ability_gating")
    mg = options.get("armor_gating")
    # The "candy" flavour carries everything the log flavour did, plus a copy of
    # the game's own Invincible Candy handler that the client can trigger. That
    # handler turned out to need only Kirby himself, not the pickup struct, so a
    # granted candy runs the real thing: protection, music and palette included.
    # StepHero variant. The "items" flavour lets the client hand Kirby an item
    # by writing its kind to a scratch word.
    #
    # It does this the way the game itself does: build a Scn.Step.Item.GetInfo
    # on the stack, set its kind, and call ItemCollReact.OnCatch. The game's own
    # TryToUseStockItem does exactly this to hand over a stocked item, so it is a
    # supported path rather than something bolted on. Earlier attempts copied
    # individual handler bodies out of OnCatch instead, which crashed; thanks to
    # firubii for pointing out that OnCatch can simply be called.
    ag = options.get("ability_gating")
    mg = options.get("armor_gating")
    if mg:
        variant = "StepHero_items_ability_armor.bin.cmp"
    elif ag:
        variant = "StepHero_items_ability_only.bin.cmp"
    else:
        variant = "StepHero_items_heal_only.bin.cmp"
    place(variant, os.path.join("mint", "StepHero.bin.cmp"))

    # 3b) Boss gate and the road to it. Two separate things had to change.
    #
    #     The gate: the world map opens a boss road on its own as soon as you
    #     have physically collected enough Code Cubes, through
    #     Scn.LvMap.Utility.IsBossStageAvailable, which ignores Archipelago. That
    #     check now returns the boss stage's own "opened" flag instead of
    #     counting cubes, and the client sets that flag from the cubes AP has
    #     sent, so the security wall follows Archipelago and never the cubes you
    #     happened to pick up.
    #
    #     The road: Scn.LvMap.Ground.Field.Road decided the boss road's starting
    #     state from two conditions, that the stage before it is cleared AND that
    #     the boss is opened. The first is pure vanilla stage-order progression,
    #     and it left the road shut even with the gate open and the cubes in
    #     hand, so you had to go beat the preceding stage to walk over. That
    #     condition is forced true, leaving the boss's opened flag as the only
    #     thing that matters. As a backstop, the road's closed state also runs
    #     its opened state's body.
    place("LvMap_bossgate.bin.cmp", os.path.join("mint", "LvMap.bin.cmp"))

    # 4) Kirby's body color (cosmetic). 'pink' is vanilla and ships nothing.
    #    Each other color is a single native-format texture bundled under
    #    data/colors/<name>.bch.cmp, dropped at the game's Kirby base texture.
    color = (options.get("kirby_color") or "pink")
    if color and color != "pink":
        place(color + ".bch.cmp",
              os.path.join("gfx", "Common", "Hero", "Kirby", "Base", "Pink.bch.cmp"),
              src_subdir="data/colors")

    with open(os.path.join(title_root, "ap_seed.txt"), "w") as f:
        f.write(f"seed: {plan.get('seed', '')}\n")
        f.write(f"player: {plan.get('player', '')}\n")
        f.write("files replaced:\n")
        for p in placed:
            f.write(f"  romfs/{p}\n")

    return title_root
