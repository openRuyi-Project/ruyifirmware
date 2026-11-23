# SiFive HiFive Unmatched

Ruyi Firmware provides UEFI boot and setup for HiFive Unmatched A00.
It supports NVMe and USB storage, USB keyboards and PCIe graphics.

Use the [JTAG guide](INSTALL.txt) to install firmware or run it from RAM.
Use RELEASE for normal operation and DEBUG for more diagnostic output.

## Build

On Ubuntu 26.04, run from the repository directory:

```sh
sudo bash ci/install-deps.sh
make BOARD=unmatched TARGET=RELEASE package
```

Use `TARGET=DEBUG` for a DEBUG package. Output is written to
`dist/unmatched/RELEASE/` or `dist/unmatched/DEBUG/`.

Use `normal-spi.bin` for SPI programming. Use `recovery-bootblock.bin`,
`recovery-jtag.rom` and the supplied OpenOCD scripts for RAM recovery.
Keep the files from one package together.

## Setup and updates

Press F2 for Setup or F12 for the boot menu. System Information shows the
CPU, memory, PCIe devices and storage.

The serial console uses TTYTERM at 115200 baud, 8N1, without flow control.
Use a terminal with xterm-compatible keys.
Setup uses an 80x25 character grid on both consoles. HDMI retains the
selected pixel resolution.

The release image enables UEFI driver emulation. Change its stored default
in Platform Settings,
then save and restart. Supported older AMD cards use the included ARM64
GOP 1.68. Other cards use their x64 UEFI driver. Older AMD card support is
experimental.

See [capture-card sample results](../display-testing.md) when testing
through a USB video capture device.

To update through Setup, copy `normal-spi.bin` and its `SHA256SUMS` to a FAT
USB drive or the NVMe EFI partition. Open Firmware Update, select the image
and confirm. Wait for verification before restarting. This method preserves
UEFI variables and platform settings.

## Network boot

PXE and HTTP Boot are included in every image. Their installation defaults
are disabled.
Open Platform Settings to enable either method. Save and restart to apply.
HTTP Boot supports `http://` URLs. HTTPS is not supported.

## Operating systems

Use an operating system built for RV64GC. Unmatched does not support
userspace that requires RISC-V vector instructions.

The default UEFI loader path is `\EFI\BOOT\BOOTRISCV64.EFI`.
For serial output, add `console=ttySIF0,115200 earlycon=sbi` to the Linux
command line.

See [Linux issues](../linux-issues.md) for the firmware framebuffer and PCIe
resource conflict and its workaround.

See [Platform defaults](../settings.md) for settings, optional overrides
and installation-image configuration.
