# SOPHGO SG2042

One firmware image contains the device trees for three single-socket
SG2042 boards. The SCP initializes DRAM and releases the C920 harts.
Coreboot reads the board ID that the SCP records at `0x703001023c`.

| Board ID | Board | Device tree |
| --- | --- | --- |
| `0x02` | SOPHGO EVB v1 | `sg2042-evb-v1.dtb` |
| `0x03` | Milk-V Pioneer | `sg2042-milkv-pioneer.dtb` |
| `0x05` | SOPHGO EVB v2 | `sg2042-evb-v2.dtb` |

Coreboot loads the selected tree from CBFS and adds the installed memory
ranges and disabled CPU clusters. It passes the tree to OpenSBI and the
SG2042 EDK2 payload. EDK2 uses the tree for PCIe controller selection and
publishes it to the operating system. Coreboot stops on other board IDs,
including Pisces (`0x04`).

## EVB v2 display

The SOPHGO EVB v2 uses a Silicon Motion SM768 PCIe graphics controller.
With driver emulation enabled, the firmware can load an x64 UEFI GOP
from the controller's Option ROM if the ROM contains one.
**TODO:** integrate a native SM768 GOP.

## Pioneer kernel compatibility

Before booting this firmware on Pioneer, install and boot openRuyi Linux
`ruyi/v7.3.5-3` or a kernel with both the RISC-V EFI runtime MMIO fix and
the SG2042 reserved-device clock fix. Older kernels can panic when
`rtc-efi` first reads the clock. Enable `CONFIG_RTC_DRV_EFI` for Linux
access to the DS1307. The driver registers the RTC after its first
successful time read. If the clock has stopped, check its backup supply
and set a valid date and time before updating the firmware.

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
| DS1307 RTC | UEFI owns I2C0 and provides runtime time services. Linux reads and sets the clock through `rtc-efi`. |
| SPI flash | Setup updates SPI1. UEFI stores persistent variables in `ruyi-vars` on SPI1. SPI0 is available to Linux. |
| Serial console and power control | OpenSBI provides the debug console, reset and shutdown services. The SCP and board MCU handle power sequencing. |

Linux uses the handed-off DT for GPIO, fan control, sensors and the MCU.
The M.2 E-key connector exposes PCIe and USB. Preboot network support
depends on the installed card.

The Pioneer Box can also contain an Intel X540-T2. A card with an x64
UEFI network Option ROM can use the firmware emulator. **TODO:** add
Intel's native XGigUndiDxe driver for the X540.

Build the firmware from the repository root:

```sh
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
