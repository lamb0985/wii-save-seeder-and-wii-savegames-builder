Wii Save Seeder + Wii Savegames Builder

<img width="128" height="48" alt="icon" src="https://github.com/user-attachments/assets/f6c6e46a-e8f5-4644-9400-e0f44b2c66ba" />

OVERVIEW

This repository contains two related utilities for moving Wii save data from Dolphin or Wii System Menu data.bin exports onto a real Wii:

1. Wii Save Seeder v0.8
   A Wii homebrew application that installs prepared Wii save data directly to real Wii NAND.

2. Wii Savegames Builder v2.2
   A desktop Python utility that converts supported save sources into the /savegames folder structure used by Wii Save Seeder.

IMPORTANT DISCLAIMER

USE THESE PROGRAMS AT YOUR OWN RISK.

Wii Save Seeder writes directly to the Wii's internal NAND filesystem and modifies /sys/uid.sys. Incorrect NAND modifications can potentially cause save corruption, filesystem damage, or in the worst case an unusable Wii.

Before using Wii Save Seeder, it is strongly recommended that you:

- Have a current BootMii NAND backup.
- Keep a copy of that NAND backup somewhere other than the Wii SD card.
- Have Priiloader and/or another recovery method available where appropriate.
- Back up any existing saves you care about.
- Keep the uid.sys backups automatically created by Wii Save Seeder.
- Keep your original Dolphin or data.bin save files.

WII SAVE SEEDER IS UNOFFICIAL HOMEBREW.

Wii Save Seeder is an independent homebrew application. It is not officially supported, endorsed, or maintained by the Homebrew Channel, devkitPro, Dolphin, Nintendo, USB Loader GX, or any other Wii homebrew project whose research, libraries, or source code may have helped make this project possible.

Do not contact those projects for support with Wii Save Seeder.

HOW THE WORKFLOW WORKS

Dolphin save folder
        OR
Wii data.bin export
        |
        v
Wii Savegames Builder
        |
        v
savegames/00010000XXXXXXXX/
        |
        v
SD card
        |
        v
Wii Save Seeder
        |
        v
Real Wii NAND save

The Builder runs on a computer and prepares the files.

The Seeder runs on the Wii and installs them.

------------------------------------------------------------
WII SAVEGAMES BUILDER v2.2
------------------------------------------------------------

Wii Savegames Builder is a desktop Python utility.

It converts supported Wii save sources into the directory layout expected by Wii Save Seeder.

The Windows package includes:

BUILD_SAVEGAMES.bat
wii_savegames_builder.py

The Python script contains the actual program logic. The BAT file is only a Windows convenience launcher.

SUPPORTED INPUTS

Wii Savegames Builder can process:

- Individual Wii data.bin save exports.
- A folder containing one or more data.bin save exports.
- Individual Dolphin Wii title folders.
- Dolphin/User/Wii/title/00010000/
- Dolphin/User/Wii/
- Multiple supported inputs together.

DOLPHIN RAW NAND SAVES

Example Dolphin save:

Dolphin/User/Wii/title/00010000/52535045/
    content/
        title.tmd
    data/
        banner.bin
        RPSports.dat

Wii Save Seeder only needs the contents of the title's data folder.

The Builder converts the example above into:

savegames/
    0001000052535045/
        banner.bin
        RPSports.dat

Nested directories are preserved.

Example:

data/
    banner.bin
    DBZT3
    nocopy/
        DBZT3_WIFI

becomes:

savegames/
    00010000XXXXXXXX/
        banner.bin
        DBZT3
        nocopy/
            DBZT3_WIFI

The Dolphin content/title.tmd file is intentionally not copied because Wii Save Seeder does not use it.

WII data.bin EXPORTS

The Builder can also process saves exported by the Wii System Menu.

These are commonly found under:

private/wii/title/XXXX/data.bin

The Builder:

1. Decrypts the Wii save archive.
2. Reads the embedded title ID.
3. Reconstructs banner.bin.
4. Extracts the embedded save files.
5. Preserves nested directories and filenames.
6. Creates the Wii Save Seeder folder automatically.

Example:

data.bin

may become:

savegames/
    0001000052534245/
        banner.bin
        advsv0.bin
        ...

AES DECRYPTION

Wii data.bin files use AES encryption.

Wii Savegames Builder v2.2 includes:

- A Windows-native AES path using bcrypt.dll / Windows CNG.
- A pure-Python AES fallback.

No separate data.bin extraction program is required.

The pure-Python fallback can be significantly slower, especially with large saves.

Progress information is displayed while data.bin files are being processed.

EXISTING OUTPUT PROTECTION

If a title already exists inside the generated savegames folder, the Builder moves the existing output into a timestamped backup before replacing it.

OUTPUT FORMAT

The Builder creates folders in this format:

savegames/
    00010000XXXXXXXX/
        banner.bin
        save files...
        subfolders...

The complete folder name is the Wii title ID.

------------------------------------------------------------
WII SAVE SEEDER v0.8
------------------------------------------------------------

Wii Save Seeder is a Wii homebrew application.

Its purpose is to install prepared Wii save data onto real Wii NAND, including cases where the game has never previously created a save on that Wii.

WHY IT EXISTS

Some Wii save restoration tools expect a game to have already been launched so that the console has created:

- The title save directory.
- The title's UID entry.
- Correct NAND ownership information.

Wii Save Seeder creates that required save environment itself.

This allows a prepared save to be installed without requiring the game to be launched first.

SD CARD LAYOUT

Place Wii Save Seeder under the normal Homebrew Channel application directory:

SD:/
    apps/
        wii_save_seeder/
            boot.dol
            meta.xml
            icon.png

Place prepared saves at:

