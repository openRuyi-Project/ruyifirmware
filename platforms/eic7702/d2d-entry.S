/* SPDX-License-Identifier: MIT */
/* Enter D2D 1.66 after the EBC7702-D01 SYS and DDR stages. */
#ifndef DIE
#error "select die 0 or 1"
#elif DIE == 0
#define SPRAM 0x59000000
#elif DIE == 1
#define SPRAM 0x79000000
#else
#error "select die 0 or 1"
#endif
#define SYS_BOARD_TYPE  (SPRAM + 0x2ff000)
#define D2D_BOARD_TYPE  (SPRAM + 0x3ffe00)

	.section .text.d2d_entry,"ax",@progbits
	.option norvc
	.option norelax
	.global d2d_entry
d2d_entry:
	/* The vendor entry overwrites a0 and a2 before using either. */
	lui	a0, %hi(SYS_BOARD_TYPE)
	lw	a2, %lo(SYS_BOARD_TYPE)(a0)
	lui	a0, %hi(D2D_BOARD_TYPE)
	sw	a2, %lo(D2D_BOARD_TYPE)(a0)
	fence	rw, rw
	lui	a0, %hi(SPRAM)
	jr	a0
