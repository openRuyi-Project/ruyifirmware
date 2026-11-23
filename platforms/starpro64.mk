# SPDX-License-Identifier: MIT
include $(ROOT)/platforms/eic7700/common.mk
COREBOOT_CONFIG := config.pine64_starpro64
DTB_SOURCE := arch/riscv/boot/dts/eswin/eic7700-pine64-starpro64.dts
DTB_FILE := pine64-starpro64.dtb
DTB_COMPATIBLE := pine64,starpro64
RECOVERY_METHOD := usb-storage
PACKAGE_EXTRA := "$(BUILD)/ddr-build.json" "$(BUILD)/ddr-LICENSE.txt" "$(BUILD)/ddr-COPYING.txt"
