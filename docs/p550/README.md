# SiFive HiFive Premier P550

Ruyi Firmware boots the EIC7700 through coreboot, OpenSBI and EDK2.
Use the package for your board. DEBUG and RELEASE packages use the same
installation procedure.

See [INSTALL.txt](INSTALL.txt) for SPI updates and UART/JTAG recovery.
The 8 MiB SPI image fits boards with either 8 MiB or 16 MiB flash.

Connect the FT4232 console channel C at 115200 baud, 8N1, with no flow
control. Press F2 for Setup or F12 for the boot menu. A compatible PCIe
graphics card can provide the graphical console.

See [PCIe power checks](pcie-power.md) if a card fails to establish a link.

SATA disks are available in the boot menu and UEFI Shell.

Platform Settings controls UEFI driver emulation, PXE and HTTP Boot.
Driver emulation is enabled by default. PXE and HTTP Boot are disabled
by default. Save changes and restart to apply them.

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

Board information and schematics are available from
[SiFive](https://www.sifive.com/boards/hifive-premier-p550).
