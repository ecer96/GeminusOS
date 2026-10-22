# GeminusOS

A ready-to-use custom system image for the **Anbernic RG DS Plus** (Rockchip RK3568, dual 1024×768 displays). It includes a custom launcher, emulators, an in-game menu, apps and system settings in a single image.

**English** | [Español](README.es.md)

![GeminusOS](https://img.shields.io/badge/system-v1.29-blue)

## Download

The base image is available in the **[v1 release](https://github.com/ecer96/GeminusOS/releases/tag/v1)**:

| File | Size | SHA-256 |
|---|---|---|
| `GeminusOS-v1.1.img.zst` | 1.7 GB | `40bcf0d689fc9c35124b1946469c5e688d665a1e5d5da5995d16ca784ab08674` |

The uncompressed image is 15.5 GB. You need a microSD card of **at least 16 GB** (32 GB recommended).

> The downloadable image is the **v1.1 base**. After the first boot, update to the latest version (currently **v1.29**) from **Settings → Update**. The base image already includes the updater.

### What is in each release?

- **v1** — full base image. Download this once and flash it to a microSD card.
- **v1.29** — latest system payload. It is installed automatically through **Settings → Update**; you do **not** need to reflash the card.
- Later releases are incremental payloads for the updater. The full image only changes when the base system needs to be regenerated.

## Requirements

- Anbernic RG DS Plus.
- A microSD card: 16 GB minimum, 32 GB recommended.
- A microSD reader (or a USB cable for MTP after the first boot).
- A computer with Windows, Linux or macOS.

> Flashing completely erases the microSD card. Back up anything you want to keep first.

---

## 1. Verify the download

### Windows (PowerShell)

```powershell
Get-FileHash .\GeminusOS-v1.1.img.zst -Algorithm SHA256
```

The result must be:

```text
40bcf0d689fc9c35124b1946469c5e688d665a1e5d5da5995d16ca784ab08674
```

### Linux

```bash
sha256sum GeminusOS-v1.1.img.zst
```

### macOS

```bash
shasum -a 256 GeminusOS-v1.1.img.zst
```

---

## 2. Extract the image

balenaEtcher and Rufus **cannot open `.zst` files**. Extract the `.img` first.

### Windows

Choose one:

- **7-Zip** (recent versions support Zstandard): right-click the `.zst` file → **7-Zip → Extract Here**.
- **PeaZip**: open the `.zst` and extract the image.
- **Official zstd**: download it from <https://github.com/facebook/zstd/releases>, then run:

```powershell
.\zstd.exe -d .\GeminusOS-v1.1.img.zst
```

### Linux

Install `zstd` if needed (package name may vary):

```bash
sudo apt install zstd        # Debian/Ubuntu
sudo pacman -S zstd          # Arch
sudo dnf install zstd        # Fedora
```

Then extract:

```bash
zstd -d GeminusOS-v1.1.img.zst
```

### macOS

Install `zstd` with Homebrew if needed:

```bash
brew install zstd
```

Then extract:

```bash
zstd -d GeminusOS-v1.1.img.zst
```

After this step you should have a file named `GeminusOS-v1.1.img` (about 15.5 GB).

---

## 3. Flash the microSD card

### Windows — balenaEtcher (recommended)

1. Install and open [balenaEtcher](https://etcher.balena.io/).
2. Click **Flash from file** and select `GeminusOS-v1.1.img`.
3. Select your microSD card.
4. Click **Flash** and wait for it to finish.
5. Eject the card.

If Windows asks you to format the newly created partitions, click **Cancel**. Those partitions belong to GeminusOS.

### Windows — Rufus

1. Download and open [Rufus](https://rufus.ie/).
2. Under **Device**, select the microSD card.
3. Click **SELECT** and choose `GeminusOS-v1.1.img`.
4. Click **START**.
5. If Rufus asks about image mode, choose **Write in DD image mode**.
6. Confirm that all data on the card will be erased, and wait for completion.

### Linux — dd (terminal)

> Replace `/dev/sdX` with the **whole microSD device**, not a partition such as `/dev/sdX1`. Use `lsblk` to identify it.

```bash
lsblk -o NAME,SIZE,MODEL
```

Unmount any mounted partitions from the card:

```bash
sudo umount /dev/sdX* 2>/dev/null
```

Flash the image:

```bash
sudo dd if=GeminusOS-v1.1.img of=/dev/sdX bs=4M status=progress conv=fsync
sync
```

You can also use balenaEtcher on Linux (AppImage).

### macOS — dd (terminal)

> Replace `diskN` with the **whole microSD disk**, for example `disk4`. Do not use `disk4s1`.

```bash
diskutil list
diskutil unmountDisk /dev/diskN
sudo dd if=GeminusOS-v1.1.img of=/dev/rdiskN bs=4m
sync
diskutil eject /dev/diskN
```

Using `/dev/rdiskN` (raw disk) is much faster than `/dev/diskN`.

You can also use balenaEtcher on macOS.

---

## 4. First boot and update

1. Insert the microSD card into the RG DS Plus.
2. Power on the console.
3. The first boot may take a little longer than usual.
4. Connect to WiFi.
5. Open **Settings → Update** and install the latest version (currently **v1.29**).

The base image is v1.1. Updating is important: new launcher features, fixes and improvements are delivered through the updater, so you do not need to reflash the card for every release.

---

## 5. Add your games

GeminusOS does **not** include games, ROMs or BIOS files.

After the first boot, copy your files to:

```text
/mnt/sdcard/roms/<system>/
```

Examples:

```text
/mnt/sdcard/roms/nds/
/mnt/sdcard/roms/snes/
/mnt/sdcard/roms/psx/
/mnt/sdcard/roms/APPS/
```

You can use the console's MTP mode over USB or put the microSD card in a card reader. On Windows, the large data partition may appear as a separate drive; do not modify the system partitions.

Covers and metadata can be downloaded from the **Scraper** menu. Place BIOS files where each emulator expects them.

---

## What’s included

### Interface

- Custom launcher with three home layouts: grid, panel + list and console-style carousel.
- Three game library layouts: classic slider, wheel and grid.
- Covers, synopsis and game metadata.
- Full navigation with D-pad, buttons and touchscreen.
- Light/dark themes, custom accent colors and Spanish/English UI.

### Library

- Automatic ROM scanning by platform.
- Favorites, recent games, search and “no cover” filters.
- On-screen keyboard search.
- Sorting, random game (“Surprise”) and game collections.
- Cover/metadata scraping with Libretro or ScreenScraper.

### In-game

- RetroArch in-game panel on the lower screen:
  - Save and load states.
  - Fast forward, pause, reset and RetroArch menu.
  - Screenshots, brightness and volume.
  - CPU, RAM, battery and temperature information.
- Nintendo DS with DraStic:
  - Custom in-game menu.
  - Custom shaders (`.dfx`, `.dsd`, `.frag`).
  - Save/load states, fast forward, microphone and screenshots.
- Automatic saves and “Continue” for the last game.

### Apps

- Lightweight web browser.
- YouTube.
- Media player.
- Ports and additional apps from the `APPS` folder.

### System

- WiFi, SSH and MTP.
- Brightness, volume and screen timeout.
- Date and time.
- System information: IP, MAC, kernel, temperature, CPU, RAM and battery.
- Safe reboot and shutdown.
- Over-the-air updates from **Settings → Update**.

---

## Supported platforms

**Dedicated emulators**

Nintendo DS · PSP · Dreamcast · Saturn · OpenBOR · Pico-8

**RetroArch**

Game Boy · Game Boy Color · Game Boy Advance · NES · SNES · Sega Genesis / Mega Drive · Sega CD · Sega 32X · Master System · Game Gear · Nintendo 64 · PlayStation · Atari 2600 · Atari 5200 · Atari 7800 · Atari 800 · Atari Lynx · Atari ST · Commodore 64 · VIC-20 · Amiga · CPS1 · CPS2 · CPS3 · Neo Geo · Neo Geo CD · Neo Geo Pocket · MAME · FBNeo · MSX · PC Engine · PC Engine CD · WonderSwan · Virtual Boy · Pokémon Mini · Game & Watch · ScummVM · DOS · EasyRPG · ONS

**Other**

Ports · Apps

---

## Controls

| Button | Action |
|---|---|
| D-pad / stick | Navigate |
| **A** | Open / confirm |
| **B** | Back / cancel |
| **X** | Continue last game (Home) |
| **Y** | Options: favorite, surprise, collection, sort, scrape |
| **L1 / R1** | Alphabetical jump in the game list |
| **Select** | Play the game of the day |
| **Menu** | Open settings |
| Touchscreen | Navigation and actions |

---

## Troubleshooting

### balenaEtcher or Rufus does not recognize the file

Extract the `.zst` first and select the resulting `.img` file.

### Windows asks me to format the card after flashing

Click **Cancel**. The card contains Linux partitions that Windows cannot read; this is normal.

### The console does not boot

- Verify the SHA-256 of the downloaded `.zst`.
- Extract again and reflash the **whole** card, not a partition.
- Try a different microSD card (32 GB recommended) and card reader.
- Make sure you selected the correct device in Rufus/Etcher.

### I updated but I still see the old version

Open **Settings → Update** and check again. If it says “offline”, verify WiFi and try later. You can also reboot and check again.

---

## Notes

GeminusOS is an independent project and is not affiliated with Anbernic. It does not include games, ROMs or BIOS files. Only use content you legally own. Third-party components keep their original licenses.
