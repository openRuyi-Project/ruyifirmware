# SPDX-License-Identifier: MIT
EIC7700_OPENOCD_PRESET := p550-ft4232
include $(ROOT)/platforms/eic7700/common.mk
COREBOOT_CONFIG := config.sifive_hifive_premier_p550
DTB_SOURCE := arch/riscv/boot/dts/eswin/eic7700-hifive-premier-p550.dts
DTB_FILE := hifive-premier-p550.dtb
DTB_COMPATIBLE := sifive,hifive-premier-p550
ROM_RECOVERY_PACK_ARGS = --layout $(BOARD) --sys-init "$(BUILD)/sys-init.bin" \
  --ddr "$(BUILD)/ddr-recovery.bin"
RECOVERY_METHOD := uart-jtag
PACKAGE_EXTRA := "$(EIC7700_OPENOCD_DIR)/p550-ft4232.cfg" "$(ROOT)/tools/eic7700/load-ram.tcl" "$(ROOT)/tools/eic7700/upload-ddr.sh" "$(BUILD)/recovery-addresses.tcl" \
  "$(BUILD)/ddr-build.json" "$(BUILD)/ddr-LICENSE.txt" "$(BUILD)/ddr-COPYING.txt"
