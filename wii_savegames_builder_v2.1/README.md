# Wii Savegames Builder v2.1

Creates the exact `/savegames` format used by Wii Save Seeder.

## Inputs

You can drag any mixture of these onto `BUILD_SAVEGAMES.bat`:

- Wii `data.bin` save exports
- a folder containing multiple `data.bin` exports
- Dolphin raw NAND title folders
- Dolphin `Wii/title/00010000`
- Dolphin `Wii`

For data.bin-only use, `EXTRACT_DATA_BIN.bat` is included too.

## data.bin handling

The tool decrypts Wii save exports itself. No tachtig, FE100, OpenSSL,
PyCryptodome, or other dependency is required.

It:

1. decrypts the 0xF0C0 header with the Wii SD key/IV;
2. verifies the header MD5;
3. reads the full 64-bit title ID;
4. reconstructs raw `banner.bin` from the decrypted banner block;
5. parses every 0x80-byte file header;
6. decrypts each file with its per-file IV;
7. preserves nested directories;
8. writes directly to the Wii Save Seeder layout.

Example:

```text
private/wii/title/RSBE/data.bin

becomes

savegames/
  0001000052534245/
    banner.bin
    advsv0.bin
    ...
```

## Dolphin handling

For Dolphin raw NAND:

```text
Dolphin/User/Wii/title/00010000/52535045/data/
```

becomes:

```text
savegames/0001000052535045/
```

Everything underneath Dolphin's `data/` folder is copied exactly.

## Safety

- Only `00010000` disc-title saves are accepted because that is what the
  current Wii Save Seeder supports.
- Paths stored inside data.bin are checked for traversal (`..`) before
  extraction.
- Existing output title folders are moved to a timestamped backup first.
- `banner.bin` must begin with `WIBN` before an output is accepted.

## Requirements

Python 3 only. No third-party modules.


## v2.1 progress display

Same pure-Python AES as v2.0, but now shows:
- header decryption progress
- title ID, entry count, and payload size
- current file/directory
- per-file decryption progress bar
- final extraction summary

Progress updates are throttled to avoid slowing extraction further.
