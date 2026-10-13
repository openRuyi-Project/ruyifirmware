# SPDX-License-Identifier: MIT
SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c
.ONESHELL:
.NOTPARALLEL:
.DEFAULT_GOAL := all

ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
SOURCES := $(ROOT)/src
TARGET ?= RELEASE
X64EMU_ENABLE ?= TRUE
ifneq ($(X64EMU_ENABLE),TRUE)
ifneq ($(X64EMU_ENABLE),FALSE)
$(error X64EMU_ENABLE must be TRUE or FALSE)
endif
endif
ifeq ($(TARGET),DEBUG)
COREBOOT_LOGLEVEL := 7
SBI_FW_OPTIONS := 0
DEBUG_PRINT_ERROR_LEVEL ?= 0x80000047
else ifeq ($(TARGET),RELEASE)
COREBOOT_LOGLEVEL := 4
# SBI_SCRATCH_NO_BOOT_PRINTS; keep the generic platform configuration.
SBI_FW_OPTIONS := 1
DEBUG_PRINT_ERROR_LEVEL ?= 0x80000002
else
$(error TARGET must be DEBUG or RELEASE)
endif
BUILD ?= $(ROOT)/build/$(TARGET)
BUILD := $(abspath $(BUILD))
export CCACHE_DIR := $(BUILD)/ccache
JOBS ?= 2
PYTHON ?= python3
CROSS_COMPILE ?= riscv64-linux-gnu-
EDK_WORK := $(BUILD)/edk2
EDK_NORMAL := $(EDK_WORK)/Build/SpacemitK3PicoItx/$(TARGET)_GCC/FV/SPACEMITK3.fd
SBI_NORMAL := $(BUILD)/opensbi-normal/platform/generic/firmware
MAU_BUILD := $(BUILD)/multiarch/Build/MultiArchUefiPkg/$(TARGET)_GCC/RISCV64
MAU_EFI := $(MAU_BUILD)/EmulatorDxe.efi
MAU_DEPEX := $(MAU_BUILD)/MultiArchUefiPkg/Drivers/Emulator/Emulator/OUTPUT/EmulatorDxe.depex
X64EMU_FLAGS := -D X64EMU_ENABLE=$(X64EMU_ENABLE)
ifeq ($(X64EMU_ENABLE),TRUE)
X64EMU_FLAGS += -D X64EMU_EFI="$(MAU_EFI)" -D X64EMU_DEPEX="$(MAU_DEPEX)"
edk2-normal: multiarch
endif
PACK := $(PYTHON) $(ROOT)/tools/k3image.py
EDK_LOG_FLAGS := -D DEBUG_PRINT_ERROR_LEVEL=$(DEBUG_PRINT_ERROR_LEVEL)

.PHONY: all normal recovery dtb edk2-normal opensbi-normal coreboot-normal source-info help

all: normal recovery source-info
	cd "$(BUILD)"
	sha256sum normal-spi.bin recovery-bootrom.bin > SHA256SUMS

normal: coreboot-normal
	mkdir -p "$(BUILD)/normal"
	cp "$(BUILD)/coreboot-normal/coreboot.rom" "$(BUILD)/normal/coreboot.rom"
	"$(BUILD)/coreboot-normal/cbfstool" "$(BUILD)/normal/coreboot.rom" add-flat-binary \
	  -f "$(EDK_NORMAL)" -n fallback/payload -l 0x102000000 -e 0x102000000 -c lzma
	"$(BUILD)/coreboot-normal/cbfstool" "$(BUILD)/normal/coreboot.rom" add \
	  -f "$(BUILD)/k3-pico-itx.dtb" -n k3-pico-itx.dtb -t raw
	$(PACK) nor --rom "$(BUILD)/normal/coreboot.rom" \
	  --bootblock "$(BUILD)/coreboot-normal/cbfs/fallback/bootblock.bin" \
	  --output "$(BUILD)/normal-spi.bin"
	"$(BUILD)/coreboot-normal/cbfstool" "$(BUILD)/normal-spi.bin" print -kv

