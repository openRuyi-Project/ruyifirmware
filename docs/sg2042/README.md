# SOPHGO SG2042

One firmware image contains the device trees for three single-socket
SG2042 boards. The SCP initializes DRAM and releases the C920 harts.
Coreboot reads the board ID that the SCP records at `0x703001023c`.

| Board ID | Board | Device tree |
| --- | --- | --- |
| `0x02` | SOPHGO EVB v1 | `sg2042-evb-v1.dtb` |
| `0x03` | Milk-V Pioneer | `sg2042-milkv-pioneer.dtb` |
| `0x05` | SOPHGO EVB v2 | `sg2042-evb-v2.dtb` |

The SCP reads the board identity from the MCU. On SD it opens the
matching file in `/riscv64/`. On SPI1 it looks for a partition with
that filename, then for the same file in the coreboot filesystem inside
`zsbl.bin`.

To supply a custom DTB for SCP PCIe setup, use the filename and root
compatible for your board. Coreboot selects its own copy from
`zsbl.bin` by board ID. It adds the installed memory ranges and disabled
CPU clusters and passes the tree to OpenSBI and EDK2. EDK2 publishes
the system device tree to the operating system. Coreboot stops on
other board IDs, including Pisces (`0x04`).

## EVB v2 display

The SOPHGO EVB v2 uses a Silicon Motion SM768 PCIe graphics controller.
With driver emulation enabled, the firmware can load an x64 UEFI GOP
from the controller's Option ROM if the ROM contains one.
**TODO:** integrate a native SM768 GOP.

## RTC

On Pioneer and both EVBs, UEFI reads the hardware clock once at boot on
I2C0, at address `0x68`. Pioneer uses a DS1307. Both EVBs use a
PT7C4307WE with the same calendar interface. UEFI initializes its
virtual clock from that reading. Later EFI time reads and writes use
the virtual clock. Linux can read and set the physical clock through
`rtc-ds1307`. Use the native RTC to change the time for the next boot.

If the hardware clock is stopped, the date is invalid, or the device
does not respond, the virtual clock starts at the last time saved by EFI SetTime. If no time
has been saved, it starts at the firmware build time. Check the RTC driver name in
`/sys/class/rtc/rtc*/name` to distinguish the physical clock from
`rtc-efi`.

I2C0 remains available to Linux on all three boards. On EVB v1 it also
serves the SMBus pins on PCIe slot 0. On EVB v2 it also serves the
ISL68127 voltage regulator. The EVB schematics label the RTC as U2001
and the I2C level shifter as U2003.

## Pioneer devices

| Hardware | UEFI driver or interface |
| --- | --- |
| ASM2824 PCIe switch and expansion slots | The SG2042 Cadence host driver publishes the enabled PCIe roots. PciBusDxe enumerates the bridges and endpoints. |
| Five SATA ports on the JMB585 | The EDK2 AHCI and ATA drivers use 32-bit DMA for this controller and publish Block I/O for attached disks. |
| Two M.2 M-key sockets | The EDK2 NVMe driver binds to NVMe drives. |
| USB 3 ports and front-panel header | The PCI xHCI and USB bus drivers support keyboards and mass storage. |
| microSD and eMMC module | The SG2042 driver configures the two DWC MSHC hosts. The SD and eMMC drivers use PIO for boot I/O. |
| Two 2.5 GbE ports | The native RTL8125B SNP driver uses each controller's own MAC address. EDK2 provides PXE and HTTP boot. |
| Display card | MultiArchUefiPkg can run supported EFI graphics drivers. A card with only a legacy video BIOS needs a compatible GOP to provide a UEFI display. |
| DS1307 RTC | UEFI samples the calendar at boot. Linux has native access to the RTC. |
| SPI flash | Setup updates SPI1. UEFI stores persistent variables in `ruyi-vars` on SPI1. SPI0 is available to Linux. |
| Serial console and power control | OpenSBI provides the debug console, reset and shutdown services. The SCP and board MCU handle power sequencing. |

Linux uses the handed-off DT for GPIO, fan control, sensors and the MCU.
The M.2 E-key connector exposes PCIe and USB. Preboot network support
depends on the installed card.

The Pioneer Box can also contain an Intel X540-T2. A card with an x64
UEFI network Option ROM can use the firmware emulator. **TODO:** add
Intel's native XGigUndiDxe driver for the X540.

## Build

Build on Ubuntu 26.04 with the distribution's RISC-V GCC. In release
`20261122`, its `libgcc.a` supplied a byte-swap routine that used
`rev8`. The C920 trapped on that instruction while reading the first
CBFS file header. The build now links coreboot with its own integer
helpers and omits the toolchain's `libgcc.a` from the coreboot stages.

From the repository root, run:

```sh
sudo bash ci/install-deps.sh
make BOARD=sg2042 prepare
make BOARD=sg2042 TARGET=RELEASE package
```

The package in `dist/sg2042/RELEASE/` contains both boot images.

| File | Use |
| --- | --- |
| `recovery-sd.img` | Write to a whole microSD card to boot the firmware from SD. |
| `normal-spi.bin` | Select in UEFI Setup under Firmware Update to install to SPI. |

Use `TARGET=DEBUG` for boot diagnostics. See [INSTALL.txt](INSTALL.txt)
for installation and for using an existing FAT32 card.
See the [Milk-V Pioneer hardware overview](https://milkv.io/docs/pioneer/overview)
and the [board schematic](https://github.com/milkv-pioneer/pioneer-files/tree/main/hardware)
for the board connections.
