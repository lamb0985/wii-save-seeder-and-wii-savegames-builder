#!/usr/bin/env python3
"""
Wii Savegames Builder v2.1

Accepts:
  * Dolphin raw Wii title folders
  * parent Dolphin Wii/title/00010000 folders
  * Nintendo Wii SD save exports named data.bin

Produces the exact structure expected by Wii Save Seeder:

  savegames/00010000XXXXXXXX/
      banner.bin
      <save files and nested directories>

No third-party Python packages are required.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import struct
import sys
from datetime import datetime
from pathlib import Path

TITLE_TYPE = 0x00010000
TITLE_TYPE_HEX = "00010000"
HEADER_SIZE = 0xF0C0
BK_HEADER_SIZE = 0x80
FILE_HEADER_SIZE = 0x80
FILE_MAGIC = 0x03ADF17E
BK_MAGIC = 0x426B0001

# Public/global Wii SD savegame crypto material used by the System Menu.
SD_KEY = bytes.fromhex("ab01b9d8e1622b08afbad84dbfc2a55d")
SD_IV = bytes.fromhex("216712e6aa1f689f95c5a22324dc6a98")
MD5_BLANKER = bytes.fromhex("0e65378199be4517ab06ec22451a5793")

LOW_RE = re.compile(r"^[0-9A-Fa-f]{8}$")
FULL_RE = re.compile(r"^00010000[0-9A-Fa-f]{8}$")


# ---------------------------------------------------------------------------
# Minimal AES-128 decryption implementation (standard Rijndael/AES).
# Only ECB block decryption + CBC chaining are implemented because that is
# all Wii data.bin extraction needs.
# ---------------------------------------------------------------------------

SBOX = (
    0x63,0x7c,0x77,0x7b,0xf2,0x6b,0x6f,0xc5,0x30,0x01,0x67,0x2b,0xfe,0xd7,0xab,0x76,
    0xca,0x82,0xc9,0x7d,0xfa,0x59,0x47,0xf0,0xad,0xd4,0xa2,0xaf,0x9c,0xa4,0x72,0xc0,
    0xb7,0xfd,0x93,0x26,0x36,0x3f,0xf7,0xcc,0x34,0xa5,0xe5,0xf1,0x71,0xd8,0x31,0x15,
    0x04,0xc7,0x23,0xc3,0x18,0x96,0x05,0x9a,0x07,0x12,0x80,0xe2,0xeb,0x27,0xb2,0x75,
    0x09,0x83,0x2c,0x1a,0x1b,0x6e,0x5a,0xa0,0x52,0x3b,0xd6,0xb3,0x29,0xe3,0x2f,0x84,
    0x53,0xd1,0x00,0xed,0x20,0xfc,0xb1,0x5b,0x6a,0xcb,0xbe,0x39,0x4a,0x4c,0x58,0xcf,
    0xd0,0xef,0xaa,0xfb,0x43,0x4d,0x33,0x85,0x45,0xf9,0x02,0x7f,0x50,0x3c,0x9f,0xa8,
    0x51,0xa3,0x40,0x8f,0x92,0x9d,0x38,0xf5,0xbc,0xb6,0xda,0x21,0x10,0xff,0xf3,0xd2,
    0xcd,0x0c,0x13,0xec,0x5f,0x97,0x44,0x17,0xc4,0xa7,0x7e,0x3d,0x64,0x5d,0x19,0x73,
    0x60,0x81,0x4f,0xdc,0x22,0x2a,0x90,0x88,0x46,0xee,0xb8,0x14,0xde,0x5e,0x0b,0xdb,
    0xe0,0x32,0x3a,0x0a,0x49,0x06,0x24,0x5c,0xc2,0xd3,0xac,0x62,0x91,0x95,0xe4,0x79,
    0xe7,0xc8,0x37,0x6d,0x8d,0xd5,0x4e,0xa9,0x6c,0x56,0xf4,0xea,0x65,0x7a,0xae,0x08,
    0xba,0x78,0x25,0x2e,0x1c,0xa6,0xb4,0xc6,0xe8,0xdd,0x74,0x1f,0x4b,0xbd,0x8b,0x8a,
    0x70,0x3e,0xb5,0x66,0x48,0x03,0xf6,0x0e,0x61,0x35,0x57,0xb9,0x86,0xc1,0x1d,0x9e,
    0xe1,0xf8,0x98,0x11,0x69,0xd9,0x8e,0x94,0x9b,0x1e,0x87,0xe9,0xce,0x55,0x28,0xdf,
    0x8c,0xa1,0x89,0x0d,0xbf,0xe6,0x42,0x68,0x41,0x99,0x2d,0x0f,0xb0,0x54,0xbb,0x16
)
INV_SBOX = [0] * 256
for _i, _v in enumerate(SBOX):
    INV_SBOX[_v] = _i
INV_SBOX = tuple(INV_SBOX)

RCON = (0x00,0x01,0x02,0x04,0x08,0x10,0x20,0x40,0x80,0x1b,0x36)

def _xtime(a: int) -> int:
    return ((a << 1) ^ (0x11B if a & 0x80 else 0)) & 0xFF

def _gmul(a: int, b: int) -> int:
    out = 0
    while b:
        if b & 1:
            out ^= a
        a = _xtime(a)
        b >>= 1
    return out

def _expand_key(key: bytes):
    if len(key) != 16:
        raise ValueError("AES-128 key must be 16 bytes")
    w = list(key)
    bytes_generated = 16
    rcon_iter = 1
    temp = [0,0,0,0]
    while bytes_generated < 176:
        temp[:] = w[bytes_generated-4:bytes_generated]
        if bytes_generated % 16 == 0:
            temp = temp[1:] + temp[:1]
            temp = [SBOX[x] for x in temp]
            temp[0] ^= RCON[rcon_iter]
            rcon_iter += 1
        for x in temp:
            w.append(w[bytes_generated - 16] ^ x)
            bytes_generated += 1
    return [bytes(w[i:i+16]) for i in range(0, 176, 16)]

def _add_round_key(state, rk):
    for i in range(16):
        state[i] ^= rk[i]

def _inv_shift_rows(s):
    # State is column-major: index = row + 4*column.
    s[1], s[5], s[9], s[13] = s[13], s[1], s[5], s[9]
    s[2], s[6], s[10], s[14] = s[10], s[14], s[2], s[6]
    s[3], s[7], s[11], s[15] = s[7], s[11], s[15], s[3]

def _inv_sub_bytes(s):
    for i in range(16):
        s[i] = INV_SBOX[s[i]]

def _inv_mix_columns(s):
    for c in range(4):
        i = c * 4
        a0,a1,a2,a3 = s[i:i+4]
        s[i+0] = _gmul(a0,14) ^ _gmul(a1,11) ^ _gmul(a2,13) ^ _gmul(a3,9)
        s[i+1] = _gmul(a0,9)  ^ _gmul(a1,14) ^ _gmul(a2,11) ^ _gmul(a3,13)
        s[i+2] = _gmul(a0,13) ^ _gmul(a1,9)  ^ _gmul(a2,14) ^ _gmul(a3,11)
        s[i+3] = _gmul(a0,11) ^ _gmul(a1,13) ^ _gmul(a2,9)  ^ _gmul(a3,14)

def aes128_decrypt_block(block: bytes, key: bytes) -> bytes:
    if len(block) != 16:
        raise ValueError("AES block must be 16 bytes")
    keys = _expand_key(key)
    s = list(block)
    _add_round_key(s, keys[10])
    for rnd in range(9, 0, -1):
        _inv_shift_rows(s)
        _inv_sub_bytes(s)
        _add_round_key(s, keys[rnd])
        _inv_mix_columns(s)
    _inv_shift_rows(s)
    _inv_sub_bytes(s)
    _add_round_key(s, keys[0])
    return bytes(s)

def aes128_cbc_decrypt(data: bytes, key: bytes, iv: bytes, progress_label: str | None = None) -> bytes:
    if len(iv) != 16:
        raise ValueError("AES IV must be 16 bytes")
    if len(data) % 16:
        raise ValueError("AES-CBC data length is not a multiple of 16")
    out = bytearray()
    prev = iv
    total = len(data)
    update_every = max(16, ((total // 100) // 16) * 16) if total else 16
    next_update = 0
    if progress_label:
        _print_progress(progress_label, 0, total)
    for off in range(0, total, 16):
        block = data[off:off+16]
        dec = aes128_decrypt_block(block, key)
        out.extend(a ^ b for a, b in zip(dec, prev))
        prev = block
        done = off + 16
        if progress_label and (done >= next_update or done >= total):
            _print_progress(progress_label, done, total)
            next_update = done + update_every
    return bytes(out)


# ---------------------------------------------------------------------------
# Console progress helpers
# ---------------------------------------------------------------------------

def _format_bytes(n: int) -> str:
    units = ("B", "KB", "MB", "GB")
    value = float(n)
    for unit in units:
        if value < 1024.0 or unit == units[-1]:
            return f"{int(value)} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024.0
    return f"{n} B"

def _print_progress(label: str, done: int, total: int, width: int = 32):
    total = max(total, 1)
    done = max(0, min(done, total))
    ratio = done / total
    filled = int(ratio * width)
    bar = "#" * filled + "-" * (width - filled)
    print(f"\r{label:<18} [{bar}] {ratio*100:6.2f}% ({_format_bytes(done)} / {_format_bytes(total)})", end="", flush=True)
    if done >= total:
        print()

# ---------------------------------------------------------------------------
# Wii data.bin parsing
# ---------------------------------------------------------------------------

class DataBinError(Exception):
    pass

def be32(b: bytes, off: int) -> int:
    return struct.unpack_from(">I", b, off)[0]

def be64(b: bytes, off: int) -> int:
    return struct.unpack_from(">Q", b, off)[0]

def align64(n: int) -> int:
    return (n + 63) & ~63

def safe_relative_name(raw: bytes) -> Path:
    name = raw.split(b"\0", 1)[0].decode("utf-8", "replace").replace("\\", "/")
    while name.startswith("/"):
        name = name[1:]
    parts = [p for p in name.split("/") if p not in ("", ".")]
    if not parts or any(p == ".." for p in parts):
        raise DataBinError(f"unsafe file name in data.bin: {name!r}")
    return Path(*parts)

def inspect_data_bin(path: Path):
    size = path.stat().st_size
    if size < HEADER_SIZE + BK_HEADER_SIZE:
        raise DataBinError("file is too small to be a Wii save data.bin")

    with path.open("rb") as f:
        encrypted_header = f.read(HEADER_SIZE)
        if len(encrypted_header) != HEADER_SIZE:
            raise DataBinError("short encrypted header")

        header = aes128_cbc_decrypt(encrypted_header, SD_KEY, SD_IV, "Header decrypt")

        saved_md5 = header[0x0E:0x1E]
        md5_input = bytearray(header)
        md5_input[0x0E:0x1E] = MD5_BLANKER
        calc_md5 = hashlib.md5(md5_input).digest()
        if saved_md5 != calc_md5:
            raise DataBinError(
                "header MD5 check failed (not a valid Wii save data.bin, "
                "or file is damaged)"
            )

        title_id = be64(header, 0)
        banner_size = be32(header, 8)

        if banner_size < 0x72A0 or banner_size > 0xF0A0:
            raise DataBinError(f"invalid banner size 0x{banner_size:X}")

        if header[0x20:0x24] != b"WIBN":
            raise DataBinError("decrypted banner does not begin with WIBN")

        bk = f.read(BK_HEADER_SIZE)
        if len(bk) != BK_HEADER_SIZE:
            raise DataBinError("missing Bk header")
        if be32(bk, 0) != 0x70 or be32(bk, 4) != BK_MAGIC:
            raise DataBinError("invalid Bk header")

        n_files = be32(bk, 0x0C)
        files_size = be32(bk, 0x10)
        total_size = be32(bk, 0x1C)

    return {
        "title_id": title_id,
        "banner_size": banner_size,
        "header": header,
        "n_files": n_files,
        "files_size": files_size,
        "total_size": total_size,
        "file_size": size,
    }

def extract_data_bin(path: Path, temp_out: Path):
    info = inspect_data_bin(path)
    title_id = info["title_id"]

    # Save Seeder currently supports normal disc titles only.
    high = (title_id >> 32) & 0xFFFFFFFF
    low = title_id & 0xFFFFFFFF
    if high != TITLE_TYPE:
        raise DataBinError(
            f"title ID {title_id:016X} is not a normal 00010000 disc-title save"
        )

    out = temp_out / f"{title_id:016X}"
    out.mkdir(parents=True, exist_ok=False)

    # data.bin's encrypted header contains the exact raw NAND banner.bin
    # beginning at offset 0x20; the size field at 0x08 is its length.
    banner = info["header"][0x20:0x20 + info["banner_size"]]
    if len(banner) != info["banner_size"] or not banner.startswith(b"WIBN"):
        raise DataBinError("could not reconstruct banner.bin")
    (out / "banner.bin").write_bytes(banner)

    extracted = 0
    dirs = 0
    processed_entries = 0

    print()
    print(f"Title ID          : {title_id:016X}")
    print(f"Entries           : {info['n_files']}")
    print(f"Encrypted payload : {_format_bytes(info['files_size'])}")
    print()

    with path.open("rb") as f:
        f.seek(HEADER_SIZE + BK_HEADER_SIZE)

        for index in range(info["n_files"]):
            fh = f.read(FILE_HEADER_SIZE)
            if len(fh) != FILE_HEADER_SIZE:
                raise DataBinError(f"short file header at entry {index}")

            if be32(fh, 0) != FILE_MAGIC:
                raise DataBinError(
                    f"bad file magic at entry {index}: 0x{be32(fh,0):08X}"
                )

            file_size = be32(fh, 4)
            file_type = fh[10]
            rel = safe_relative_name(fh[11:0x50])
            target = out / rel

            # Belt-and-suspenders path traversal check.
            resolved_root = out.resolve()
            resolved_target_parent = target.parent.resolve()
            if resolved_root != resolved_target_parent and resolved_root not in resolved_target_parent.parents:
                raise DataBinError(f"unsafe output path: {rel}")

            if file_type == 2:
                target.mkdir(parents=True, exist_ok=True)
                dirs += 1
                processed_entries += 1
                print(f"[{processed_entries:>3}/{info['n_files']}] DIR   {rel}")
                continue

            if file_type != 1:
                raise DataBinError(
                    f"unsupported entry type {file_type} for {rel}"
                )

            rounded = align64(file_size)
            encrypted = f.read(rounded)
            if len(encrypted) != rounded:
                raise DataBinError(f"short encrypted file data for {rel}")

            processed_entries += 1
            print(f"[{processed_entries:>3}/{info['n_files']}] FILE  {rel}  ({_format_bytes(file_size)})")
            iv = fh[0x50:0x60]
            plaintext = aes128_cbc_decrypt(encrypted, SD_KEY, iv, f"  decrypt {processed_entries}/{info['n_files']}")

            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(plaintext[:file_size])
            extracted += 1

    print()
    print(f"Extraction complete: {extracted} file(s), {dirs} director{'y' if dirs == 1 else 'ies'}")
    print()

    return {
        **info,
        "output": out,
        "files_extracted": extracted,
        "dirs_extracted": dirs,
        "full_id": f"{title_id:016X}",
        "low_id": f"{low:08X}",
    }


# ---------------------------------------------------------------------------
# Dolphin raw NAND discovery
# ---------------------------------------------------------------------------

def is_valid_data_dir(data_dir: Path) -> bool:
    return data_dir.is_dir() and (data_dir / "banner.bin").is_file()

def title_from_low_folder(folder: Path):
    if folder.is_dir() and LOW_RE.fullmatch(folder.name):
        data_dir = folder / "data"
        if is_valid_data_dir(data_dir):
            return folder.name.upper(), data_dir
    return None

def title_from_full_folder(folder: Path):
    if folder.is_dir() and FULL_RE.fullmatch(folder.name):
        low = folder.name[-8:].upper()
        if (folder / "banner.bin").is_file():
            return low, folder
        data_dir = folder / "data"
        if is_valid_data_dir(data_dir):
            return low, data_dir
    return None

def title_from_data_folder(folder: Path):
    if folder.is_dir() and folder.name.lower() == "data" and is_valid_data_dir(folder):
        parent = folder.parent
        if LOW_RE.fullmatch(parent.name):
            return parent.name.upper(), folder
        if FULL_RE.fullmatch(parent.name):
            return parent.name[-8:].upper(), folder
    return None

def discover_dolphin_titles(path: Path):
    found = {}
    if not path.exists() or path.is_file():
        return found

    for detector in (title_from_data_folder, title_from_full_folder, title_from_low_folder):
        hit = detector(path)
        if hit:
            found[hit[0]] = hit[1]
            return found

    if path.name.lower() == TITLE_TYPE_HEX:
        for child in path.iterdir():
            hit = title_from_low_folder(child)
            if hit:
                found[hit[0]] = hit[1]
        return found

    for common in (path / "title" / TITLE_TYPE_HEX, path / TITLE_TYPE_HEX):
        if common.is_dir():
            for child in common.iterdir():
                hit = title_from_low_folder(child)
                if hit:
                    found[hit[0]] = hit[1]
            if found:
                return found

    for root, dirs, files in os.walk(path, followlinks=False):
        rootp = Path(root)
        if rootp.name.lower() == "data" and "banner.bin" in files:
            parent = rootp.parent
            if LOW_RE.fullmatch(parent.name):
                found[parent.name.upper()] = rootp
                dirs[:] = []
                continue
            if FULL_RE.fullmatch(parent.name):
                found[parent.name[-8:].upper()] = rootp
                dirs[:] = []
                continue
        if FULL_RE.fullmatch(rootp.name) and "banner.bin" in files:
            found[rootp.name[-8:].upper()] = rootp
            dirs[:] = []
    return found


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------

def find_data_bins(path: Path):
    if path.is_file():
        return [path] if path.name.lower() == "data.bin" else []
    if not path.is_dir():
        return []
    return [p for p in path.rglob("*") if p.is_file() and p.name.lower() == "data.bin"]

def backup_and_replace(src: Path, dst: Path, backup_root: Path | None):
    if dst.exists():
        if backup_root is None:
            raise RuntimeError("internal backup path error")
        backup_root.mkdir(parents=True, exist_ok=True)
        shutil.move(str(dst), str(backup_root / dst.name))
    shutil.copytree(src, dst)

def main():
    script_dir = Path(__file__).resolve().parent
    output_root = script_dir / "savegames"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_root = script_dir / f"savegames_backup_{stamp}"
    temp_root = script_dir / f".extract_tmp_{stamp}"

    args = [Path(a.strip('"')).expanduser() for a in sys.argv[1:]]
    if not args:
        print()
        print("Wii Savegames Builder v2.1")
        print("=" * 50)
        print("Drag Dolphin title folders, data.bin files, or folders")
        print("containing data.bin files onto BUILD_SAVEGAMES.bat.")
        print()
        raw = input("Or paste a path here: ").strip().strip('"')
        if not raw:
            return 1
        args = [Path(raw).expanduser()]

    sources = {}
    errors = []

    temp_root.mkdir(parents=True, exist_ok=True)

    try:
        print()
        print("Scanning inputs...")
        for arg in args:
            p = arg.resolve()
            if not p.exists():
                errors.append(f"{p}: path does not exist")
                continue

            # Direct/recursive data.bin support.
            dbins = find_data_bins(p)
            if dbins:
                for db in dbins:
                    try:
                        print()
                        print("=" * 50)
                        print(f"[DATA.BIN] {db}")
                        print("=" * 50)
                        result = extract_data_bin(db, temp_root)
                        low = result["low_id"]
                        sources[low] = result["output"]
                        print(
                            f"           {result['full_id']} - "
                            f"{result['files_extracted']} file(s), "
                            f"{result['dirs_extracted']} dir(s)"
                        )
                    except Exception as exc:
                        errors.append(f"{db}: {exc}")

                # If input itself was data.bin, don't also treat as Dolphin path.
                if p.is_file():
                    continue

            # Dolphin raw title folders.
            found = discover_dolphin_titles(p)
            for low, data_dir in found.items():
                if low not in sources:
                    print(f"[DOLPHIN]  {TITLE_TYPE_HEX}{low} <- {data_dir}")
                    sources[low] = data_dir

        if not sources:
            print()
            print("No usable saves found.")
            for e in errors:
                print("ERROR:", e)
            input("\nPress Enter to exit...")
            return 2

        output_root.mkdir(parents=True, exist_ok=True)

        print()
        print("Building Seeder folder...")
        ok = 0
        failed = 0

        for low in sorted(sources):
            full_id = f"{TITLE_TYPE_HEX}{low}"
            src = sources[low]
            dst = output_root / full_id

            try:
                if dst.exists():
                    backup_root.mkdir(parents=True, exist_ok=True)
                    old = backup_root / full_id
                    if old.exists():
                        shutil.rmtree(old)
                    print(f"[BACKUP]   {full_id}")
                    shutil.move(str(dst), str(old))

                print(f"[COPY]     {full_id}")
                shutil.copytree(src, dst)

                banner = dst / "banner.bin"
                if not banner.is_file() or banner.read_bytes()[:4] != b"WIBN":
                    raise RuntimeError("output banner.bin is missing or invalid")

                ok += 1

            except Exception as exc:
                failed += 1
                errors.append(f"{full_id}: {exc}")
                if dst.exists():
                    shutil.rmtree(dst, ignore_errors=True)
                old = backup_root / full_id
                if old.exists() and not dst.exists():
                    shutil.move(str(old), str(dst))

        if backup_root.exists():
            try:
                if not any(backup_root.iterdir()):
                    backup_root.rmdir()
            except OSError:
                pass

        print()
        print("=" * 50)
        print(f"Created : {ok}")
        print(f"Failed  : {failed}")
        print(f"Output  : {output_root}")
        if backup_root.exists():
            print(f"Backup  : {backup_root}")

        if errors:
            print()
            print("Errors:")
            for e in errors:
                print(" -", e)

        print()
        print("Copy the resulting 'savegames' folder to the root of")
        print("the SD card used by Wii Save Seeder.")
        input("\nPress Enter to exit...")
        return 0 if failed == 0 and not errors else 3

    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
