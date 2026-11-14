/* SPDX-License-Identifier: Apache-2.0 */
/* Copyright 2026 Han Gao <gaohan@iscas.ac.cn> */
#include "common.h"

/* Offsets belong to the SHA256-pinned standard reference in ddr.py. */
#define REFERENCE_BASE		0x59000000U
#define GLOBALS			(REFERENCE_BASE + 0x428a8)
#define PRINT			((int (*)(const char *, ...))(REFERENCE_BASE + 0xa1c))
#define INIT_BANKS		((void (*)(u8))(REFERENCE_BASE + 0x1238))
#define SELF_CHECK		((int (*)(void))(REFERENCE_BASE + 0xe724))

int ddr_ecc_policy(void);

int ddr_boot(int ecc)
{
	struct ddr_die_info die;
	struct ddr_training_result result;
	struct ddr_device device;

	if (ecc < 0 || ecc > 1)
		return -1;
	/* Preserve the NX/ECC reference topology policy. */
	ddr_read_die_info(&die, DDR_BOARD_NX || ecc);
	INIT_BANKS(die.ordinal);
	device = (struct ddr_device) {
		ddr_read32(GLOBALS + 0x08), ddr_read32(GLOBALS + 0x0c),
		ddr_read32(GLOBALS + 0x14), (DDR_BOARD_NX || ecc) ? 0 : die.count,
		DDR_BOARD_NX, ecc
	};
	PRINT("DDR training: NX=%u ECC=%u\r\n", DDR_BOARD_NX, ecc);
	if (ddr_train(&device, 0, &result)) {
		PRINT("DDR training failed\r\n");
		return -1;
	}
	PRINT("DDR training passed: %u GiB, %u MT/s\r\n", result.size_gib, result.rate);
	if (ecc) {
		struct ddr_ecc_region region = {
			ddr_read32(GLOBALS + 0x2c), device.controller0,
			ddr_read32(GLOBALS + 0x24) + 0x280000U,
			ddr_read32(GLOBALS + 0x30), ddr_read32(GLOBALS + 0x34), result.size_gib
		};
		if (ddr_ecc_scrub(&region)) {
			PRINT("DDR ECC scrub failed\r\n");
			return -1;
		}
		PRINT("DDR ECC scrub passed\r\n");
	}
	if (SELF_CHECK()) {
		PRINT("DDR self test failed\r\n");
		return -1;
	}
	PRINT("DDR self test OK\r\n");
	return 0;
}

int ddr_entry(void)
{
	return ddr_boot(ddr_ecc_policy());
}

int ddr_recovery_entry(void)
{
	/* UART recovery must work independently of the saved SPI policy. */
	return ddr_boot(0);
}
