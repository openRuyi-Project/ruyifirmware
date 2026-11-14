/* SPDX-License-Identifier: Apache-2.0 */
/*
 * Copyright 2024 Beijing ESWIN Computing Technology Co., Ltd.
 * Copyright 2026 Han Gao <gaohan@iscas.ac.cn>
 * Inline-ECC memory initialization through AXI DMA.
 */
#include "common.h"

/*
 * Synopsys DW AXI DMAC byte offsets. Channel n starts at
 * dma + (n + 1) * 0x100. This boot path owns hardware channel 1.
 * CHEN bit 17 is the write-enable for channel-enable bit 1.
 */
#define DMA_CONFIG		0x10
#define DMA_ENABLE		0x18
#define DMA_INTERRUPT		0x30
#define DMA_CHANNEL1		0x200
#define DMA_CH1_ENABLE		(1U << 1)
#define DMA_CH1_WRITE		(1U << 17)
#define CHANNEL_SAR		0x00
#define CHANNEL_DAR		0x08
#define CHANNEL_BLOCK_TS	0x10
#define CHANNEL_CONTROL		0x18
#define CHANNEL_CONFIG		0x20
#define CHANNEL_STATUS_ENABLE	0x80
#define CHANNEL_STATUS		0x88
#define CHANNEL_SIGNAL_ENABLE	0x90
#define CHANNEL_CLEAR		0x98
#define SEED_BYTES		0x20000U
#define COPY_BYTES		0x400000U

/* The RV32 SCPU writes split 64-bit DMA registers low half first. */
static void write64(u32 address, unsigned long long value)
{
	ddr_write32(address, value);
	ddr_write32(address + 0x04, value >> 32);
}

static void disable_channel(u32 dma)
{
	ddr_write32(dma + DMA_ENABLE,
		    (ddr_read32(dma + DMA_ENABLE) & ~DMA_CH1_ENABLE) | DMA_CH1_WRITE);
	while (ddr_read32(dma + DMA_ENABLE) & DMA_CH1_ENABLE)
		;
}

static int copy(u32 dma, unsigned long long source,
		unsigned long long destination, u32 length, int seed)
{
	u32 channel = dma + DMA_CHANNEL1;

	ddr_write32(dma + DMA_CONFIG, ddr_read32(dma + DMA_CONFIG) | 0x01);
	ddr_write32(dma + DMA_CONFIG, ddr_read32(dma + DMA_CONFIG) | 0x02);
	disable_channel(dma);
	ddr_write32(channel + CHANNEL_CONFIG, 0x00000000);
	ddr_write32(channel + CHANNEL_CONFIG + 0x04, seed ? 0x7f818010 : 0x7f818018);
	write64(channel + CHANNEL_SAR, source);
	write64(channel + CHANNEL_DAR, destination);
	/*
	 * BLOCK_TS is a transfer-count field. Keep its reference encoding
	 * together with the source/destination widths in CHANNEL_CONTROL.
	 */
	ddr_write32(channel + CHANNEL_BLOCK_TS, length - 1);
	ddr_write32(channel + CHANNEL_CONTROL, seed ? 0x00267601 : 0x00267600);
	ddr_write32(channel + CHANNEL_CONTROL + 0x04, 0x04000000);
	ddr_write32(channel + CHANNEL_SIGNAL_ENABLE, 0x003f7fe3);
	ddr_write32(channel + CHANNEL_STATUS_ENABLE, 0x203f7fe3);
	ddr_write32(dma + DMA_ENABLE,
		    ddr_read32(dma + DMA_ENABLE) | DMA_CH1_ENABLE | DMA_CH1_WRITE);

	for (;;) {
		u32 pending = ddr_read32(dma + DMA_INTERRUPT);
		u32 low, high;

		if (!(pending & DMA_CH1_ENABLE))
			continue;
		low = ddr_read32(channel + CHANNEL_STATUS);
		high = ddr_read32(channel + CHANNEL_STATUS + 0x04);
		ddr_write32(channel + CHANNEL_CLEAR, low);
		if (high || (low & ~0x03U)) {
			disable_channel(dma);
			return -1;
		}
		if (low & 0x01)
			return 0;
	}
}

static void sample_dma_status(u32 dma)
{
	(void)ddr_read32(dma + DMA_INTERRUPT);
	for (unsigned int channel = 0; channel < 10; channel++) {
		u32 base = dma + (channel + 1) * 0x100;

		(void)ddr_read32(base + CHANNEL_STATUS);
		(void)ddr_read32(base + CHANNEL_STATUS + 0x04);
	}
}

static void sample_ecc_status(u32 controller0)
{
	for (unsigned int channel = 0; channel < 2; channel++)
		(void)ddr_read32(controller0 + channel * 0x80000U + 0x10608);
}

int ddr_ecc_scrub(const struct ddr_ecc_region *region)
{
	unsigned long long start, length;

	if (region->physical_gib != 16 && region->physical_gib != 32)
		return -1;
	start = region->dram_low | (unsigned long long)region->dram_high << 32;
	/* Inline ECC reserves one eighth of physical memory for check bits. */
	length = (unsigned long long)region->physical_gib * 7 << 27;

	/* The reference initializes ECC with this pattern, not with zeros. */
	for (unsigned int i = 0; i < SEED_BYTES; i += 8) {
		ddr_write32(region->seed + i, 0x90abcdef);
		ddr_write32(region->seed + i + 0x04, 0x12345678);
	}
	/* Seed the first window from SRAM, then propagate through DRAM. */
	for (unsigned int offset = 0; offset < COPY_BYTES; offset += SEED_BYTES) {
		if (copy(region->dma, region->seed, start + offset, SEED_BYTES, 1))
			return -1;
		(void)ddr_read32(region->dma + DMA_INTERRUPT);
	}
	sample_dma_status(region->dma);
	sample_ecc_status(region->controller0);
	sample_ecc_status(region->controller0);
	for (unsigned long long offset = COPY_BYTES; offset < length; offset += COPY_BYTES)
		if (copy(region->dma, start + offset - COPY_BYTES,
			 start + offset, COPY_BYTES, 0))
			return -1;
	(void)ddr_read32(region->dma + DMA_INTERRUPT);
	sample_dma_status(region->dma);
	sample_ecc_status(region->controller0);
	return 0;
}
