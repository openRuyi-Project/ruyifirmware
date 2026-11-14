/* SPDX-License-Identifier: Apache-2.0 */
/*
 * Copyright 2024 Beijing ESWIN Computing Technology Co., Ltd.
 * Copyright 2026 Han Gao <gaohan@iscas.ac.cn>
 *
 * EIC7700 SCPU DDR control and PHY mailbox.
 * These routines retain the reference access widths, ordering and polling.
 */
#include "common.h"

/* ESWIN die, clock and reset controls, outside the Synopsys DDR blocks. */
#define SYSCRG_DIE_INFO		0x51828308U
#define SYSCRG_DDR_PLL0		0x78
#define SYSCRG_DDR_PLL1		0x7c
#define SYSCRG_DDR_PLL2		0x80
#define SYSCRG_PLL_STATUS	0xa4
#define SYSCRG_DDR_RESET	0x410
#define DDR_PLL_LOCKED		(1U << 6)
#define D2D_PLL_LOCKED		(1U << 7)
#define DDR_RESET_ASSERT	0x07200300U

/*
 * Synopsys APBONLY mailbox, expressed as EIC7700 byte offsets:
 * UctShadowRegs (0xd0004), DctWriteProt (0xd0031),
 * UctWriteOnlyShadow (0xd0032), UctDatWriteOnlyShadow (0xd0034).
 * STATUS bit 0 is clear when the PMU has a message ready for the host.
 */
#define PHY_MESSAGE_STATUS	0x1a0008U
#define PHY_MESSAGE_ACK		0x1a0062U
#define PHY_MESSAGE_LOW		0x1a0064U
#define PHY_MESSAGE_HIGH	0x1a0068U
#define PHY_MESSAGE_BUSY	0x01U

u32 ddr_read_die_info(struct ddr_die_info *info, int probe_second_die)
{
	u32 value = ddr_read32(SYSCRG_DIE_INFO);

	info->count = value >> 16;
	info->ordinal = value >> 8;
	if (probe_second_die) {
		value = ddr_read32(SYSCRG_DIE_INFO + 0x20000000U);
		info->count = value >> 16;
		info->ordinal = value >> 8;
	}
	return value;
}

u32 ddr_die_offset(u8 ordinal)
{
	return ordinal ? 0x20000000U : 0;
}

u8 ddr_reset_and_detect_d2d(u32 syscrg, u8 die_count)
{
	u8 d2d = 0;
	u32 status;

	ddr_write32(syscrg + SYSCRG_DDR_RESET, DDR_RESET_ASSERT);
	do {
		status = ddr_read32(syscrg + SYSCRG_PLL_STATUS);
		if (status & D2D_PLL_LOCKED)
			d2d = 1;
	} while (!(status & DDR_PLL_LOCKED));

	/* Normal mode uses the die count. NX and ECC paths pass zero. */
	if (die_count > 1)
		d2d = 1;
	return d2d;
}

/* rate is the memory data rate in MT/s, not a PLL frequency in MHz. */
int ddr_set_data_rate(u32 syscrg, u32 rate)
{
	u32 cfg0, cfg1 = 0x00000000;
	int write_cfg1 = 0;

	switch (rate) {
	case 1066:
		cfg0 = 0x02c01300;
		cfg1 = 0x05555552;
		write_cfg1 = 1;
		break;
	case 1600:
	case 3200:
		cfg0 = 0x08501300;
		cfg1 = 0x05555552;
		write_cfg1 = 1;
		break;
	case 5500:
		cfg0 = 0x0e501300;
		cfg1 = 0x02aaaaa2;
		write_cfg1 = 1;
		break;
	case 6000:
		cfg0 = 0x0fa01300;
		cfg1 = 0x00000002;
		write_cfg1 = 1;
		break;
	case 6400:
		cfg0 = 0x10a01300;
		break;
	case 0:
		ddr_write32(syscrg + SYSCRG_DDR_PLL0, 0x0b101300);
		ddr_write32(syscrg + SYSCRG_DDR_PLL0, 0x0b1013f1);
		goto wait_lock;
	case 4266:
		/* Keep the BootROM's PLL configuration, as the reference does. */
		goto wait_lock;
	default:
		/* Caller must reject unsupported rates before starting training. */
		return -1;
	}

	ddr_write32(syscrg + SYSCRG_DDR_PLL0, cfg0);
	if (write_cfg1)
		ddr_write32(syscrg + SYSCRG_DDR_PLL1, cfg1);
	if (rate == 1600)
		ddr_write32(syscrg + SYSCRG_DDR_PLL2, 0x00000104);
	ddr_write32(syscrg + SYSCRG_DDR_PLL0, cfg0 | 0x01U);
wait_lock:
	while (!(ddr_read32(syscrg + SYSCRG_PLL_STATUS) & DDR_PLL_LOCKED))
		;
	return 0;
}

u32 ddr_phy_read_message(u32 phy, u8 stream)
{
	u32 value;

	/* Receive before acknowledging. Stream words combine two halfwords. */
	while (ddr_read16(phy + PHY_MESSAGE_STATUS) & PHY_MESSAGE_BUSY)
		;
	value = ddr_read16(phy + PHY_MESSAGE_LOW);
	if (stream)
		value |= (u32)ddr_read16(phy + PHY_MESSAGE_HIGH) << 16;
	/* Acknowledge this word, wait for the PMU response, then release ACK. */
	ddr_write16(phy + PHY_MESSAGE_ACK, 0x0000);
	while (!(ddr_read16(phy + PHY_MESSAGE_STATUS) & PHY_MESSAGE_BUSY))
		;
	ddr_write16(phy + PHY_MESSAGE_ACK, 0x0001);
	return value;
}

int ddr_phy_wait_training(u32 phy, u32 controller,
			  const struct ddr_training_log *log)
{
	u32 progress = 0;

	for (;;) {
		u32 message = ddr_phy_read_message(phy, 0);

		switch (message) {
		case 0x07: /* PMU training completed successfully. */
			if (log && log->progress)
				log->progress(controller, 100);
			return 0;
		case 0xff: /* PMU reports training failure. */
			return -1;
		case 0x08: {
			u32 stream = ddr_phy_read_message(phy, 1);

			/*
			 * The upper 16 bits contain the ID, the lower 16 the word count.
			 * Drain all words before reading the next status message.
			 */
			if (log && log->stream) {
				log->stream(stream >> 16, (u16)stream, phy);
			} else {
				for (u32 i = 0; i < (u16)stream; i++)
					ddr_phy_read_message(phy, 1);
			}
			break;
		}
		default:
			/* Reference UI estimate. Only message 0x07 confirms completion. */
			progress += 6;
			if (progress > 100)
				progress = 100;
			if (log && log->progress)
				log->progress(controller, progress);
			break;
		}
	}
}