SD:/
    savegames/
        0001000052535045/
            banner.bin
            RPSports.dat

        0001000052534245/
            banner.bin
            advsv0.bin
            ...

The save folder name is the complete Wii disc title ID:

00010000XXXXXXXX

where XXXXXXXX is the hexadecimal lower 32 bits of the title ID.

Example:

RSPE

ASCII bytes:

52 53 50 45

Full title ID:

0001000052535045

WHAT WII SAVE SEEDER DOES

At a high level, Wii Save Seeder:

1. Scans the SD card /savegames directory.
2. Displays available saves.
3. Reads the selected Wii title ID.
4. Reads /sys/uid.sys from NAND.
5. Creates a backup of uid.sys on the SD card.
6. Finds the existing title UID, or allocates a new one when necessary.
7. Verifies that the required NAND ownership operation works.
8. Adds the title UID mapping if necessary.
9. Creates the title save directory.
10. Creates empty save files and directories.
11. Assigns the correct game UID ownership.
12. Copies the save data.
13. Verifies ownership after writing.

uid.sys

The Wii stores title-to-UID mappings in:

/sys/uid.sys

Games normally receive an entry when their save environment is created.

If the selected game already has a UID entry, Wii Save Seeder reuses it.

If the game does not have an entry, Wii Save Seeder adds one.

Before modifying uid.sys, Wii Save Seeder creates a backup on the SD card.

KEEP THESE BACKUPS.

NAND OWNERSHIP

Simply copying files into:

/title/00010000/XXXXXXXX/data/

is not enough.

Wii save files and directories must have the ownership information expected by IOS and the game.

Wii Save Seeder uses temporary runtime IOS patches and ISFS_SetAttr() to assign the game's UID to newly-created save content.

v0.8 uses this order for files:

create empty file
    |
    v
assign game UID
    |
    v
verify ownership
    |
    v
write save contents
    |
    v
verify ownership again

The ownership change is performed before writing file contents because IOS may reject ownership changes on non-empty files.

RUNTIME IOS PATCHING

Wii Save Seeder requires Homebrew Channel AHBPROT access.

The application's meta.xml must include:

<ahb_access/>

At runtime, Wii Save Seeder temporarily patches the currently-loaded IOS in memory to allow the NAND operations required for save installation.

These patches are temporary and are not permanently installed into IOS.

The application checks for the expected IOS patch signatures before applying them.

If the required signatures are not found, Wii Save Seeder refuses to continue.

EXISTING SAVES

Wii Save Seeder is primarily intended to seed or restore saves where the proper Wii save environment does not already exist.

It should not be treated as a general-purpose save merge utility.

Back up existing saves before replacing or modifying them.

VERIFIED USE CASE

The intended workflow has been successfully tested as:

Dolphin Wii NAND
    |
    v
Wii Savegames Builder
    |
    v
SD:/savegames/
    |
    v
Wii Save Seeder
    |
    v
Real Wii NAND
    |
    v
Launch game
    |
    v
Restored save recognized by the game

Wii Save Seeder v0.8 was successfully tested with a save that previously could not be restored because the required Wii save/UID environment did not exist.

After installation through Wii Save Seeder, the game recognized the restored save data normally.

This does not guarantee compatibility with every Wii title.

REQUIREMENTS

Wii Save Seeder:

- Nintendo Wii capable of running Homebrew Channel applications.
- SD card.
- Homebrew Channel with AHBPROT access.
- Properly-prepared /savegames directory.
- Strongly recommended: current BootMii NAND backup.

Wii Savegames Builder:

- Python 3.
- Windows, Linux, or another environment capable of running the Python script for the platform-independent portions.
- The included BAT file is only a Windows convenience launcher.
- Some acceleration features in v2.2 are Windows-specific.

RECOMMENDED BACKUP PROCEDURE

Before experimenting with NAND save installation:

1. Create a current BootMii NAND backup.
2. Copy the NAND backup somewhere off the SD card.
3. Back up existing Wii saves.
4. Keep Wii Save Seeder's uid.sys backup files.
5. Keep the original Dolphin or data.bin source saves.

Do not make the generated savegames folder your only copy of important save data.

KNOWN LIMITATIONS

- Wii Save Seeder currently targets normal Wii disc-title saves using title type 00010000.
- Not every Wii game has been tested.
- Some games may use unusual save structures or additional system services.
- Wii Save Seeder is not intended to install channels, WADs, tickets, IOSes, or System Menu content.
- Wii Save Seeder is not a replacement for a NAND backup or brick-recovery solution.
- The pure-Python data.bin AES fallback can be slow.
- v2.2's native bcrypt.dll acceleration is Windows-specific.

PROJECT SCOPE

Wii Save Seeder intentionally deals only with save-related NAND content.

It does not attempt to install:

- Game channels.
- WADs.
- IOS modules.
- Tickets.
- System Menu files.
- Game executable content.

The goal is narrowly focused:

Prepare the Wii's NAND save environment and restore an existing game's save data without requiring the game to be launched first.

CREDITS / ACKNOWLEDGMENTS

This project builds on publicly documented Wii filesystem behavior, Wii save formats, libogc/devkitPro APIs, and years of Wii homebrew research.

Relevant projects and documentation include:

- devkitPro / libogc
- Homebrew Channel
- Dolphin Emulator
- WiiBrew documentation
- USB Loader GX / libruntimeiospatch
- Prior Wii filesystem and save-format research

Their inclusion here is acknowledgment only and does not imply endorsement or official support of Wii Save Seeder.

LICENSE / RESPONSIBILITY

Review the licenses of any included or adapted source code before redistributing binaries or source.

By using Wii Save Seeder or Wii Savegames Builder, you accept responsibility for any changes made to your files, SD card, saves, or Wii NAND.

BACK UP FIRST.
