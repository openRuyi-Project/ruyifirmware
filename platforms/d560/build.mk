# SPDX-License-Identifier: MIT
IMAGE_FILES := firmware.bin bootchain-die0.bin bootchain-die1.bin normal-spi-die0.bin normal-spi-die1.bin
D560_DTS ?= $(SOURCES)/linux/arch/riscv/boot/dts/eswin/eic7702-eswin-d560.dts
D560_IMAGE := $(ROOT)/platforms/d560/bootchain.py
D560_D2D_DIR ?= $(ROOT)/platforms/eic7702
D560_ENTRIES := $(BUILD)/d2d-entry0.bin $(BUILD)/d2d-entry1.bin

$(BUILD)/d2d-entry%.bin: $(ROOT)/platforms/eic7702/d2d-entry.S
	mkdir -p "$(BUILD)"
	$(CROSS_COMPILE)gcc -march=rv32imac -mabi=ilp32 -DDIE=$* -c "$<" -o "$@.o"
	$(CROSS_COMPILE)objcopy -O binary -j .text.d2d_entry "$@.o" "$@"


dtb:
	mkdir -p "$(BUILD)"
	gcc -E -P -nostdinc -undef -D__DTS__ -x assembler-with-cpp \
	  -I"$(SOURCES)/linux/include" "$(D560_DTS)" | dtc -I dts -O dtb -o "$(DTB)"

normal: edk2-normal dtb coreboot-normal $(D560_ENTRIES)
	cp "$(BUILD)/coreboot-normal/coreboot.rom" "$(BUILD)/d560.rom"
	"$(BUILD)/coreboot-normal/cbfstool" "$(BUILD)/d560.rom" add -n fallback/DTB -t raw -a 8 -f "$(DTB)"
	"$(BUILD)/coreboot-normal/cbfstool" "$(BUILD)/d560.rom" add-flat-binary -n fallback/payload \
	  -f "$(EDK_FD)" -l $(PAYLOAD_ADDRESS) -e $(PAYLOAD_ADDRESS) -c lzma
	$(PYTHON) "$(D560_IMAGE)" build "$(D560_ESWIN_DIR)" "$(BUILD)" --d2d-dir "$(abspath $(D560_D2D_DIR))"

recovery: normal

source-info:
	mkdir -p "$(BUILD)"
	for tree in coreboot opensbi edk2 edk2-ruyi linux edk2-platforms MultiArchUefiPkg unicorn; do
	  printf '%-18s %s\n' "$$tree" "$$(git -C "$(SOURCES)/$$tree" rev-parse HEAD)"
	done > "$(BUILD)/source-revisions.txt"
	git -C "$(ROOT)" submodule status --recursive > "$(BUILD)/submodules.txt"
	$(CROSS_COMPILE)gcc --version > "$(BUILD)/toolchain.txt"
	printf '%s\n' "BOARD=$(PACKAGE_BOARD)" "TARGET=$(TARGET)" "RISCV_ISA=$(RISCV_ISA)" \
	  "X64EMU_ENABLE=$(X64EMU_ENABLE)" > "$(BUILD)/build-options.txt"
ifeq ($(X64EMU_ENABLE),TRUE)
	cp "$(EDK_WORK)/AmdGop/amd-gop.json" "$(BUILD)/amd-gop.json"
endif

verify: all
	$(PYTHON) "$(D560_IMAGE)" verify "$(D560_ESWIN_DIR)" "$(BUILD)" --d2d-dir "$(abspath $(D560_D2D_DIR))"
