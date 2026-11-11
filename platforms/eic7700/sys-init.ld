/* SPDX-License-Identifier: Apache-2.0 */
OUTPUT_ARCH(riscv)
ENTRY(scpu_sys_init)
SECTIONS
{
	. = 0;
	.text : { KEEP(*(.text.entry)) *(.text .text.*) }
	.rodata : { *(.rodata .rodata.*) }
	.data : { *(.data .data.* .sdata .sdata.*) }
	.bss : { *(.bss .bss.* .sbss .sbss.* COMMON) }
	.got : { *(.got .got.*) }
	/DISCARD/ : { *(.comment .note* .eh_frame* .riscv.attributes) }
}
ASSERT(scpu_sys_init == 0, "SCPU entry must be the first instruction")
ASSERT(SIZEOF(.data) == 0 && SIZEOF(.bss) == 0, "SCPU stage needs no data initialization")
ASSERT(SIZEOF(.got) == 0, "SCPU stage must not need address relocation")
ASSERT(. <= 0x4000, "SCPU stage overlaps the UART boot table")
