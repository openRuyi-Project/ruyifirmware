/* SPDX-License-Identifier: Apache-2.0 */
OUTPUT_ARCH(riscv)
ENTRY(ddr_entry)
SECTIONS
{
	/* Pinned reference programs and globals end below 0x59043000. */
	. = 0x59048000;
	_ddr_source_start = .;
	.text : { *(.text .text.*) }
	.rodata : { *(.rodata .rodata.* .srodata .srodata.*) }
	_ddr_source_end = .;
	.data : { *(.data .data.* .sdata .sdata.*) }
	.bss : { *(.bss .bss.* .sbss .sbss.* COMMON) }
	.got : { *(.got .got.* .igot .igot.*) }
	/DISCARD/ : { *(.comment .note* .eh_frame* .riscv.attributes) }
}
ASSERT(SIZEOF(.data) == 0 && SIZEOF(.bss) == 0, "DDR source needs no data initialization")
ASSERT(SIZEOF(.got) == 0, "DDR source must not need address relocation")
/* Keep the stage within the BootROM image reservation. */
ASSERT(_ddr_source_end <= 0x59100000, "DDR source exceeds its payload reservation")
