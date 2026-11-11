/* SPDX-License-Identifier: Apache-2.0 */
/* Copyright 2026 Han Gao <gaohan@iscas.ac.cn> */
/* Select an authorized vendor DDR payload before any MCPU code runs. */
#include <IndustryStandard/Eic7700BootConfig.h>

typedef unsigned int u32;
typedef unsigned char u8;

#define BIT(n)                  (1U << (n))
#define SPI                     0x51800000U
#define SPI_DATA                0x5c000000U
#define SYSCRG                  0x51828000U
#define SPI_CLOCK               (SYSCRG + 0x104)
#define SPI_CONFIG_CLOCK        (SYSCRG + 0x108)
#define AON_BUS_CLOCK           (SYSCRG + 0x1e4)
#define SPI_RESET               (SYSCRG + 0x490)
#define CLOCK_ENABLE            BIT(31)
#define BUS_ENABLE              BIT(29)
#define CLOCK_XTAL              BIT(0)
#define BUS_MODE                0x04
#define FAST_READ               0x10
#define TRANSFER_BYTES          0x14
#define COMMAND                 0x18
#define INTERRUPT_CONTROL       0x1c
#define DMA_THRESHOLD           0x20
#define FLASH_ADDRESS           0x24
#define COMMAND_VALID           BIT(0)
#define INTERRUPT_DONE          BIT(0)
#define INTERRUPT_CLEAR         BIT(1)
#define INTERRUPT_ENABLE        BIT(2)
#define READ_COMMAND            ((3U << 6) | (13U << 1) | COMMAND_VALID)
/* BootROM provides no timer ABI. Bound polling rather than blocking it forever. */
#define SPI_POLL_LIMIT          1000000U
#define DDR_LOAD_ADDRESS        0x59000000U

extern const u8 _ddr_normal_start[] __attribute__((visibility("hidden")));
extern const u8 _ddr_normal_end[] __attribute__((visibility("hidden")));
extern const u8 _ddr_ecc_start[] __attribute__((visibility("hidden")));
extern const u8 _ddr_ecc_end[] __attribute__((visibility("hidden")));

static u32 read32(u32 address)
{
	u32 value = *(volatile u32 *)address;
	__asm__ volatile ("fence i,r" ::: "memory");
	return value;
}

static void write32(u32 address, u32 value)
{
	__asm__ volatile ("fence w,o" ::: "memory");
	*(volatile u32 *)address = value;
}

static int wait32(u32 address, u32 mask, u32 value)
{
	for (u32 count = 0; count < SPI_POLL_LIMIT; count++)
		if ((read32(address) & mask) == value)
			return 0;
	return -1;
}

static u32 crc32(const u8 *data, u32 size)
{
	u32 crc = ~0U;
	while (size--) {
		crc ^= *data++;
		for (unsigned bit = 0; bit < 8; bit++)
			crc = (crc >> 1) ^ ((crc & 1) ? 0xedb88320U : 0);
	}
	return ~crc;
}

static int valid(const u32 *record)
{
	return record[EIC7700_BOOT_CONFIG_MAGIC_WORD] == EIC7700_BOOT_CONFIG_MAGIC &&
	       record[EIC7700_BOOT_CONFIG_VERSION_WORD] == EIC7700_BOOT_CONFIG_VERSION &&
	       !(record[EIC7700_BOOT_CONFIG_FLAGS_WORD] & ~EIC7700_BOOT_CONFIG_ECC) &&
	       crc32((const u8 *)record, EIC7700_BOOT_CONFIG_BYTES - sizeof(u32)) ==
		       record[EIC7700_BOOT_CONFIG_CRC_WORD];
}