recovery: normal
	$(PACK) ram --rom "$(BUILD)/normal-spi.bin" --output "$(BUILD)/recovery-bootrom.bin"

coreboot-normal: dtb opensbi-normal edk2-normal
	sed '/^CONFIG_DEFAULT_CONSOLE_LOGLEVEL_[0-9]=/d' "$(SOURCES)/coreboot/configs/config.spacemit_k3_pico_itx_normal" > "$(BUILD)/coreboot-normal.config"
	printf 'CONFIG_DEFAULT_CONSOLE_LOGLEVEL_%s=y\n' "$(COREBOOT_LOGLEVEL)" >> "$(BUILD)/coreboot-normal.config"
	printf 'CONFIG_OPENSBI_BLOB_PATH="%s"\n' "$(SBI_NORMAL)/fw_dynamic.elf" >> "$(BUILD)/coreboot-normal.config"
	$(MAKE) -C "$(SOURCES)/coreboot" obj="$(BUILD)/coreboot-normal" DOTCONFIG="$(BUILD)/coreboot-normal.config" \
	  UPDATED_SUBMODULES=1 CROSS_COMPILE_riscv="$(CROSS_COMPILE)" olddefconfig
	$(MAKE) -C "$(SOURCES)/coreboot" obj="$(BUILD)/coreboot-normal" DOTCONFIG="$(BUILD)/coreboot-normal.config" \
	  UPDATED_SUBMODULES=1 CROSS_COMPILE_riscv="$(CROSS_COMPILE)" -j$(JOBS)

opensbi-normal:
	mkdir -p "$(BUILD)/opensbi-normal"
	$(MAKE) -C "$(SOURCES)/opensbi" O="$(BUILD)/opensbi-normal" PLATFORM=generic \
	  CROSS_COMPILE="$(CROSS_COMPILE)" FW_TEXT_START=0x100000000 FW_OPTIONS=$(SBI_FW_OPTIONS) -j$(JOBS)

.PHONY: multiarch
multiarch:
	$(MAKE) -C "$(SOURCES)/MultiArchUefiPkg" EDK2_DIR="$(SOURCES)/edk2" \
	  MAU_BUILD_DIR="$(BUILD)/multiarch" TARGET=$(TARGET) JOBS=$(JOBS) \
	  CROSS_COMPILE="$(CROSS_COMPILE)" PYTHON="$(PYTHON)"

edk2-normal:
	mkdir -p "$(EDK_WORK)/Conf"
	$(MAKE) -C "$(SOURCES)/edk2/BaseTools/Source/C" -j$(JOBS)
	export WORKSPACE="$(EDK_WORK)"
	export PACKAGES_PATH="$(SOURCES)/edk2-ruyi:$(SOURCES)/edk2-platforms:$(SOURCES)/edk2"
	export GCC_RISCV64_PREFIX="$(CROSS_COMPILE)" PYTHON_COMMAND="$(PYTHON)"
	export CONF_PATH="$(EDK_WORK)/Conf"
	unset EDK_TOOLS_PATH
	set +u
	source "$(SOURCES)/edk2/edksetup.sh"
	set -u
	build -a RISCV64 -p SpacemitPlatformPkg/K3/PicoItx/PicoItx.dsc -t GCC -b $(TARGET) -n $(JOBS) $(EDK_LOG_FLAGS) $(X64EMU_FLAGS)

