# SPDX-License-Identifier: MIT
EDK_PLATFORM := SpacemitK3PicoItx
EDK_DSC := SpacemitPlatformPkg/K3/PicoItx/PicoItx.dsc
EDK_EXTRA_FLAGS :=
FD_FILE := SPACEMITK3.fd
FD_SIZE := 0x300000
COREBOOT_CONFIG := config.spacemit_k3_pico_itx_normal
COREBOOT_CROSS_COMPILE ?= $(CROSS_COMPILE)
COREBOOT_RECOVERY_OPTION :=
JTAG_DDR_SYMBOL :=
JTAG_DDR_VARIABLE :=
SBI_ADDRESS := 0x100000000
PAYLOAD_ADDRESS := 0x102000000
DTB_SOURCE := arch/riscv/boot/dts/spacemit/k3-pico-itx.dts
DTB_FILE := k3-pico-itx.dtb
DTB_COMPATIBLE := spacemit,k3-pico-itx
CBFS_DTB_NAME := k3-pico-itx.dtb
CBFS_REPLACE_DTB := FALSE
ROM_PACKER := tools/k3/image.py
RECOVERY_METHOD := bootrom
# OpenSBI initializes these M-mode AIA nodes, then disables them for S-mode.
FIRMWARE_IRQ_NODES := /soc/interrupt-controller@f1000000 /soc/interrupt-controller@f1800000
PACKAGE_EXTRA := "$(ROOT)/tools/settings.py"
