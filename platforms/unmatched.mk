# SPDX-License-Identifier: MIT
EDK_PLATFORM := SiFiveUnmatched
EDK_DSC := SiFivePlatformPkg/Unmatched/Unmatched.dsc
EDK_EXTRA_FLAGS := -D MAU_DEFAULT_ENABLE=$(EMULATION_ENABLE)
FD_FILE := UNMATCHED.fd
FD_SIZE := 0x400000
COREBOOT_CONFIG := config.sifive_hifive_unmatched
COREBOOT_CROSS_COMPILE ?= riscv64-unknown-elf-
COREBOOT_RECOVERY_OPTION := CONFIG_HIFIVE_UNMATCHED_JTAG_BOOT=y
JTAG_DDR_SYMBOL := cbmem_initialize_empty
JTAG_DDR_VARIABLE := unmatched_ddr_ready
SBI_ADDRESS := 0x80000000
PAYLOAD_ADDRESS := 0x82200000
DTB_SOURCE := arch/riscv/boot/dts/sifive/hifive-unmatched-a00.dts
DTB_FILE := hifive-unmatched.dtb
DTB_COMPATIBLE := sifive,hifive-unmatched-a00
CBFS_DTB_NAME := fallback/DTB
CBFS_REPLACE_DTB := TRUE
ROM_PACKER :=
RECOVERY_METHOD := jtag
FIRMWARE_IRQ_NODES :=
PACKAGE_EXTRA := "$(ROOT)/tools/unmatched/openocd.cfg" "$(ROOT)/tools/unmatched/load-ram.tcl" "$(BUILD)/recovery-addresses.tcl"
