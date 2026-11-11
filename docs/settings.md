# Platform defaults

Platform Settings displays and edits persistent defaults for UEFI driver
emulation, PXE and HTTP Boot. Save changes and restart to apply them.
An existing valid UEFI override still takes priority over saved defaults.

Programs can supply optional UEFI variable overrides. Setup reports when
an override is present. Select Clear UEFI overrides and restart to use
the stored defaults. Restore Defaults reloads the stored values and
cancels pending edits.

K3, Unmatched and P550 store defaults in SPI. Saving defaults does not
require nonvolatile UEFI variables. The storage interface also permits a
reserved eMMC boot area. A board that uses that storage needs its own
adapter and reserved layout.

CPU mode and DDR ECC appear only on boards that support those settings.
Their values are read during early startup. Changing them also requires
a restart.

## Configure an installation image

Use the settings tool from the same release package as the image.
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
the input image unchanged. The same command works for K3, Unmatched and
P550. Options that you omit keep their existing default value.

## First installation of this format

Old platform records are not migrated. Reflash once with this package.
Follow your board's installation guide:

- [K3](k3/INSTALL.txt): use BootROM recovery, then `fastboot flash spi`.
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
