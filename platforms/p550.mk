# SPDX-License-Identifier: MIT
EDK_PLATFORM := SiFivePremierP550
EDK_DSC := EswinPlatformPkg/PremierP550/PremierP550.dsc
EDK_EXTRA_FLAGS :=
RISCV_ISA := rv64gc_zba_zbb
FD_FILE := PREMIERP550.fd
FD_SIZE := 0x400000
COREBOOT_CONFIG := config.sifive_hifive_premier_p550
COREBOOT_CROSS_COMPILE ?= $(CROSS_COMPILE)
SBI_ADDRESS := 0x80000000
PAYLOAD_ADDRESS := 0x82200000
DTB_SOURCE := arch/riscv/boot/dts/eswin/eic7700-hifive-premier-p550.dts
DTB_FILE := hifive-premier-p550.dtb
DTB_COMPATIBLE := sifive,hifive-premier-p550
CBFS_DTB_NAME := fallback/DTB
CBFS_REPLACE_DTB := FALSE
ROM_PACKER := tools/eic7700/image.py
ROM_PACK_ARGS = --layout $(BOARD) --sys-init "$(BUILD)/sys-init.bin" \
  --ddr "$(BUILD)/ddr-dispatch.bin"
ROM_RECOVERY_PACK_ARGS = --layout $(BOARD) --sys-init "$(BUILD)/sys-init.bin" \
  --ddr "$(BUILD)/ddr-normal.bin"
RECOVERY_METHOD := uart-jtag
FIRMWARE_IRQ_NODES :=
INPUT_PREPARER := tools/eic7700/prepare-inputs.py
INPUT_PREPARER_ARGS = --cross-compile "$(CROSS_COMPILE)"
PACKAGE_EXTRA := "$(ROOT)/platforms/p550/openocd.cfg" "$(ROOT)/tools/eic7700/load-ram.tcl" "$(BUILD)/recovery-addresses.tcl" \
  "$(BUILD)/ddr-LICENSE.txt" "$(BUILD)/ddr-COPYING.txt"
