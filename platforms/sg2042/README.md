# SG2042 SCP firmware

`fip.bin` is a byte-for-byte copy of the
[SG2042 boot firmware from SOPHGO's edk2-non-osi repository](https://github.com/sophgo/edk2-non-osi/blob/7e74bf4c6002f69774505fde8ecf57c59886536f/Silicon/Sophgo/SG2042/Boot/fip.bin).
The build copies it to SPI offset `0x30000` and to the first FAT32
partition on SD for Pioneer and both EVBs.
