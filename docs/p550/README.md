# SiFive HiFive Premier P550

Ruyi Firmware boots the EIC7700 through coreboot, OpenSBI and EDK2.
Use the package for your board. DEBUG and RELEASE packages use the same
installation procedure.

See [INSTALL.txt](INSTALL.txt) for SPI updates and UART/JTAG recovery.
The 8 MiB SPI image fits boards with either 8 MiB or 16 MiB flash.

Connect the FT4232 console channel C at 115200 baud, 8N1, with no flow
control. Press F2 for Setup or F12 for the boot menu. A compatible PCIe
graphics card can provide the graphical console.
Setup uses 80 columns and 25 rows on the serial console and the display.
On the display, the grid fills the selected GOP resolution.

See [capture-card sample results](../display-testing.md) when testing
through a USB video capture device.

See [PCIe power checks](pcie-power.md) if a card fails to establish a link.

SATA disks are available in the boot menu and UEFI Shell.

Platform Settings controls UEFI driver emulation, PXE and HTTP Boot.
Release images enable emulation and disable PXE and HTTP Boot.
Save changes and restart to apply them.

The P550 enters UEFI at 1.6 GHz. Linux can select up to 1.6 GHz by default.
The 1.6 and 1.8 GHz operating points both use 0.9 V. The Rev 3.0 SoM
schematic shows GPIO94 selecting this voltage through R643, Q15 and R640.
Check that these components are fitted on your module. A board modified
for fixed 0.9 V needs a device tree describing that fixed supply.

On the GPIO-equipped SoM, the SCPU selects 0.9 V before training DDR
and switches the CPU PLL from 1.4 to 1.6 GHz after the memory self-test.
To enable 1.8 GHz in Linux, select **Platform Settings > CPU mode >
Allow 1.8 GHz in Linux**, save and restart.

DDR ECC is disabled by default. Enable it in Platform Settings.
Save the change. Restart the board to apply it.
Inline ECC reserves one eighth of DDR capacity for
check bits. A 16 GiB board then provides 14 GiB before other reservations.
Firmware updates preserve this setting. UART/JTAG recovery uses non-ECC
DDR so you can change the setting if SPI boot fails.

For HTTP Boot, enable it in Platform Settings. Open Device Manager,
Network Device List, select a port, then open HTTP Boot Configuration.
Enter the image URL and save. Select the new entry in Boot Manager.
HTTP Boot supports `http://` URLs. Use an EFI executable with an `.efi`
suffix, or an ISO image with an `.iso` suffix. For a kernel file named
`Image`, configure the server to send `Content-Type: application/efi`.

The dual-role USB-A port uses host mode during normal operation.
Enter USB Fastboot before connecting its download cable to another
computer. Disconnect that cable before pressing Esc to leave Fastboot.
The port then returns to host mode.

Fastboot exposes eMMC as `mmc0`, its boot areas as `mmc0boot0` and
`mmc0boot1`, and the SD card as `mmc1`. The eMMC boot areas remain
accessible in the UEFI Shell but do not appear as automatic boot entries.

See [Linux issues](../linux-issues.md) if the kernel reports a firmware
framebuffer conflict with the PCIe host bridge.

The firmware package lists its Linux device tree revision in
`source-revisions.txt`. The P550 device tree uses `pwm-fan` to control
the fan and `eic7700-fan` to read its speed. The operating system needs
both drivers and a DWC PWM driver that supports normal polarity.

Board information and schematics are available from
[SiFive](https://www.sifive.com/boards/hifive-premier-p550).

See [Platform defaults](../settings.md) for settings, optional overrides
and installation-image configuration.

## Build from source

Install the [build dependencies](https://github.com/openRuyi-Project/ruyifirmware/blob/ruyi/ci/install-deps.sh).
From the repository root, run:

```sh
make BOARD=p550 prepare
make BOARD=p550 TARGET=RELEASE package
```

To build packages for P550, Megrez and StarPro64 together, run
`make BOARD=eic7700 TARGET=RELEASE package`. The three images use one
EDK II payload. Coreboot passes the board's device tree to UEFI.

Each package is written to `dist/<board>/RELEASE`. For P550 installation
and UART/JTAG recovery, follow [INSTALL.txt](INSTALL.txt).

The build compiles one DDR program for normal and ECC operation. It reads
`sifive,hifive-premier-p550` from the firmware DTB's root `compatible`
property to select P550 memory wiring. The `model` property is a display
name. ECC is selected at boot from the setting saved in UEFI Setup.
Each boot trains memory. With ECC enabled, it also initializes memory
and check bits.

The build retains the supplied PHY microcode and reference code for
register setup, UART output and memory checks. See [DDR sources and licensing](https://github.com/openRuyi-Project/ruyifirmware/tree/ruyi/platforms/eic7700/ddr).
