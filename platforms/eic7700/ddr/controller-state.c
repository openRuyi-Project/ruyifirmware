/* SPDX-License-Identifier: Apache-2.0 */
/*
 * Copyright 2024 Beijing ESWIN Computing Technology Co., Ltd.
 * Copyright 2026 Han Gao <gaohan@iscas.ac.cn>
 */
#include "common.h"

/* DWC_ddrctl byte offsets in the EIC7700 controller aperture. */
#define DDRC_DQSOSCCTL0		0x00a80
#define DDRC_STAT		0x10014
#define DDRC_MRSTAT		0x10090
#define DDRC_DERATECTL0		0x10100
#define DDRC_PWRCTL		0x10180
#define DDRC_RFSHCTL0		0x10208
#define DDRC_DFIMISC		0x10510
#define DDRC_DFISTAT		0x10514
#define DDRC_SWCTL		0x10c80
#define DDRC_SWSTAT		0x10c84

static void wait32(u32 address, u32 mask, u32 value)
{
	while ((ddr_read32(address) & mask) != value)
		;
}

/*
 * SWCTL.sw_done brackets a quasi-dynamic update. SWSTAT acknowledges
 * propagation to the controller clock domain before the next operation.
 */
static void set_dfi(u32 base, u32 value)
{
	ddr_write32(base + DDRC_SWCTL, 0x00000000);
	ddr_write32(base + DDRC_DFIMISC, value);
	ddr_write32(base + DDRC_SWCTL, 0x00000001);
	wait32(base + DDRC_SWSTAT, ~0U, 0x00000001);
}

int ddr_controllers_prepare_training(u32 controller0,
				     enum ddr_memory_profile memory)
{
	if ((unsigned int)memory > DDR_LPDDR5_32GB)
		return -1;
	for (unsigned int channel = 0; channel < 2; channel++) {
		u32 base = controller0 + channel * 0x80000U;

		ddr_write32(base + DDRC_RFSHCTL0, 0x00000001);
		if (memory == DDR_LPDDR4X) {
			/* Both writes are present in the reference sequence. */
			ddr_write32(base + DDRC_PWRCTL, 0x00020000);
			ddr_write32(base + DDRC_PWRCTL, 0x00020000);
		}
		ddr_write32(base + DDRC_DERATECTL0, 0x00000000);
		/*
		 * DFIMISC: channel mode=1, reset_n=1, active-high data CS.
		 * init_start and init_complete_en remain clear during PMU training.
		 */
		set_dfi(base, 0x00010014);
		ddr_write32(base + DDRC_RFSHCTL0, 0x00000000);
	}
	return 0;
}

int ddr_controllers_finish_training(u32 controller0,
				    enum ddr_memory_profile memory)
{
	if ((unsigned int)memory > DDR_LPDDR5_32GB)
		return -1;
	for (unsigned int channel = 0; channel < 2; channel++) {
		u32 base = controller0 + channel * 0x80000U;
		int lp4 = memory == DDR_LPDDR4X;

		/*
		 * Request PHY initialization with DFIMISC.init_start (bit 5).
		 * After DFISTAT acknowledges, lower the request, then enable the
		 * controller's initialization-complete path with bit 0.
		 */
		set_dfi(base, 0x00010034);
		wait32(base + DDRC_DFISTAT, ~0U, 0x00000001);
		set_dfi(base, 0x00010014);
		set_dfi(base, 0x00010015);
		if (lp4) {
			ddr_write32(base + DDRC_PWRCTL, 0x00020000);
			wait32(base + DDRC_STAT, ~0U, 0x00000001);
			ddr_write32(base + DDRC_DQSOSCCTL0, 0x00001194);
		} else {
			wait32(base + DDRC_DQSOSCCTL0, ~0U, 0x00000881);
			ddr_write32(base + DDRC_DQSOSCCTL0, 0x00000880);
		}
		/* Complete mode-register activity before the power-state transition. */
		wait32(base + DDRC_MRSTAT, ~0U, 0x00000000);
		ddr_write32(base + DDRC_PWRCTL, lp4 ? 0x00000a00 : 0x00000800);
		wait32(base + DDRC_STAT, 0x07U << 12, 0x02U << 12);
		ddr_write32(base + DDRC_PWRCTL, 0x00000000);
		/* STAT.operating_mode=1: normal controller operation. */
		wait32(base + DDRC_STAT, 0x07, 0x00000001);
		if (!lp4)
			ddr_write32(base + DDRC_RFSHCTL0, 0x00000000);
		ddr_write32(base + DDRC_DERATECTL0, 0x00000001);
		ddr_write32(base + DDRC_DQSOSCCTL0, lp4 ? 0x00001194 : 0x00000881);
	}
	return 0;
}
