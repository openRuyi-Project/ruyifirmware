# Platform defaults

Platform Settings displays and edits persistent defaults for UEFI driver
emulation, PXE and HTTP Boot. Save changes and restart to apply them.
An existing valid UEFI override still takes priority over saved defaults.

Programs can supply optional UEFI variable overrides. Setup reports when
an override is present. Select Clear UEFI overrides and restart to use
the stored defaults. Restore Defaults reloads the stored values and
cancels pending edits.

K3, Unmatched, P550, Megrez and StarPro64 store defaults in two SPI
records. They can save defaults even without nonvolatile UEFI variables.

SG2042 stores defaults in the `PlatformDefaults` UEFI variable. Firmware
Update preserves it in the Ruyi variable partition. With RAM-backed
variables, changes last until reset.

CPU mode and DDR ECC appear on boards that support them. Save and
restart to apply a change. On P550, CPU mode controls whether Linux
can select 1.6 GHz on a board modified for a fixed 0.9 V CPU supply.

## Configure an installation image

On SG2042, set the defaults in UEFI Setup. On the other boards, use the
settings tool from the same release package as the image.
To inspect its defaults, run:

```sh
python3 settings.py normal-spi.bin
```

To create a copy with all three defaults disabled, run:

```sh
python3 settings.py normal-spi.bin --default-emulation disabled \
  --default-pxe disabled --default-http disabled --output-dir configured
```

The command writes the configured image and its SHA256SUMS file. It leaves
the input image unchanged. Options that you omit keep their existing
default value.

## First installation

On SG2042, boot the recovery SD card and install the SPI image through
Firmware Update. Follow the kernel upgrade instructions in the package
before booting the card on Pioneer. Start the installed firmware before
saving persistent defaults.

On the five boards listed below, reflash once when moving from the old
platform record format. Use the installation guide for your board.

- [K3](k3/INSTALL.txt): use BootROM recovery, then `fastboot flash spi`.
- [Megrez](megrez/INSTALL.txt): start UEFI from the USB recovery disk,
  then write the image to SPI with Firmware Update or USB Fastboot.
- [StarPro64](starpro64/INSTALL.txt): start UEFI through USB recovery,
  then install the image with Firmware Update.
- [Unmatched](unmatched/INSTALL.txt): program the image through JTAG.
- [P550](p550/INSTALL.txt): use UART/JTAG recovery, then Firmware Update.
  The updater installs the image defaults when no valid records exist.

Keep tools and firmware from one package. Release images start with
emulation enabled and network boot disabled unless you change the image.

Unmatched retains UEFI variables outside the installation image. Clear
UEFI overrides in Setup if you want to use the installed defaults.

## Later updates

Normal Firmware Update and Fastboot firmware updates preserve valid
defaults already stored on the board. Changing the defaults in an update
image does not replace them. Change installed defaults in Setup, or use
a program that calls the platform settings protocol.

Firmware Update requires normal-spi.bin and its matching SHA256SUMS in
the same directory on every board. It checks the image before writing and
verifies the written data. CPU settings and ECC selections are retained
when valid. DDR training caches are regenerated after a K3 firmware update.
