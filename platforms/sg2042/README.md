# SG2042 SCP firmware

The build places `fip.bin` at offset `0x30000` on SPI1 and in the
root directory of the SD boot volume. Milk-V Pioneer and both SOPHGO
SG2042 evaluation boards use the same file.

Read the release version and TF-A commit ID from the binary with
`strings fip.bin | grep -F '(release):ruyi' | sort -u`.
