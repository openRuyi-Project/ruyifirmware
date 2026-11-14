# EIC7700 SCPU initialization

`sys-init.c` replaces the small system-initialization binary supplied by
ESWIN as `sys/sys_init.bin` and by SiFive as `second_boot_fw.bin`.
It runs on the RV32 SCPU before the separate DDR firmware.

BootROM supplies the stack and return address. The entry returns zero.
The image uses no initialized writable data, BSS or address relocations.
The same image runs at `0x59000000` for SPI boot and `0x30008000` for UART
recovery.

The implementation preserves the reference PLL, UART and fan PWM access
sequence. It also preserves the reference wait behavior and the die-0
PLL selection. The die ID selects the UART and fan register bank.
It does not initialize DDR or change PCIe configuration.

Reference binary:

- [ESWIN sys_init.bin](https://github.com/eswincomputing/Esbd-77serial-firmware/blob/8ad2177026e982acc0e14ef1e9ebe682aff6dfca/sys/sys_init.bin)
- SHA256: `7d10fd7aa4b0b5924daec199be00ab6d76515115e19f46c69e0b2ad665f7a744`

The reconstructed stage and linker script use Apache-2.0. See `LICENSE`.
The DDR build is described in [`ddr/`](ddr/README.md).

Boards that use these stages call `tools/eic7700/prepare-inputs.py` during
the build. It writes `sys-init.bin` and `sys-init.elf` to the selected
build directory.

## DDR program

`tools/eic7700/prepare-inputs.py` also builds the shared
[DDR program](ddr/README.md). Its SPI entry reads the two CRC-protected
ECC policy slots. Its UART entry forces non-ECC mode. Both entries use
the same training and PHY code. The policy format is shared with EDK2
through `Eic7700BootConfig.h`.

Board wiring is selected from the firmware DTB's `compatible` property
at build time. See the [P550 guide](../../docs/p550/README.md) for build
and ECC configuration instructions.

## Reference comparison

Build a host Unicorn library with its RISC-V backend. Compile
`tools/eic7700/tests/sys-init-trace.c` against that library. Pass the reference
binary and the newly built `sys-init.bin` to the test executable.

The test compares MMIO reads, writes, I/O fences and UART output at both
load addresses. It checks the return value and preserved ABI registers.
Cases cover die selection, an initially unlocked PLL, delayed PLL lock
and UART backpressure. This models register behavior, not hardware timing.