static int ecc_policy(void)
{
	static const u32 offsets[] = {
		BUS_MODE, FAST_READ, TRANSFER_BYTES, DMA_THRESHOLD, FLASH_ADDRESS
	};
	u32 saved[sizeof(offsets) / sizeof(offsets[0])];
	u32 clocks[3], interrupt;
	u32 records[EIC7700_BOOT_CONFIG_SLOT_COUNT][EIC7700_BOOT_CONFIG_BYTES / sizeof(u32)];
	unsigned selected = EIC7700_BOOT_CONFIG_SLOT_COUNT;
	int status = -1;

	clocks[0] = read32(SPI_CLOCK);
	clocks[1] = read32(SPI_CONFIG_CLOCK);
	clocks[2] = read32(AON_BUS_CLOCK);
	write32(AON_BUS_CLOCK, clocks[2] | BUS_ENABLE);
	write32(SPI_CONFIG_CLOCK, clocks[1] | CLOCK_ENABLE);
	write32(SPI_CLOCK, clocks[0] | CLOCK_ENABLE);
	if ((read32(SPI_RESET) & 3) != 3)
		goto restore_clocks;
	/* An incomplete command must keep its clock and register state. */
	if (wait32(SPI + COMMAND, COMMAND_VALID, 0))
		return -1;
	for (unsigned i = 0; i < sizeof(offsets) / sizeof(offsets[0]); i++)
		saved[i] = read32(SPI + offsets[i]);
	interrupt = read32(SPI + INTERRUPT_CONTROL) & INTERRUPT_ENABLE;
	write32(SPI_CLOCK, clocks[0] | CLOCK_ENABLE | CLOCK_XTAL);
	write32(SPI + BUS_MODE, 0);
	write32(SPI + FAST_READ, 0);
	write32(SPI + DMA_THRESHOLD, 0);
	for (unsigned slot = 0; slot < EIC7700_BOOT_CONFIG_SLOT_COUNT; slot++) {
		write32(SPI + INTERRUPT_CONTROL, INTERRUPT_CLEAR | INTERRUPT_ENABLE);
		write32(SPI + FLASH_ADDRESS, EIC7700_BOOT_CONFIG_OFFSET +
			slot * EIC7700_BOOT_CONFIG_SLOT_SIZE);
		write32(SPI + TRANSFER_BYTES, EIC7700_BOOT_CONFIG_BYTES);
		write32(SPI + COMMAND, READ_COMMAND);
		if (wait32(SPI + COMMAND, COMMAND_VALID, 0) ||
		    wait32(SPI + INTERRUPT_CONTROL, INTERRUPT_DONE, INTERRUPT_DONE))
			return -1;
		for (unsigned i = 0; i < EIC7700_BOOT_CONFIG_BYTES / sizeof(u32); i++)
			records[slot][i] = read32(SPI_DATA + i * sizeof(u32));
		if (valid(records[slot]) &&
		    (selected == EIC7700_BOOT_CONFIG_SLOT_COUNT ||
		     (int)(records[slot][EIC7700_BOOT_CONFIG_GEN_WORD] -
			   records[selected][EIC7700_BOOT_CONFIG_GEN_WORD]) > 0))
			selected = slot;
	}
	status = selected < EIC7700_BOOT_CONFIG_SLOT_COUNT &&
		 (records[selected][EIC7700_BOOT_CONFIG_FLAGS_WORD] & EIC7700_BOOT_CONFIG_ECC);
	for (unsigned i = 0; i < sizeof(offsets) / sizeof(offsets[0]); i++)
		write32(SPI + offsets[i], saved[i]);
	write32(SPI + INTERRUPT_CONTROL, interrupt | INTERRUPT_CLEAR);
restore_clocks:
	write32(SPI_CLOCK, clocks[0]);
	write32(SPI_CONFIG_CLOCK, clocks[1]);
	write32(AON_BUS_CLOCK, (read32(AON_BUS_CLOCK) & ~BUS_ENABLE) |
		(clocks[2] & BUS_ENABLE));
	return status;
}

int ddr_dispatch(void)
{
	int ecc = ecc_policy();
	const u8 *source = ecc ? _ddr_ecc_start : _ddr_normal_start;
	const u8 *end = ecc ? _ddr_ecc_end : _ddr_normal_end;
	volatile u8 *destination = (void *)DDR_LOAD_ADDRESS;
	if (ecc < 0)
		return -1;
	/* The dispatcher is above both payloads. Copy forward to handle overlap. */
	while (source < end)
		*destination++ = *source++;
	__asm__ volatile ("fence rw,rw\nfence.i" ::: "memory");
	return ((int (*)(void))DDR_LOAD_ADDRESS)();
}
