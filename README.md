# Ruyi Firmware

Firmware based on coreboot, OpenSBI and EDK2.
Currently supports SpacemiT K3 Pico ITX.

Build on Ubuntu 26.04:

```sh
git clone --recurse-submodules https://github.com/openRuyi-Project/ruyifirmware.git
cd ruyifirmware
sudo bash ci/install-deps.sh
make                         # RELEASE
make TARGET=DEBUG
```

Outputs: `build/RELEASE/` or `build/DEBUG/`.
