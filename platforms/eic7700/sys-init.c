/* SPDX-License-Identifier: Apache-2.0 */
/*
 * Copyright 2024 Beijing ESWIN Computing Technology Co., Ltd.
 * Copyright 2026 Han Gao <gaohan@iscas.ac.cn>
 *
 * Source reconstruction of the SCPU initialization stage distributed as
 * Esbd-77serial-firmware/sys/sys_init.bin and SiFive second_boot_fw.bin.
 * Reference SHA256: 7d10fd7aa4b0b5924daec199be00ab6d76515115e19f46c69e0b2ad665f7a744
 *
 * BootROM supplies a stack and calls the first instruction. The same binary
 * must run at 0x59000000 for SPI and 0x30008000 for UART recovery, then return.
 */

typedef unsigned int u32;

#define DIE_ID                  0x21b4003cU
#define DIE_ID_SHIFT            8
#define DIE_ADDRESS_STRIDE      0x20000000U
#define SYSCRG                  0x51828000U
#define CPU_PLL_CONFIG0         (SYSCRG + 0x64)
#define CPU_PLL_CONFIG1         (SYSCRG + 0x68)
#define PLL_STATUS              (SYSCRG + 0xa4)
#define CPU_CLOCK_CONTROL       (SYSCRG + 0x208)
#define CPU_PLL_LOCKED          (1U << 5)
#define CPU_PLL_ENABLE          1U
#define CPU_PLL_CONFIG0_VALUE   0x0e901300U
#define CPU_PLL_CONFIG1_VALUE   0x0555555aU
#define CPU_CLOCK_CONTROL_VALUE 0xff800000U
#define UART                    0x50900000U
#define UART_LINE_STATUS        0x14
#define UART_TX_EMPTY           (1U << 5)
#define FAN_PIN                0x5160024cU
#define FAN_PIN_PWM             8U
#define PWM                    0x50818000U
#define PWM_LOAD_LOW            0
#define PWM_CONTROL             8
#define PWM_LOAD_HIGH           0xb0
#define FAN_LOW_COUNT           9000U
#define FAN_HIGH_COUNT          10000U
#define FAN_PWM_CONTROL         30U
#define PWM_ENABLE              1U

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

static void print_ready(u32 uart)
{
	const char *message = "pll config ok\r\n";

	/* Preserve the reference UART access sequence and wait semantics. */
	while (*message) {
		while (!(*(volatile u32 *)(uart + UART_LINE_STATUS) & UART_TX_EMPTY))
			;
		*(volatile u32 *)uart = (unsigned char)*message++;
	}
}

__attribute__((section(".text.entry")))
int scpu_sys_init(void)
{
	u32 die_offset = ((read32(DIE_ID) >> DIE_ID_SHIFT) & 0xff) ?
			 DIE_ADDRESS_STRIDE : 0;

	/* The reference stage always configures the die-0 CPU PLL. */
	if (read32(PLL_STATUS) & CPU_PLL_LOCKED) {
		write32(CPU_PLL_CONFIG0, CPU_PLL_CONFIG0_VALUE);
		write32(CPU_PLL_CONFIG1, CPU_PLL_CONFIG1_VALUE);
		write32(CPU_PLL_CONFIG0, CPU_PLL_CONFIG0_VALUE | CPU_PLL_ENABLE);
		while (!(read32(PLL_STATUS) & CPU_PLL_LOCKED))
			;
		write32(CPU_CLOCK_CONTROL, CPU_CLOCK_CONTROL_VALUE);
		print_ready(UART + die_offset);
	}

	write32(FAN_PIN + die_offset, FAN_PIN_PWM);
	write32(PWM + die_offset + PWM_CONTROL, 0);
	write32(PWM + die_offset + PWM_LOAD_LOW, FAN_LOW_COUNT);
	write32(PWM + die_offset + PWM_LOAD_HIGH, FAN_HIGH_COUNT);
	write32(PWM + die_offset + PWM_CONTROL, FAN_PWM_CONTROL);
	write32(PWM + die_offset + PWM_CONTROL,
		read32(PWM + die_offset + PWM_CONTROL) | PWM_ENABLE);
	return 0;
}
