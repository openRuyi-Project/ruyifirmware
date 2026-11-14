# SPDX-License-Identifier: Apache-2.0
CROSS_COMPILE ?= riscv64-unknown-elf-
OUT ?= $(abspath ../../../build/eic7700-ddr)
SOURCES := common.c lanes.c controller.c controller-state.c phy.c training.c ecc.c
OBJECTS := $(addprefix $(OUT)/,$(SOURCES:.c=.o))
CFLAGS := -march=rv32im -mabi=ilp32 -Os -ffreestanding -fno-builtin \
	-msmall-data-limit=0 -mno-relax -Wall -Wextra -Werror -MMD -MP

.PHONY: all images
all: $(OUT)/libeic7700-ddr.a images

# DTB is the same compiled device tree that is embedded in the board firmware.
images:
	test -n "$(DTB)" || { echo 'Set DTB to the board device tree path.' >&2; exit 1; }
	python3 ../../../tools/eic7700/ddr.py --dtb "$(DTB)" --output "$(OUT)/ddr.bin" \
		--cross-compile "$(CROSS_COMPILE)"

$(OUT):
	mkdir -p $@

$(OUT)/%.o: %.c common.h | $(OUT)
	$(CROSS_COMPILE)gcc $(CFLAGS) -c $< -o $@

$(OUT)/phy.o: phy-data.inc

$(OUT)/libeic7700-ddr.a: $(OBJECTS)
	$(CROSS_COMPILE)ar rcs $@ $^

-include $(OBJECTS:.o=.d)
