# SPDX-License-Identifier: MIT
EDK_FD := $(EDK_WORK)/Build/$(EDK_PLATFORM)/$(TARGET)_GCC/FV/$(FD_FILE)
DTB := $(BUILD)/$(DTB_FILE)
SBI_FIRMWARE := $(BUILD)/opensbi/platform/generic/firmware/fw_dynamic.elf
COREBOOT_TARGETS := coreboot-normal
IMAGE_FILES := normal-spi.bin
VERIFY_INPUTS := --rom normal-spi.bin normal
ifeq ($(RECOVERY_METHOD),jtag)
COREBOOT_TARGETS += coreboot-recovery
IMAGE_FILES += recovery-jtag.rom recovery-bootblock.bin $(FD_FILE) $(DTB_FILE)
VERIFY_INPUTS += --rom recovery-jtag.rom recovery --bootblock recovery-bootblock.bin
else ifeq ($(RECOVERY_METHOD),bootrom)
IMAGE_FILES += recovery-bootrom.bin
VERIFY_INPUTS += --bootrom recovery-bootrom.bin
else ifeq ($(RECOVERY_METHOD),uart-jtag)
IMAGE_FILES += recovery-jtag.rom recovery-ddr.ihex
VERIFY_INPUTS += --rom recovery-jtag.rom recovery --uart recovery-ddr.ihex
else
$(error Unsupported RECOVERY_METHOD=$(RECOVERY_METHOD))
endif

.PHONY: all normal recovery dtb edk2-normal opensbi-normal $(COREBOOT_TARGETS) multiarch source-info prepare prepare-inputs verify package help check-settings-abi
recovery: check-settings-abi

all: normal recovery source-info
	cd "$(BUILD)"
	sha256sum $(IMAGE_FILES) > SHA256SUMS

prepare:
	git -C "$(ROOT)" submodule sync --recursive
	git -C "$(ROOT)" submodule update --init --recursive --depth 1 --jobs $(JOBS)

check-settings-abi:
	$(PYTHON) "$(ROOT)/scripts/check-settings-abi.py" "$(SOURCES)" --cross-compile "$(CROSS_COMPILE)"

prepare-inputs: check-settings-abi
	if [[ -n "$(INPUT_PREPARER)" ]]; then
	  $(PYTHON) "$(ROOT)/$(INPUT_PREPARER)" "$(SOURCES)" "$(BUILD)" $(INPUT_PREPARER_ARGS)
	fi

multiarch:
	$(MAKE) -C "$(SOURCES)/MultiArchUefiPkg" EDK2_DIR="$(SOURCES)/edk2" \
	  MAU_BUILD_DIR="$(BUILD)/multiarch" TARGET=$(TARGET) JOBS=$(JOBS) MAU_DYNAMIC_POLICY=TRUE \
	  MAU_SUPPORTS_AARCH64_BINS=YES MAU_RISCV_ISA="$(RISCV_ISA)" CROSS_COMPILE="$(CROSS_COMPILE)" PYTHON="$(PYTHON)"

edk2-normal: multiarch
	mkdir -p "$(EDK_WORK)/Conf" "$(EDK_WORK)/X64EmulatorBin"
	$(PYTHON) "$(SOURCES)/edk2-ruyi/tools/fetch-amd-gop.py" "$(EDK_WORK)/AmdGop"
	cp "$(MAU_EFI)" "$(MAU_DEPEX)" "$(EDK_WORK)/X64EmulatorBin/"
	$(MAKE) -C "$(SOURCES)/edk2/BaseTools/Source/C" -j$(JOBS)
	export WORKSPACE="$(EDK_WORK)"
	export PACKAGES_PATH="$(EDK_WORK):$(SOURCES):$(SOURCES)/edk2-ruyi:$(SOURCES)/edk2-platforms:$(SOURCES)/edk2"
	export GCC_RISCV64_PREFIX="$(CROSS_COMPILE)" PYTHON_COMMAND="$(PYTHON)"
	export CONF_PATH="$(EDK_WORK)/Conf"
	unset EDK_TOOLS_PATH
	set +u
	source "$(SOURCES)/edk2/edksetup.sh"
	set -u
	build -a RISCV64 -p "$(EDK_DSC)" -t GCC -b $(TARGET) -n $(JOBS) \
	  -D X64EMU_ENABLE=TRUE -D DEBUG_PRINT_ERROR_LEVEL=$(DEBUG_PRINT_ERROR_LEVEL) $(EDK_EXTRA_FLAGS)
	cp "$(EDK_FD)" "$(BUILD)/$(FD_FILE)"

