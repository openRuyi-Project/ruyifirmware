# SOPHGO SG2042

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