DTB := $(BUILD)/k3-pico-itx.dtb
dtb:
	mkdir -p "$(BUILD)"
	gcc -E -P -nostdinc -undef -D__DTS__ -x assembler-with-cpp -I"$(SOURCES)/linux/include" \
	  "$(SOURCES)/linux/arch/riscv/boot/dts/spacemit/k3-pico-itx.dts" -o "$(BUILD)/k3-pico-itx.dts"
	dtc -I dts -O dtb -o "$(DTB)" "$(BUILD)/k3-pico-itx.dts"
	fdtput -t s "$(DTB)" /aliases console "$$(fdtget -t s "$(DTB)" /aliases serial0)"
	for node in $$(fdtget -l "$(DTB)" /cpus); do
	  case "$$node" in cpu@*) hart=$$(fdtget -t x "$(DTB)" "/cpus/$$node" reg)
	    if (( 16#$$hart >= 8 )); then fdtput -t s "$(DTB)" "/cpus/$$node" status disabled; fi;; esac
	done
	fdtput -t i "$(DTB)" /soc/interrupt-controller@f1000000 riscv,guest-index-bits 0
	fdtput -d "$(DTB)" /soc/interrupt-controller@f1000000 riscv,num-guest-ids
	fdtput -t s "$(DTB)" /soc/interrupt-controller@f1000000 status okay
	fdtput -t s "$(DTB)" /soc/interrupt-controller@f1800000 status okay
	fdtput -c "$(DTB)" /soc/hart-controller@d4282800
	fdtput -t s "$(DTB)" /soc/hart-controller@d4282800 compatible spacemit,k3-hart-control
	fdtput -t s "$(DTB)" /soc/hart-controller@d4282800 reg-names apmu mpmu ciu cci dciu
	fdtput -t x "$(DTB)" /soc/hart-controller@d4282800 reg \
	  0 d4282800 0 400 0 d4050000 0 209c 0 d4282c00 0 400 0 d8500000 0 10000 0 d8440000 0 c000
	fdtput -t x "$(DTB)" /memory@100000000 reg 1 0 0 0

source-info:
	mkdir -p "$(BUILD)"
	for tree in coreboot opensbi edk2 edk2-ruyi linux edk2-platforms $(if $(filter TRUE,$(X64EMU_ENABLE)),MultiArchUefiPkg unicorn); do
	  printf '%-18s ' "$$tree"
	  git -C "$(SOURCES)/$$tree" rev-parse HEAD
	done > "$(BUILD)/source-revisions.txt"
	git -C "$(ROOT)" submodule status --recursive > "$(BUILD)/submodules.txt"
	$(CROSS_COMPILE)gcc --version > "$(BUILD)/toolchain.txt"
	printf 'TARGET=%s\nX64EMU_ENABLE=%s\nCOREBOOT_LOGLEVEL=%s\nOPENSBI_FW_OPTIONS=%s\nEDK2_DEBUG_PRINT_ERROR_LEVEL=%s\n' \
	  "$(TARGET)" "$(X64EMU_ENABLE)" "$(COREBOOT_LOGLEVEL)" "$(SBI_FW_OPTIONS)" "$(DEBUG_PRINT_ERROR_LEVEL)" > "$(BUILD)/build-options.txt"

help:
	printf '%s\n' 'make: RELEASE normal SPI + BootROM RAM recovery' \
	  'make TARGET=DEBUG: DEBUG builds in build/DEBUG' \
	  'X64EMU_ENABLE=FALSE: omit X64 UEFI emulation from normal firmware' \
	  'DEBUG_PRINT_ERROR_LEVEL=<mask>: override the target EDK2 logging mask' \
	  'make normal: build the shared firmware' \
	  'make recovery: also extract its BootROM entry' \
	  'make dtb | opensbi-normal | edk2-normal | coreboot-normal' \
	  'Overrides: BUILD=/absolute/output JOBS=8 CROSS_COMPILE=/path/riscv64-linux-gnu- PYTHON=python3'

.PHONY: prepare verify package
prepare:
	git -C "$(ROOT)" submodule sync --recursive
	git -C "$(ROOT)" submodule update --init --recursive --depth 1 --jobs $(JOBS)

verify: all
	$(PYTHON) "$(ROOT)/scripts/verify-images.py" "$(BUILD)"

package: verify
	$(PYTHON) "$(ROOT)/scripts/package.py" "$(BUILD)" "$(ROOT)/dist/$(TARGET)"
