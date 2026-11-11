/* SPDX-License-Identifier: MIT */
/* Compare the reference and reconstructed RV32 SCPU stages with modeled MMIO. */
#include <inttypes.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unicorn/unicorn.h>
#include <unicorn/riscv.h>

#define CHECK(expr) do { if (!(expr)) { \
	fprintf(stderr, "%s:%d: %s\n", __FILE__, __LINE__, #expr); exit(1); \
} } while (0)
#define UC_OK(expr) do { uc_err err = (expr); if (err != UC_ERR_OK) { \
	fprintf(stderr, "%s: %s\n", #expr, uc_strerror(err)); exit(1); \
} } while (0)
#define MAX_EVENTS 4096
#define STACK_BASE 0x30010000U
#define RETURN_PC 0x30004000U

struct event {
	uint32_t kind, address, value;
};
struct run {
	struct event events[MAX_EVENTS];
	unsigned count, die, delay, pll_reads, uart_reads;
	bool initial_lock;
};

static void event(struct run *r, unsigned kind, uint32_t address, uint32_t value)
{
	CHECK(r->count < MAX_EVENTS);
	r->events[r->count++] = (struct event){kind, address, value};
}

static bool mmio(uint64_t address)
{
	static const uint32_t pages[] = {
		0x21b40000, 0x51828000, 0x51600000, 0x50818000, 0x50900000,
		0x71600000, 0x70818000, 0x70900000,
	};
	for (unsigned i = 0; i < sizeof(pages) / sizeof(pages[0]); i++)
		if ((address & ~0xfffULL) == pages[i])
			return true;
	return false;
}

static void access_mmio(uc_engine *uc, uc_mem_type type, uint64_t address,
		       int size, int64_t value, void *user)
{
	struct run *r = user;
	uint32_t word = value;
	if (!mmio(address))
		return;
	CHECK(size == 4);
	if (type == UC_MEM_READ) {
		if (address == 0x21b4003c) {
			word = (r->die << 8) | 0xa5000001U;
		} else if (address == 0x518280a4) {
			word = r->pll_reads++ == 0 ? (r->initial_lock ? 32 : 0) :
			       (r->pll_reads > r->delay + 1 ? 32 : 0);
		} else if (address == 0x50900014 || address == 0x70900014) {
			word = r->uart_reads++ % 3 == 2 ? 32 : 0;
		} else {
			CHECK(address == 0x50818008 || address == 0x70818008);
			UC_OK(uc_mem_read(uc, address, &word, sizeof(word)));
		}
		UC_OK(uc_mem_write(uc, address, &word, sizeof(word)));
	}
	event(r, type, address, word);
}

static void instruction(uc_engine *uc, uint64_t address, uint32_t size, void *user)
{
	uint32_t word = 0;
	if (size == 4) {
		UC_OK(uc_mem_read(uc, address, &word, sizeof(word)));
		if (word == 0x0820000f || word == 0x0140000f)
			event(user, 0, 0, word);
	}
}

static unsigned char *load(const char *path, size_t *bytes)
{
	FILE *f = fopen(path, "rb");
	CHECK(f != NULL);
	CHECK(fseek(f, 0, SEEK_END) == 0);
	long size = ftell(f);
	CHECK(size > 0 && size <= 0x4000);
	CHECK(fseek(f, 0, SEEK_SET) == 0);
	unsigned char *data = malloc(size);
	CHECK(data != NULL);
	CHECK(fread(data, 1, size, f) == (size_t)size);
	CHECK(fclose(f) == 0);
	*bytes = size;
	return data;
}

static void execute(const char *path, uint32_t address, struct run *r)
{
	uc_engine *uc;
	uc_hook mem_hook, code_hook;
	size_t bytes;
	unsigned char *code = load(path, &bytes);
	static const uint32_t pages[] = {
		0x21b40000, 0x51828000, 0x51600000, 0x50818000, 0x50900000,
		0x71600000, 0x70818000, 0x70900000,
	};
	UC_OK(uc_open(UC_ARCH_RISCV, UC_MODE_RISCV32, &uc));
	UC_OK(uc_mem_map(uc, address, 0x4000, UC_PROT_ALL));
	UC_OK(uc_mem_map(uc, STACK_BASE, 0x10000, UC_PROT_ALL));
	UC_OK(uc_mem_map(uc, RETURN_PC, 0x1000, UC_PROT_ALL));
	for (unsigned i = 0; i < sizeof(pages) / sizeof(pages[0]); i++)
		UC_OK(uc_mem_map(uc, pages[i], 0x1000, UC_PROT_ALL));
	UC_OK(uc_mem_write(uc, address, code, bytes));
	uint32_t initial[32];
	for (unsigned reg = 1; reg < 32; reg++) {
		initial[reg] = 0x31415900U + reg;
		UC_OK(uc_reg_write(uc, UC_RISCV_REG_X0 + reg, &initial[reg]));
	}
	initial[1] = RETURN_PC;
	initial[2] = STACK_BASE + 0x10000;
	UC_OK(uc_reg_write(uc, UC_RISCV_REG_RA, &initial[1]));
	UC_OK(uc_reg_write(uc, UC_RISCV_REG_SP, &initial[2]));
	UC_OK(uc_hook_add(uc, &mem_hook, UC_HOOK_MEM_READ | UC_HOOK_MEM_WRITE,
			 access_mmio, r, 1, 0));
	UC_OK(uc_hook_add(uc, &code_hook, UC_HOOK_CODE, instruction, r, 1, 0));
	UC_OK(uc_emu_start(uc, address, RETURN_PC, 1000000, 100000));
	uint32_t value;
	UC_OK(uc_reg_read(uc, UC_RISCV_REG_PC, &value));
	CHECK(value == RETURN_PC);
	UC_OK(uc_reg_read(uc, UC_RISCV_REG_A0, &value));
	CHECK(value == 0);
	for (unsigned reg = 1; reg < 32; reg++) {
		if (reg <= 4 || reg == 8 || reg == 9 || (reg >= 18 && reg <= 27)) {
			UC_OK(uc_reg_read(uc, UC_RISCV_REG_X0 + reg, &value));
			CHECK(value == initial[reg]);
		}
	}
	UC_OK(uc_close(uc));
	free(code);
}

int main(int argc, char **argv)
{
	CHECK(argc == 3);
	unsigned cases = 0;
	for (unsigned base = 0; base < 2; base++)
		for (unsigned die = 0; die < 3; die++)
			for (unsigned locked = 0; locked < 2; locked++)
				for (unsigned delay = 0; delay < 4; delay += 3) {
					struct run old = {.die = die ? (die == 1 ? 1 : 0xa5) : 0,
						.initial_lock = locked, .delay = delay};
					struct run new = old;
					uint32_t address = base ? 0x30008000 : 0x59000000;
					execute(argv[1], address, &old);
					execute(argv[2], address, &new);
					CHECK(old.count == new.count);
					for (unsigned i = 0; i < old.count; i++) {
						if (memcmp(&old.events[i], &new.events[i], sizeof(struct event))) {
							fprintf(stderr, "trace mismatch at %u, base %08x die %u lock %u delay %u\n", i, address, old.die, locked, delay);
							return 1;
						}
					}
					cases++;
				}
	printf("PASS %u cases: MMIO values/order, I/O fences, UART bytes, return ABI and both load addresses\n", cases);
	return 0;
}
