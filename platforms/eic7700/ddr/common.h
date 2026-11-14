/* SPDX-License-Identifier: Apache-2.0 */
/* Copyright 2026 Han Gao <gaohan@iscas.ac.cn> */
#ifndef EIC7700_DDR_COMMON_H
#define EIC7700_DDR_COMMON_H

typedef unsigned char u8;
typedef unsigned short u16;
typedef unsigned int u32;

struct ddr_die_info {
	u8 count;
	u8 ordinal;
};

/*
 * EIC7700 access units:
 * SYSCRG, DDRC and DMAC offsets are byte offsets with 32-bit accesses.
 * PHY offsets in this code are also bytes, but accesses are 16-bit.
 * A Synopsys PHY word-register number must be multiplied by two once.
 */
static inline u32 ddr_read32(u32 address)
{
	return *(volatile u32 *)address;
}

static inline void ddr_write32(u32 address, u32 value)
{
	*(volatile u32 *)address = value;
}

static inline u16 ddr_read16(u32 address)
{
	return *(volatile u16 *)address;
}

static inline void ddr_write16(u32 address, u16 value)
{
	*(volatile u16 *)address = value;
}

u32 ddr_read_die_info(struct ddr_die_info *info, int probe_second_die);
u32 ddr_die_offset(u8 ordinal);
u8 ddr_reset_and_detect_d2d(u32 syscrg, u8 die_count);
int ddr_set_data_rate(u32 syscrg, u32 rate);
u32 ddr_phy_read_message(u32 phy, u8 stream);

/* A stream callback consumes the additional words through the same mailbox. */
struct ddr_training_log {
	void (*progress)(u32 controller, u32 percent);
	void (*stream)(u16 id, u16 words, u32 phy);
};

int ddr_phy_wait_training(u32 phy, u32 controller,
			  const struct ddr_training_log *log);

enum ddr_memory_profile {
	DDR_LPDDR4X,
	DDR_LPDDR5_16GB,
	DDR_LPDDR5_32GB,
};

int ddr_phy_configure_lanes(u32 phy, enum ddr_memory_profile memory,
			    unsigned int channel, int nx, int d2d);

int ddr_configure_controllers(u32 controller0, enum ddr_memory_profile memory,
			      int ecc);

int ddr_controllers_prepare_training(u32 controller0,
				     enum ddr_memory_profile memory);
int ddr_controllers_finish_training(u32 controller0,
				    enum ddr_memory_profile memory);

int ddr_phy_prepare(u32 phy, enum ddr_memory_profile memory);
int ddr_phy_load_training(u32 phy, enum ddr_memory_profile memory);
int ddr_phy_start_training(u32 phy, enum ddr_memory_profile memory);
void ddr_phy_stop_training(u32 phy);
void ddr_phy_read_training_result(u32 phy, u16 *result);
int ddr_phy_finish_training(u32 phy, enum ddr_memory_profile memory);

struct ddr_device {
	u32 syscrg;
	u32 controller0;
	u32 phy0;
	u32 die_count;
	u32 nx;
	u32 ecc;
};

struct ddr_training_result {
	enum ddr_memory_profile memory;
	u32 size_gib;
	u32 rate;
	u32 d2d;
};

/* ECC users must scrub memory after training, before exposing it to CPUs. */
int ddr_train(const struct ddr_device *device, const struct ddr_training_log *log,
	      struct ddr_training_result *result);

struct ddr_ecc_region {
	u32 dma;
	u32 controller0;
	u32 seed;
	u32 dram_low;
	u32 dram_high;
	u32 physical_gib;
};

int ddr_ecc_scrub(const struct ddr_ecc_region *region);

#endif
