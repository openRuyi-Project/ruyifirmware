/* SPDX-License-Identifier: Apache-2.0 */
/* Copyright 2026 Han Gao <gaohan@iscas.ac.cn> */
#include "common.h"

#ifdef P550_GPIO_CPU_RATE
#include "../cpu-clock.h"

#define GPIO_BASE          0x51600000U
#define GPIOC_OUTPUT       (GPIO_BASE + 0x18)
#define GPIOC_DIRECTION    (GPIO_BASE + 0x1c)
#define GPIOC_INPUT        (GPIO_BASE + 0x58)
#define S_MODE_PAD         (GPIO_BASE + 0x80 + 141 * 4)
#define CPU_VSEL           (1U << 30)  /* GPIO94 on port C */
#define PAD_FUNC_MASK      (7U << 16)
#define PAD_PULL_MASK      (3U << 1)
#define PAD_FUNC_GPIO      (2U << 16)
#define PAD_INPUT_ENABLE   1U

static void select_cpu_voltage(void)
{
	/* Preload GPIO94 before connecting it to the regulator on S_MODE. */
	write32(GPIOC_OUTPUT, read32(GPIOC_OUTPUT) | CPU_VSEL);
	write32(GPIOC_DIRECTION, read32(GPIOC_DIRECTION) | CPU_VSEL);
	write32(S_MODE_PAD, (read32(S_MODE_PAD) & ~(PAD_FUNC_MASK | PAD_PULL_MASK)) |
		PAD_FUNC_GPIO | PAD_INPUT_ENABLE);
}
#endif

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
#ifdef P550_GPIO_CPU_RATE
	/* Train at the boot clock while the 0.9 V CPU supply settles. */
	select_cpu_voltage();
#endif
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
#ifdef P550_GPIO_CPU_RATE
	if (!(read32(GPIOC_INPUT) & CPU_VSEL) || !set_cpu_clock(P550_GPIO_CPU_RATE))
		PRINT("CPU clock change failed, keeping fallback clock\r\n");
#endif
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
