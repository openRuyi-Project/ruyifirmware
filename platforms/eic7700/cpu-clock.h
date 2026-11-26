/* SPDX-License-Identifier: Apache-2.0 */
/* Copyright 2024 Beijing ESWIN Computing Technology Co., Ltd. */
#ifndef EIC7700_CPU_CLOCK_H
#define EIC7700_CPU_CLOCK_H

#define SYSCRG                  0x51828000U
#define CPU_PLL_CONFIG0         (SYSCRG + 0x64)
#define CPU_PLL_CONFIG1         (SYSCRG + 0x68)
#define CPU_PLL_CONFIG2         (SYSCRG + 0x6c)
#define POSTDIV1_A_MASK         (7U << 8)
#define POSTDIV1_B_MASK         (7U << 12)
#define PLL_STATUS              (SYSCRG + 0xa4)
#define CPU_CLOCK_CONTROL       (SYSCRG + 0x208)
#define CPU_PLL_LOCKED          (1U << 5)
#define CPU_PLL_ENABLE          1U
#define CPU_SOURCE_MASK         3U
#define CPU_SOURCE_XTAL         2U
#define CPU_BUS_1_TO_1          (1U << 20)
/* The SCPU boot stages have no timer ABI. Bound both lock transitions. */
#define PLL_POLL_LIMIT          100000U
#define CPU_CLOCK_CONTROL_VALUE 0xff800000U
/* A 24 MHz reference feeds FOUT1 with a fixed divide by four. */
#define CPU_PLL_STEP_HZ         6000000ULL

static inline unsigned int read32(unsigned int address)
{
	unsigned int value = *(volatile unsigned int *)address;

	__asm__ volatile ("fence i,r" ::: "memory");
	return value;
}

static inline void write32(unsigned int address, unsigned int value)
{
	__asm__ volatile ("fence w,o" ::: "memory");
	*(volatile unsigned int *)address = value;
}

static inline int wait_cpu_pll(unsigned int expected)
{
	for (unsigned int i = 0; i < PLL_POLL_LIMIT; i++)
		if ((read32(PLL_STATUS) & CPU_PLL_LOCKED) == expected)
			return 1;
	return 0;
}

static inline int set_cpu_clock(unsigned long long hz)
{
	unsigned int cfg0 = ((unsigned int)(hz / CPU_PLL_STEP_HZ) << 20) | 0x1300U;
	unsigned int frac = ((hz % CPU_PLL_STEP_HZ) << 24) / CPU_PLL_STEP_HZ;

	unsigned int ctrl = read32(CPU_CLOCK_CONTROL);

	write32(CPU_CLOCK_CONTROL, (ctrl & ~(CPU_SOURCE_MASK | CPU_BUS_1_TO_1)) | CPU_SOURCE_XTAL);
	if ((read32(CPU_CLOCK_CONTROL) & CPU_SOURCE_MASK) != CPU_SOURCE_XTAL)
		return 0;
	write32(CPU_PLL_CONFIG0, read32(CPU_PLL_CONFIG0) & ~CPU_PLL_ENABLE);
	if (!wait_cpu_pll(0))
		return 0;
	write32(CPU_PLL_CONFIG0, cfg0);
	write32(CPU_PLL_CONFIG1, (frac << 4) | 0x0aU);
	write32(CPU_PLL_CONFIG2, read32(CPU_PLL_CONFIG2) & ~(POSTDIV1_A_MASK | POSTDIV1_B_MASK));
	write32(CPU_PLL_CONFIG0, cfg0 | CPU_PLL_ENABLE);
	if (!wait_cpu_pll(CPU_PLL_LOCKED))
		return 0;
	write32(CPU_CLOCK_CONTROL, CPU_CLOCK_CONTROL_VALUE);
	return 1;
}

#endif
