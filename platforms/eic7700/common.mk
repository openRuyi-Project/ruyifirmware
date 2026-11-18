# SPDX-License-Identifier: MIT
EDK_EXTRA_FLAGS :=
RISCV_ISA := rv64gc_zba_zbb
FD_SIZE := 0x400000
COREBOOT_CROSS_COMPILE ?= $(CROSS_COMPILE)
SBI_ADDRESS := 0x80800000
SBI_BUILD := $(BUILD)/opensbi-$(SBI_ADDRESS)
PAYLOAD_ADDRESS := 0x82200000
CBFS_DTB_NAME := fallback/DTB
CBFS_REPLACE_DTB := FALSE
ROM_PACKER := tools/eic7700/image.py
ROM_PACK_ARGS = --layout $(BOARD) --sys-init "$(BUILD)/sys-init.bin" \
  --ddr "$(BUILD)/ddr.bin"
FIRMWARE_IRQ_NODES :=
INPUT_PREPARER := tools/eic7700/prepare-inputs.py
INPUT_PREPARER_ARGS = --cross-compile "$(CROSS_COMPILE)" --dtb "$(DTB)"
prepare-inputs: dtb

EIC7700_OPENOCD_DIR := $(ROOT)/tools/eic7700/openocd
EIC7700_OPENOCD_PRESET ?= ch347
PACKAGE_COMMON += "$(EIC7700_OPENOCD_DIR)/eic7700.cfg" "$(EIC7700_OPENOCD_DIR)/ch347.cfg" "$(BUILD)/openocd.cfg"

# Keep the openocd.cfg entry point used by existing package commands.
package: $(BUILD)/openocd.cfg
$(BUILD)/openocd.cfg: $(EIC7700_OPENOCD_DIR)/$(EIC7700_OPENOCD_PRESET).cfg
	mkdir -p "$(BUILD)"
	cp "$<" "$@"
