"""
ctr.py: pure-Python extraction of romfs from a decrypted 3DS ROM.

This removes the ctrtool dependency entirely: the player only needs their own
decrypted .cci/.3ds, and everything else is done here.

Container chain:
    NCSD (.cci/.3ds)  ->  partition 0 is the game NCCH (.cxi)
    NCCH              ->  has a RomFS section (offset/size in the header)
    RomFS             ->  IVFC wrapper -> Level 3 -> a directory/file metadata
                          table + the raw file data

Only *decrypted* ROMs are supported (encrypted dumps would need console keys,
which we neither have nor want). We detect encryption and say so plainly.

References: the NCSD/NCCH/RomFS layouts are public, well-documented 3DS formats.
"""
import os
import struct
from typing import BinaryIO, Optional

MEDIA_UNIT = 0x200


class NotDecryptedError(Exception):
    pass


class BadRomError(Exception):
    pass


def _u16(b, o):
    return struct.unpack_from("<H", b, o)[0]


def _u32(b, o):
    return struct.unpack_from("<I", b, o)[0]


def _u64(b, o):
    return struct.unpack_from("<Q", b, o)[0]


def _find_ncch(f: BinaryIO) -> int:
    """Return the absolute offset of the game NCCH ('NCCH' magic at +0x100)."""
    f.seek(0)
    head = f.read(0x4000)
    if len(head) < 0x200:
        raise BadRomError("File is too small to be a 3DS ROM.")

    # Case 1: a raw NCCH/CXI (magic at 0x100).
    if head[0x100:0x104] == b"NCCH":
        return 0

    # Case 2: NCSD (.cci/.3ds), magic at 0x100, partition table at 0x120.
    if head[0x100:0x104] == b"NCSD":
        for i in range(8):
            off = _u32(head, 0x120 + i * 8) * MEDIA_UNIT
            size = _u32(head, 0x124 + i * 8) * MEDIA_UNIT
            if off and size:
                f.seek(off + 0x100)
                if f.read(4) == b"NCCH":
                    return off
        raise BadRomError("NCSD found, but no NCCH partition inside it.")

    raise BadRomError(
        "This doesn't look like a 3DS ROM (no NCSD/NCCH magic). Make sure it's "
        "a .cci/.3ds dump, not a CIA, and that it isn't compressed.")


def _romfs_region(f: BinaryIO, ncch_off: int):
    """(absolute romfs offset, size) from the NCCH header, with an encryption check."""
    f.seek(ncch_off)
    hdr = f.read(0x200)
    if len(hdr) < 0x200 or hdr[0x100:0x104] != b"NCCH":
        raise BadRomError("NCCH header is malformed.")

    # flags[7] bit 2 (0x04) = NoCrypto. If it isn't set, the ROM is encrypted.
    flags = hdr[0x188:0x190]
    no_crypto = bool(flags[7] & 0x04)
    if not no_crypto:
        raise NotDecryptedError(
            "This ROM is ENCRYPTED. A decrypted dump is required.\n"
            "  Re-dump with decryption enabled (e.g. GodMode9's 'Decrypted' "
            "option), then try again.")

    romfs_off = _u32(hdr, 0x1B0) * MEDIA_UNIT
    romfs_size = _u32(hdr, 0x1B4) * MEDIA_UNIT
    if not romfs_off or not romfs_size:
        raise BadRomError("This NCCH has no RomFS section.")
    return ncch_off + romfs_off, romfs_size


def _level3_offset(f: BinaryIO, romfs_off: int) -> int:
    """Walk the IVFC wrapper to the Level 3 (actual filesystem) offset."""
    f.seek(romfs_off)
    ivfc = f.read(0x60)
    if ivfc[:4] != b"IVFC":
        raise BadRomError("RomFS is missing its IVFC header.")
    master_size = _u32(ivfc, 0x08)
    lvl3_block = _u32(ivfc, 0x4C)          # log2 of the level-3 block size
    block = 1 << lvl3_block
    # Level 3 begins after the IVFC header (0x60) + master hash, aligned up to the
    # block size *relative to the start of the RomFS region*.
    rel = 0x60 + master_size
    rel = (rel + block - 1) & ~(block - 1)
    return romfs_off + rel


def read_title_id(rom_path: str) -> str:
    """The game's Title ID, straight from its NCCH header.

    This matters more than it looks. The emulator serves LayeredFS mods from a
    folder named after the Title ID, and if that name doesn't match the game
    you're running, the mod is silently ignored, with no error, nothing. We had
    exactly that: a hardcoded (wrong) id meant every ROM patch we made was being
    quietly skipped, which looked for all the world like the patches themselves
    were broken. So we read it from the player's own ROM instead of assuming.
    """
    with open(rom_path, "rb") as f:
        ncch = _find_ncch(f)
        f.seek(ncch + 0x108)          # Title ID, little-endian u64
        tid = struct.unpack("<Q", f.read(8))[0]
    return f"{tid:016X}"


def extract_romfs(rom_path: str, out_dir: str) -> str:
    """Extract the romfs of a decrypted .cci/.3ds into out_dir. Returns out_dir."""
    os.makedirs(out_dir, exist_ok=True)
    with open(rom_path, "rb") as f:
        ncch_off = _find_ncch(f)
        romfs_off, _size = _romfs_region(f, ncch_off)
        lvl3 = _level3_offset(f, romfs_off)

        # Level 3 header: the directory/file metadata tables + file data base.
        f.seek(lvl3)
        h = f.read(0x28)
        if _u32(h, 0x00) != 0x28:
            raise BadRomError("Unexpected RomFS Level 3 header.")
        dir_meta_off = _u32(h, 0x0C)
        file_meta_off = _u32(h, 0x1C)
        file_data_off = _u32(h, 0x24)

        f.seek(lvl3 + dir_meta_off)
        dir_meta = f.read(_u32(h, 0x10))
        f.seek(lvl3 + file_meta_off)
        file_meta = f.read(_u32(h, 0x20))

        def dir_name(off):
            name_len = _u32(dir_meta, off + 0x14)
            raw = dir_meta[off + 0x18: off + 0x18 + name_len]
            return raw.decode("utf-16-le", errors="replace")

        def walk_dir(dir_off: int, path: str):
            os.makedirs(path, exist_ok=True)

            # Files in this directory.
            fo = _u32(dir_meta, dir_off + 0x0C)
            while fo != 0xFFFFFFFF:
                data_off = _u64(file_meta, fo + 0x08)
                data_len = _u64(file_meta, fo + 0x10)
                name_len = _u32(file_meta, fo + 0x1C)
                name = file_meta[fo + 0x20: fo + 0x20 + name_len].decode(
                    "utf-16-le", errors="replace")
                dest = os.path.join(path, name)
                f.seek(lvl3 + file_data_off + data_off)
                remaining = data_len
                with open(dest, "wb") as out:
                    while remaining > 0:
                        chunk = f.read(min(1 << 20, remaining))
                        if not chunk:
                            break
                        out.write(chunk)
                        remaining -= len(chunk)
                fo = _u32(file_meta, fo + 0x04)   # next sibling file

            # Sub-directories.
            do = _u32(dir_meta, dir_off + 0x08)
            while do != 0xFFFFFFFF:
                walk_dir(do, os.path.join(path, dir_name(do)))
                do = _u32(dir_meta, do + 0x04)    # next sibling dir

        walk_dir(0, out_dir)
    return out_dir
