# SPDX-License-Identifier: MIT
EDK_PLATFORM := SG2042
EDK_DSC := SophgoPlatformPkg/SG2042/SG2042.dsc
FD_FILE := SG2042.fd
COREBOOT_CONFIG := config.sophgo_sg2042
COREBOOT_CROSS_COMPILE := $(CROSS_COMPILE)
SBI_ADDRESS := 0x00200000
PAYLOAD_ADDRESS := 0x02000000
SG2042_DTBS := sg2042-evb-v1 sg2042-milkv-pioneer sg2042-evb-v2
X64EMU_ENABLE := $(EMULATION_ENABLE)
SG2042_FIP_FILE := $(ROOT)/platforms/sg2042/fip.bin
PACKAGE_COMMON := $(if $(filter TRUE,$(X64EMU_ENABLE)),"$(EDK_WORK)/AmdGop/amd-gop.json") --board-docs-only
