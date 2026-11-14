/* SPDX-License-Identifier: Apache-2.0 */
/*
 * Copyright 2024 Beijing ESWIN Computing Technology Co., Ltd.
 * Copyright 2026 Han Gao <gaohan@iscas.ac.cn>
 * EIC7700 board DQ lane mappings.
 */
#include "common.h"

/* LPDDR4X programs byte lanes 0, 1, 3, 2. LPDDR5 uses 0, 1, 2, 3. */
static const u8 lp4_byte_order[] = {0, 1, 3, 2};
/*
 * Dimensions: wiring profile, PHY instance, byte lane, DQ bit.
 * These are board wiring permutations, applied before PMU training.
 */
static const u8 lane_maps[4][2][4][8] = {
	{ /* LPDDR4X */
		{
			{5, 4, 7, 6, 1, 0, 2, 3},
			{1, 5, 0, 2, 7, 6, 4, 3},
			{3, 2, 1, 0, 7, 6, 4, 5},
			{6, 4, 5, 7, 0, 1, 2, 3},
		},
		{
			{5, 4, 7, 6, 1, 0, 2, 3},
			{3, 2, 1, 0, 7, 6, 4, 5},
			{3, 2, 1, 0, 7, 6, 4, 5},
			{5, 4, 6, 7, 0, 1, 2, 3},
		},
	},
	{ /* LPDDR5 */
		{
			{4, 2, 7, 5, 3, 1, 0, 6},
			{2, 5, 0, 1, 3, 6, 4, 7},
			{5, 4, 7, 6, 3, 2, 1, 0},
			{2, 4, 1, 3, 5, 7, 6, 0},
		},
		{
			{4, 2, 7, 5, 3, 1, 0, 6},
			{1, 3, 0, 2, 4, 7, 5, 6},
			{7, 5, 6, 4, 2, 3, 0, 1},
			{3, 5, 0, 2, 4, 6, 7, 1},
		},
	},
	{ /* LPDDR5 D2D */
		{
			{4, 3, 6, 5, 2, 0, 1, 7},
			{2, 1, 0, 5, 3, 6, 4, 7},
			{6, 2, 7, 5, 3, 4, 1, 0},
			{1, 3, 0, 5, 4, 7, 6, 2},
		},
		{
			{0, 3, 5, 7, 6, 4, 2, 1},
			{2, 1, 0, 3, 5, 6, 4, 7},
			{6, 5, 4, 7, 3, 1, 2, 0},
			{2, 6, 1, 3, 7, 5, 4, 0},
		},
	},
	{ /* LPDDR5 NX 16 GiB */
		{
			{3, 1, 2, 0, 5, 4, 6, 7},
			{2, 5, 0, 1, 3, 6, 4, 7},
			{5, 4, 7, 6, 3, 2, 1, 0},
			{7, 6, 5, 4, 3, 0, 1, 2},
		},
		{
			{0, 2, 5, 4, 3, 1, 6, 7},
			{1, 3, 0, 2, 4, 7, 5, 6},
			{7, 6, 5, 4, 3, 2, 1, 0},
			{7, 6, 5, 4, 3, 1, 0, 2},
		},
	},
};

int ddr_phy_configure_lanes(u32 phy, enum ddr_memory_profile memory,
			    unsigned int channel, int nx, int d2d)
{
	unsigned int map;

	if (channel >= 2 || (unsigned int)memory > DDR_LPDDR5_32GB)
		return -1;
	if (memory == DDR_LPDDR4X)
		map = 0;
	else if (d2d)
		map = 2;
	else if (nx && memory == DDR_LPDDR5_16GB)
		map = 3;
	else
		map = 1;

	for (unsigned int byte = 0; byte < 4; byte++) {
		unsigned int index = map == 0 ? lp4_byte_order[byte] : byte;

		/*
		 * DBYTE Dq0LnSel starts at word 0x10080. Adjacent byte lanes
		 * are 0x1000 words apart, hence the 0x2000-byte stride.
		 */
		for (unsigned int bit = 0; bit < 8; bit++)
			ddr_write16(phy + 0x20100 + index * 0x2000 + bit * 2,
				    lane_maps[map][channel][byte][bit]);
	}
	return 0;
}
