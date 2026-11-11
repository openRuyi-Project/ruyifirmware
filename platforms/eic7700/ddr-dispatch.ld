/* SPDX-License-Identifier: Apache-2.0 */
OUTPUT_ARCH(riscv)
ENTRY(_start)
SECTIONS
{
	. = 0;
	.entry : { KEEP(*(.entry)) }
	.header : {
		LONG(0x49595552) LONG(0x00524444) /* RUYIDDR\0 */
		LONG(1)
		LONG(_ddr_normal_start) LONG(_ddr_normal_end - _ddr_normal_start)
		LONG(_ddr_ecc_start) LONG(_ddr_ecc_end - _ddr_ecc_start)
		LONG(ddr_dispatch)
	}
	. = ALIGN(0x1000);
	.normal : { _ddr_normal_start = .; KEEP(*(.ddr.normal)) _ddr_normal_end = .; }
	. = ALIGN(0x1000);
	.ecc : { _ddr_ecc_start = .; KEEP(*(.ddr.ecc)) _ddr_ecc_end = .; }
	. = ALIGN(4);
	.text : { *(.text .text.*) }
	.rodata : { *(.rodata .rodata.*) }
	.data : { *(.data .data.* .sdata .sdata.*) }
	.bss : { *(.bss .bss.* .sbss .sbss.* COMMON) }
	.got : { *(.got .got.*) }
	/DISCARD/ : { *(.comment .note* .eh_frame* .riscv.attributes) }
}
ASSERT(SIZEOF(.entry) == 4, "DDR entry must be one uncompressed jump")
ASSERT(SIZEOF(.data) == 0 && SIZEOF(.bss) == 0, "DDR dispatcher needs no data initialization")
ASSERT(SIZEOF(.got) == 0, "DDR dispatcher must not need address relocation")
ASSERT(ADDR(.text) >= _ddr_normal_end - _ddr_normal_start, "Normal DDR overwrites dispatcher")
ASSERT(ADDR(.text) >= _ddr_ecc_end - _ddr_ecc_start, "ECC DDR overwrites dispatcher")
ASSERT(. < 0x100000, "DDR stage exceeds its entry jump range")
