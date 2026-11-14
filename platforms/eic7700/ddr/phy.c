/* SPDX-License-Identifier: Apache-2.0 */
/*
 * Copyright 2024 Beijing ESWIN Computing Technology Co., Ltd.
 * Copyright 2026 Han Gao <gaohan@iscas.ac.cn>
 */
#include "common.h"

/*
 * Synopsys PHY word numbers 0xd0000 / 0xd0099 become byte offsets
 * 0x1a0000 / 0x1a0132 on EIC7700. All accesses below are 16-bit.
 */
#define PHY_APB_MUX		0x1a0000U
#define PHY_PMU_CONTROL		0x1a0132U

/* PMU instruction and data memories, at word numbers 0x50000 / 0x58000. */
#define PHY_IMEM		0x0a0000U
#define PHY_DMEM		0x0b0000U
#define PHY_MEMORY_WORDS	32768

/*
 * Three halfwords avoid padding and unaligned 32-bit table accesses.
 * offset_low | (offset_high << 16) is an already converted byte offset.
 */
struct phy_register {
	u16 offset_low;
	u16 offset_high;
	u16 value;
};

struct register_table {
	const struct phy_register *data;
	unsigned int count;
};

struct program {
	const u16 *data;
	unsigned int count;
};

struct phy_parameters {
	struct register_table prepare;		/* Initial PHY CSR writes. */
	struct program imem;			/* PMU training instructions. */
	struct register_table configure;	/* Profile CSR writes after IMEM. */
	struct program dmem;			/* PMU input data/message block. */
	struct register_table after_training;	/* Post-training CSR writes. */
	struct register_table pie;		/* PHY Init Engine sequence. */
};

#include "phy-data.inc"

static const struct phy_parameters *select_parameters(enum ddr_memory_profile memory)
{
	if ((unsigned int)memory > DDR_LPDDR5_32GB)
		return 0;
	return &parameters[memory];
}

static void write_table(u32 phy, const struct register_table *table)
{
	for (unsigned int i = 0; i < table->count; i++) {
		const struct phy_register *r = &table->data[i];
		u32 offset = r->offset_low | (u32)r->offset_high << 16;

		ddr_write16(phy + offset, r->value);
	}
}

static void write_program(u32 phy, u32 offset, const struct program *program)
{
	/* Clear the unused part of the 32768-halfword window on every load. */
	for (unsigned int i = 0; i < PHY_MEMORY_WORDS; i++)
		ddr_write16(phy + offset + i * 2,
			    i < program->count ? program->data[i] : 0x0000);
}

int ddr_phy_prepare(u32 phy, enum ddr_memory_profile memory)
{
	const struct phy_parameters *p = select_parameters(memory);

	if (!p)
		return -1;
	write_table(phy, &p->prepare);
	return 0;
}

int ddr_phy_load_training(u32 phy, enum ddr_memory_profile memory)
{
	const struct phy_parameters *p = select_parameters(memory);

	if (!p)
		return -1;
	write_program(phy, PHY_IMEM, &p->imem);
	write_table(phy, &p->configure);
	return 0;
}

int ddr_phy_start_training(u32 phy, enum ddr_memory_profile memory)
{
	const struct phy_parameters *p = select_parameters(memory);

	if (!p)
		return -1;
	/* MicroContMuxSel=0 gives the host APB access while loading DMEM. */
	ddr_write16(phy + PHY_APB_MUX, 0x0000);
	write_program(phy, PHY_DMEM, &p->dmem);
	ddr_write16(phy + PHY_APB_MUX, 0x0001);
	/* Preserve the reference MUX write before releasing the PMU reset. */
	ddr_write16(phy + PHY_APB_MUX, 0x0001);
	/* MicroReset: reset+stall, release reset while stalled, then run. */
	ddr_write16(phy + PHY_PMU_CONTROL, 0x0009);
	ddr_write16(phy + PHY_PMU_CONTROL, 0x0001);
	ddr_write16(phy + PHY_PMU_CONTROL, 0x0000);
	return 0;
}

/* Stall the PMU before returning the APB mux to the host. */
void ddr_phy_stop_training(u32 phy)
{
	ddr_write16(phy + PHY_PMU_CONTROL, 0x0001);
	ddr_write16(phy + PHY_APB_MUX, 0x0000);
}

/*
 * Read the first 512 halfwords of the PMU message block. A null result
 * preserves the reference read sequence without retaining a host copy.
 */
void ddr_phy_read_training_result(u32 phy, u16 *result)
{
	for (unsigned int i = 0; i < 512; i++) {
		u16 value = ddr_read16(phy + PHY_DMEM + i * 2);

		if (result)
			result[i] = value;
	}
}

int ddr_phy_finish_training(u32 phy, enum ddr_memory_profile memory)
{
	const struct phy_parameters *p = select_parameters(memory);

	if (!p)
		return -1;
	write_table(phy, &p->after_training);
	write_table(phy, &p->pie);
	return 0;
}
