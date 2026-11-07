# SpacemiT K3

Ruyi Firmware provides UEFI boot and setup for the SpacemiT K3 Pico ITX.
It can boot from UFS, NVMe and USB storage.

See [installation instructions](INSTALL.txt) for flashing and USB RAM recovery.
See [EC updates](EC.txt) for embedded-controller firmware.

## Build

On Ubuntu 26.04, run:

```sh
git clone --recurse-submodules https://github.com/openRuyi-Project/ruyifirmware.git
cd ruyifirmware
sudo bash ci/install-deps.sh
make BOARD=k3 TARGET=RELEASE package
```

Use `TARGET=DEBUG` for more diagnostic output. Packages are written to
`dist/k3/RELEASE/` or `dist/k3/DEBUG/`. Use `normal-spi.bin` and
`recovery-bootrom.bin` from the same package.

## Setup

Press F2 for Setup, F9 for USB Fastboot or F12 for the boot menu.
System Information shows the CPU, memory, PCIe devices and storage.

The serial console uses TTYTERM at 115200 baud, 8N1, without flow control.
Use a terminal with xterm-compatible keys.

## CPU modes

Open Platform Settings and select a CPU mode:

| Mode | Cores | Vector support | Hypervisor support | CPU name |
| --- | --- | --- | --- | --- |
| X100 only (default) | 8 X100 | Enabled | Enabled | `k3` |
| X100 + A100 | 16 | Disabled | Disabled | `k3-x100-a100` |
| A100 only | 8 A100 | Enabled | Disabled | `k3-a100` |

Save and restart to apply the selection. The CPU name is available to
system information tools such as fastfetch.

X100 + A100 mode requires userspace that can run without vector instructions,
such as RV64GC. Do not use an RVA23U64 root filesystem in this mode.
Firmware updates restore X100 only.

## Graphics

UEFI driver emulation is enabled by default. Change it in Platform Settings,
then save and restart. To change the initial setting before flashing, use
`settings.py` as described in [INSTALL.txt](INSTALL.txt).

| Graphics device | UEFI display driver |
| --- | --- |
| Supported early GCN, Polaris and Vega M cards | Included AMD ARM64 GOP 1.68 |
| Other cards, including RX6400 | Card's x64 UEFI driver |

Support for older AMD cards is experimental. If a card has no firmware
picture, use the native K3 display output or the serial console.
Disabling emulation leaves PCIe graphics to the operating system driver.

The AMD driver is obtained from [AMD](https://www.amd.com/en/resources/support-articles/release-notes/RN-AAR.html).
For an offline build, put `Arm64Gop_1_68.efi` in a directory and set
`AMD_GOP_DIR` to that directory.

## Network boot

PXE and HTTP Boot are included in every image and disabled by default.
Open Platform Settings to enable either method. Save and restart to apply.
HTTP Boot supports `http://` URLs. HTTPS is not supported.
Firmware updates load the network boot settings from the new image.

## Operating systems

SpacemiT vendor Linux is not supported.
Linux mainline support is provided on a best-effort basis.

See [Linux issues](../linux-issues.md) for the firmware framebuffer and PCIe
resource conflict and its workaround.
