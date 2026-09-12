"""
Rom.py One-click ROM handling for Kirby: Planet Robobot.

Flow (all automatic once the player opens the .apkr):
  1. Player opens the .apkr from the Archipelago Launcher.
  2. First time only: a file picker asks for their own decrypted NA .cci/.3ds.
     The answer is saved in host.yaml, so it never asks again.
  3. This module extracts romfs with ctrtool, applies the AP patch, and writes a
     LayeredFS folder `00040000001BB800` (plus a .zip) next to the patch.
  4. If `mod_path` is set in host.yaml, the folder is also copied straight into
     the emulator/SD mods directory, so there's nothing left to do.

Nothing here redistributes game data; it only reads the player's own ROM.
"""
import os
import shutil
import subprocess
import zipfile
from typing import List, Optional, Union

import settings

from . import rom_build

TITLE_ID_NA = "0004000000183600"   # fallback; we read the real one from the ROM


class KirbyRobobotSettings(settings.Group):
    class RomFile(settings.UserFilePath):
        """Your own decrypted North American Kirby: Planet Robobot ROM.
        .cci and .3ds are the same thing; only the extension differs."""
        description = "Kirby: Planet Robobot ROM (.cci/.3ds)"
        copy_to = None
        md5s = []

    class CtrtoolPath(settings.UserFilePath):
        """Path to the ctrtool executable, used to unpack your ROM.
        Only needed if ctrtool isn't on your PATH.
        Get it from https://github.com/3DSGuy/Project_CTR/releases"""
        description = "ctrtool executable"
        copy_to = None

    rom_file: RomFile = RomFile("Kirby - Planet Robobot (USA).cci")
    # Plain strings so they never trigger a file prompt on their own, and so an
    # older host.yaml that has `ctrtool_path: null` still loads cleanly.
    ctrtool_path: Optional[str] = ""
    # If set, the finished LayeredFS folder is copied here automatically, e.g.
    # "<Azahar folder>/load/mods" or "<SD card>/luma/titles".
    mod_path: Optional[str] = ""
    # A zip of the LayeredFS folder is only useful if you're moving it onto a
    # real 3DS's SD card. On an emulator it's just clutter, so it's off unless
    # you ask for it.
    make_zip: bool = False


def find_ctrtool() -> Optional[str]:
    """Locate ctrtool: host.yaml setting -> PATH -> bundled in tools/."""
    try:
        configured = str(settings.get_settings()["kirby_robobot_options"].ctrtool_path or "")
    except Exception:
        configured = ""
    if configured and os.path.exists(configured):
        return configured

    on_path = shutil.which("ctrtool") or shutil.which("ctrtool.exe")
    if on_path:
        return on_path

    here = os.path.dirname(os.path.abspath(__file__))
    for name in ("ctrtool.exe", "ctrtool"):
        p = os.path.join(here, "tools", name)
        if os.path.exists(p):
            return p
    return None


def extract_romfs(rom_path: str, work_dir: str) -> str:
    """Unpack romfs from a decrypted .cci/.3ds. Returns the romfs dir.

    Uses the bundled pure-Python extractor (no external tools needed). If that
    somehow can't handle a particular dump, and ctrtool is available, it's tried
    as a fallback.
    """
    romfs_dir = os.path.join(work_dir, "romfs")
    os.makedirs(romfs_dir, exist_ok=True)

    # 1) Built-in extractor the normal path, nothing to install.
    try:
        from .tools import ctr
    except Exception:
        import importlib.util
        _p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools", "ctr.py")
        _spec = importlib.util.spec_from_file_location("kpr_ctr", _p)
        ctr = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(ctr)

    try:
        ctr.extract_romfs(rom_path, romfs_dir)
        if os.path.isdir(os.path.join(romfs_dir, "map")):
            return romfs_dir
        # Extracted, but not the layout we expect fall through to ctrtool.
    except ctr.NotDecryptedError:
        # No point trying ctrtool on an encrypted ROM; surface the clear message.
        raise
    except Exception:
        pass  # try ctrtool as a fallback

    # 2) Optional ctrtool fallback.
    ctrtool = find_ctrtool()
    if ctrtool:
        for cmd in ([ctrtool, f"--romfsdir={romfs_dir}", rom_path],
                    [ctrtool, "-p", "-n", "0", f"--romfsdir={romfs_dir}", rom_path]):
            try:
                subprocess.run(cmd, capture_output=True, text=True)
            except OSError:
                continue
            if os.path.isdir(os.path.join(romfs_dir, "map")):
                return romfs_dir

    raise RuntimeError(
        "Could not extract romfs from your ROM.\n"
        "  * Make sure it's DECRYPTED (an encrypted dump won't work).\n"
        "  * Make sure it's the ROM itself (.cci/.3ds), not an installed CIA.")


def _ctr():
    """The bundled pure-python 3DS container reader."""
    try:
        from .tools import ctr
        return ctr
    except Exception:
        import importlib.util
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools", "ctr.py")
        spec = importlib.util.spec_from_file_location("kpr_ctr", p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod


def patch_rom(plan_path: str, rom_path: str, out_dir: str,
              enabled_bridges=None) -> str:
    """Extract -> patch -> LayeredFS folder (+ zip). Returns the folder path."""
    work = os.path.join(out_dir, "_kpr_work")
    if os.path.isdir(work):
        shutil.rmtree(work, ignore_errors=True)
    os.makedirs(work, exist_ok=True)

    try:
        romfs = extract_romfs(rom_path, work)

        # Read the Title ID from the ROM itself, so the LayeredFS folder is named
        # correctly for whatever region/dump the player actually has.
        tid = None
        try:
            tid = _ctr().read_title_id(rom_path)
        except Exception:
            pass

        layered = rom_build.build_layeredfs(plan_path, romfs, out_dir,
                                            title_id=tid)

        # A zip is only handy for copying onto a real 3DS. Skip it otherwise.
        try:
            want_zip = bool(settings.get_settings()["kirby_robobot_options"].make_zip)
        except Exception:
            want_zip = False
        if want_zip:
            zip_path = os.path.join(out_dir, os.path.basename(layered) + ".zip")
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
                for root, _dirs, files in os.walk(layered):
                    for f in files:
                        full = os.path.join(root, f)
                        z.write(full, os.path.relpath(full, out_dir))

        # Optionally install straight into the emulator / SD mods folder.
        try:
            mod_path = str(settings.get_settings()["kirby_robobot_options"].mod_path or "")
        except Exception:
            mod_path = ""
        if mod_path and os.path.isdir(mod_path):
            dest = os.path.join(mod_path, os.path.basename(layered))
            if os.path.isdir(dest):
                shutil.rmtree(dest, ignore_errors=True)
            shutil.copytree(layered, dest)
        return layered
    finally:
        shutil.rmtree(work, ignore_errors=True)