opensbi-normal:
	$(MAKE) -C "$(SOURCES)/opensbi" O="$(BUILD)/opensbi" PLATFORM=generic \
	  CROSS_COMPILE="$(CROSS_COMPILE)" PLATFORM_RISCV_ISA="$(RISCV_ISA)" \
	  FW_TEXT_START=$(SBI_ADDRESS) FW_OPTIONS=$(SBI_FW_OPTIONS) -j$(JOBS)

$(COREBOOT_TARGETS): coreboot-%: opensbi-normal
	mkdir -p "$(BUILD)"
	sed '/^CONFIG_DEFAULT_CONSOLE_LOGLEVEL_[0-9]=/d' "$(SOURCES)/coreboot/configs/$(COREBOOT_CONFIG)" > "$(BUILD)/coreboot-$*.config"
	printf 'CONFIG_DEFAULT_CONSOLE_LOGLEVEL_%s=y\n' "$(COREBOOT_LOGLEVEL)" >> "$(BUILD)/coreboot-$*.config"
	printf 'CONFIG_OPENSBI_BLOB_PATH="%s"\n' "$(SBI_FIRMWARE)" >> "$(BUILD)/coreboot-$*.config"
	if [[ "$*" == recovery ]]; then
	  printf '%s\n' '$(COREBOOT_RECOVERY_OPTION)' >> "$(BUILD)/coreboot-$*.config"
	fi
	CROSS_COMPILE_riscv="$(COREBOOT_CROSS_COMPILE)" $(MAKE) -C "$(SOURCES)/coreboot" \
	  obj="$(BUILD)/coreboot-$*" DOTCONFIG="$(BUILD)/coreboot-$*.config" UPDATED_SUBMODULES=1 olddefconfig
	CROSS_COMPILE_riscv="$(COREBOOT_CROSS_COMPILE)" $(MAKE) -C "$(SOURCES)/coreboot" \
	  obj="$(BUILD)/coreboot-$*" DOTCONFIG="$(BUILD)/coreboot-$*.config" UPDATED_SUBMODULES=1 -j$(JOBS)

dtb:
	mkdir -p "$(BUILD)"
	gcc -E -P -nostdinc -undef -D__DTS__ -x assembler-with-cpp -I"$(SOURCES)/linux/include" \
	  "$(SOURCES)/linux/$(DTB_SOURCE)" -o "$(BUILD)/$(DTB_FILE:.dtb=.dts)"
	dtc -I dts -O dtb -o "$(DTB)" "$(BUILD)/$(DTB_FILE:.dtb=.dts)"
	for node in $(FIRMWARE_IRQ_NODES); do
	  fdtput -t s "$(DTB)" "$$node" status okay
	done

# $(1): coreboot variant, $(2): output image.
define assemble_rom
	cp "$(BUILD)/coreboot-$(1)/coreboot.rom" "$(BUILD)/$(1).rom"
	if [[ "$(CBFS_REPLACE_DTB)" == TRUE ]]; then
	  "$(BUILD)/coreboot-$(1)/cbfstool" "$(BUILD)/$(1).rom" remove -n "$(CBFS_DTB_NAME)"
	fi
	"$(BUILD)/coreboot-$(1)/cbfstool" "$(BUILD)/$(1).rom" add -n "$(CBFS_DTB_NAME)" -t raw -f "$(DTB)"
	"$(BUILD)/coreboot-$(1)/cbfstool" "$(BUILD)/$(1).rom" add-flat-binary -n fallback/payload \
	  -f "$(EDK_FD)" -l $(PAYLOAD_ADDRESS) -e $(PAYLOAD_ADDRESS) -c lzma
	if [[ -n "$(ROM_PACKER)" ]]; then
	  $(PYTHON) "$(ROOT)/$(ROM_PACKER)" nor --rom "$(BUILD)/$(1).rom" \
	    $(ROM_PACK_ARGS) --output "$(BUILD)/$(2)"
	else
	  cp "$(BUILD)/$(1).rom" "$(BUILD)/$(2)"
	fi
	if [[ -n "$(SETTINGS_TOOL)" ]]; then
	  $(PYTHON) "$(ROOT)/$(SETTINGS_TOOL)" "$(BUILD)/$(2)" \
	    --default-emulation $(if $(filter TRUE,$(EMULATION_ENABLE)),enabled,disabled) --output "$(BUILD)/$(2)"
	fi
endef

normal: prepare-inputs edk2-normal dtb coreboot-normal
	$(call assemble_rom,normal,normal-spi.bin)

