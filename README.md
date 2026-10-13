# Ruyi Firmware

Firmware based on coreboot, OpenSBI and EDK2.
Currently supports SpacemiT K3 Pico ITX.

Build on Ubuntu 26.04:

```sh
git clone --recurse-submodules https://github.com/openRuyi-Project/ruyifirmware.git
cd ruyifirmware
sudo bash ci/install-deps.sh
make package                                      # x64emu RELEASE
make package TARGET=DEBUG                         # x64emu DEBUG
make package X64EMU_ENABLE=FALSE                   # no-x64emu RELEASE
make package X64EMU_ENABLE=FALSE TARGET=DEBUG       # no-x64emu DEBUG
```

Outputs: `dist/{x64emu,no-x64emu}/{DEBUG,RELEASE}/`.
Build files use the same variant and target layout under `build/`.

`x64emu` runs compatible x64 UEFI option ROMs, including discrete GPU GOP
drivers. `no-x64emu` omits the emulator; a discrete GPU that needs an x64
GOP has no firmware display and relies on its operating system driver.
Native K3 display support is present in both variants.

The tested RX550 GOPs truncate pointers and fault during initialization
on K3, preventing UEFI/GRUB display. Use `no-x64emu` for RX550 and
`x64emu` for RX6400.

[K3 Pico ITX flashing](docs/k3/INSTALL.txt)
