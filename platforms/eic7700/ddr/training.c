/* SPDX-License-Identifier: Apache-2.0 */
/*
 * Copyright 2024 Beijing ESWIN Computing Technology Co., Ltd.
 * Copyright 2026 Han Gao <gaohan@iscas.ac.cn>
 */
#include "common.h"

/*
 * SCPU orchestration for two DWC_ddrctl / LPDDR PHY instances.
 * PHY0 and PHY1 are 0x800000 bytes apart. DDRC0 and DDRC1 are 0x80000
 * bytes apart. The channel index here selects an instance, not a DFI
 * subchannel or a byte lane inside a PHY.
 */

int ddr_train(const struct ddr_device *device, const struct ddr_training_log *log,
	      struct ddr_training_result *result)
{
	static const u16 rates[] = {4266, 6400, 6400};
	static const u8 sizes[] = {16, 16, 32};
	u8 d2d = 0;

	/*
	 * The reference tries LPDDR4X, LPDDR5 16 GiB and LPDDR5 32 GiB,
	 * then repeats that order, for at most nine training attempts.
	 */
	for (unsigned int attempt = 0; attempt < 9; attempt++) {
		enum ddr_memory_profile memory = attempt % 3;
		int status = 0;

		/* Reapply clocks, controller settings and reset for each attempt. */
		d2d |= ddr_reset_and_detect_d2d(device->syscrg, device->die_count);
		if (ddr_set_data_rate(device->syscrg, rates[memory]))
			return -1;
		ddr_configure_controllers(device->controller0, memory, device->ecc);
		/* ESWIN ddr_rst_ctrl assertion/release sequence. */
		ddr_write32(device->syscrg + 0x410, 0x07200300);
		ddr_write32(device->syscrg + 0x410, 0x07ff035f);
		ddr_controllers_prepare_training(device->controller0, memory);

		/* Apply board DQ wiring before loading the PHY training program. */
		for (unsigned int channel = 0; channel < 2; channel++)
			ddr_phy_configure_lanes(device->phy0 + channel * 0x800000U,
					memory, channel, device->nx, d2d);
		for (unsigned int channel = 0; channel < 2; channel++) {
			u32 phy = device->phy0 + channel * 0x800000U;

			/* DBYTE TxModeCtlSE0, word register 0x10030. */
			ddr_write16(phy + 0x20060, 0x0002);
			ddr_write16(phy + 0x20060, 0x0003);
		}
		for (unsigned int channel = 0; channel < 2; channel++)
			ddr_phy_prepare(device->phy0 + channel * 0x800000U, memory);
		for (unsigned int channel = 0; channel < 2; channel++)
			ddr_phy_load_training(device->phy0 + channel * 0x800000U, memory);
		/*
		 * Each PMU executes its retained microcode. The SCPU waits on
		 * that PHY's mailbox before starting the next instance.
		 */
		for (unsigned int channel = 0; channel < 2; channel++) {
			u32 phy = device->phy0 + channel * 0x800000U;

			ddr_phy_start_training(phy, memory);
			status = ddr_phy_wait_training(phy, channel, log);
			if (status)
				break;
		}
		/*
		 * Stall both PMUs and read their message blocks on success or
		 * failure. A failed attempt restarts at the next memory profile.
		 */
		for (unsigned int channel = 0; channel < 2; channel++)
			ddr_phy_stop_training(device->phy0 + channel * 0x800000U);
		for (unsigned int channel = 0; channel < 2; channel++)
			ddr_phy_read_training_result(device->phy0 + channel * 0x800000U, 0);
		if (status)
			continue;

		/*
		 * Install post-training settings and the PHY Init Engine (PIE)
		 * sequence before the controller/PHY DFI completion handshake.
		 */
		for (unsigned int channel = 0; channel < 2; channel++)
			ddr_phy_finish_training(device->phy0 + channel * 0x800000U, memory);
		ddr_controllers_finish_training(device->controller0, memory);
		result->memory = memory;
		result->size_gib = sizes[memory];
		result->rate = rates[memory];
		result->d2d = d2d;
		return 0;
	}

	/* Never report usable memory after every profile failed training. */
	return -1;
}