ifeq ($(RECOVERY_METHOD),jtag)
recovery: edk2-normal dtb coreboot-recovery
	$(call assemble_rom,recovery,recovery-jtag.rom)
	cp "$(BUILD)/coreboot-recovery/cbfs/fallback/bootblock.raw.bin" "$(BUILD)/recovery-bootblock.bin"
	$(PYTHON) "$(ROOT)/scripts/recovery-layout.py" $(BOARD) --output "$(BUILD)/recovery-addresses.tcl" \
	  --rom "$(BUILD)/recovery-jtag.rom" --nm "$(COREBOOT_CROSS_COMPILE)nm" \
	  --bootblock "$(BUILD)/coreboot-recovery/cbfs/fallback/bootblock.debug"
else ifeq ($(RECOVERY_METHOD),bootrom)
recovery: normal
	$(PYTHON) "$(ROOT)/$(ROM_PACKER)" ram --rom "$(BUILD)/normal-spi.bin" --output "$(BUILD)/recovery-bootrom.bin"
else
recovery: normal
	cp "$(BUILD)/normal.rom" "$(BUILD)/recovery-jtag.rom"
	$(PYTHON) "$(ROOT)/$(ROM_PACKER)" uart $(ROM_RECOVERY_PACK_ARGS) --output "$(BUILD)/recovery-ddr.ihex"
	$(PYTHON) "$(ROOT)/scripts/recovery-layout.py" $(BOARD) --output "$(BUILD)/recovery-addresses.tcl" \
	  --rom "$(BUILD)/recovery-jtag.rom"
endif

source-info:
	mkdir -p "$(BUILD)"
	for tree in coreboot opensbi edk2 edk2-ruyi linux edk2-platforms MultiArchUefiPkg unicorn; do
	  printf '%-18s ' "$$tree"
	  git -C "$(SOURCES)/$$tree" rev-parse HEAD
	done > "$(BUILD)/source-revisions.txt"
	cp "$(EDK_WORK)/AmdGop/amd-gop.json" "$(BUILD)/amd-gop.json"
	git -C "$(ROOT)" submodule status --recursive > "$(BUILD)/submodules.txt"
	$(CROSS_COMPILE)gcc --version > "$(BUILD)/toolchain.txt"
	printf 'BOARD=%s\nTARGET=%s\nX64EMU_ENABLE=TRUE\nEMULATION_ENABLE=%s\nMAU_SUPPORTS_AARCH64_BINS=YES\nCOREBOOT_LOGLEVEL=%s\nOPENSBI_FW_OPTIONS=%s\nEDK2_DEBUG_PRINT_ERROR_LEVEL=%s\nPXE_BOOT_INCLUDED=TRUE\nHTTP_BOOT_INCLUDED=TRUE\n' \
	  "$(BOARD)" "$(TARGET)" "$(EMULATION_ENABLE)" "$(COREBOOT_LOGLEVEL)" "$(SBI_FW_OPTIONS)" "$(DEBUG_PRINT_ERROR_LEVEL)" > "$(BUILD)/build-options.txt"
	printf 'OPENSBI_RISCV_ISA=%s\nEMULATOR_RISCV_ISA=%s\n' "$(RISCV_ISA)" "$(RISCV_ISA)" >> "$(BUILD)/build-options.txt"
	sed -n 's/^CONFIG_RISCV_ARCH=/COREBOOT_RISCV_ISA=/p' "$(BUILD)/coreboot-normal.config" >> "$(BUILD)/build-options.txt"

verify: all check-settings-abi
	$(PYTHON) "$(ROOT)/scripts/verify-images.py" "$(BUILD)" --images $(IMAGE_FILES) $(VERIFY_INPUTS) \
	  --fd "$(FD_FILE)" --fd-size $(FD_SIZE) --dtb "$(DTB_FILE)" --dtb-entry "$(CBFS_DTB_NAME)" \
	  --compatible "$(DTB_COMPATIBLE)" --address $(PAYLOAD_ADDRESS) \
	  --cbfstool "$(BUILD)/coreboot-normal/cbfstool"

package: verify
	$(PYTHON) "$(ROOT)/scripts/package.py" "$(BUILD)" "$(DIST)" $(PACKAGE_COMMON) $(PACKAGE_EXTRA)

help:
	printf '%s\n' 'make BOARD=<board> TARGET=RELEASE package' \
	  'Boards: $(BOARDS)' \
	  'TARGET=DEBUG enables diagnostic logging.' \
	  'Builds: build/<board>/<target>; packages: dist/<board>/<target>' \
	  'PXE and HTTP boot are configured in UEFI Setup.' \
	  'EMULATION_ENABLE=FALSE changes the initial driver-emulation setting.' \
	  'See docs/<board>/INSTALL.txt for installation and recovery.'
