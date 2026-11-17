# SPDX-License-Identifier: MIT
include $(ROOT)/platforms/eic7700/common.mk
EDK_PLATFORM := MilkVMegrez
EDK_DSC := EswinPlatformPkg/Megrez/Megrez.dsc
FD_FILE := MEGREZ.fd
COREBOOT_CONFIG := config.milkv_megrez
DTB_SOURCE := arch/riscv/boot/dts/eswin/eic7700-milkv-megrez.dts
DTB_FILE := milkv-megrez.dtb
DTB_COMPATIBLE := milkv,megrez
RECOVERY_METHOD := usb-storage
PACKAGE_EXTRA := "$(BUILD)/ddr-build.json" "$(BUILD)/ddr-LICENSE.txt" "$(BUILD)/ddr-COPYING.txt"
