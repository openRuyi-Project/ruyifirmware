# SPDX-License-Identifier: MIT
IMAGE_FILES += recovery-sd.img

.PHONY: sg2042-fip
sg2042-fip:
	cd "$(ROOT)/platforms/sg2042" && sha256sum -c SHA256SUMS

dtb:
	mkdir -p "$(BUILD)"
	for name in $(SG2042_DTBS); do
	  gcc -E -P -nostdinc -undef -D__DTS__ -x assembler-with-cpp -I"$(SOURCES)/linux/include" \
	    "$(SOURCES)/linux/arch/riscv/boot/dts/sophgo/$$name.dts" | dtc -I dts -O dtb -o "$(BUILD)/$$name.dtb"
	done

normal: sg2042-fip edk2-normal dtb coreboot-normal
	cd "$(BUILD)"
	work=$$(mktemp -d "$(BUILD)/.pack.XXXXXXXX")
	trap 'rm -rf "$$work"' EXIT
	rom="$$work/zsbl.bin"
	cp coreboot-normal/coreboot.rom "$$rom"
	for name in $(SG2042_DTBS); do
	  coreboot-normal/cbfstool "$$rom" add -n "$$name.dtb" -t raw -a 8 -f "$$name.dtb"
	done
	coreboot-normal/cbfstool "$$rom" add-flat-binary -n fallback/payload -c lzma \
	  -f "$(FD_FILE)" -l $(PAYLOAD_ADDRESS) -e $(PAYLOAD_ADDRESS)
	$(PYTHON) "$(ROOT)/platforms/sg2042/spi.py" "$(SG2042_FIP_FILE)" \
	  "$$rom" "$$work/normal-spi.bin"
	mv "$$rom" "$$work/normal-spi.bin" .

recovery: normal
	cd "$(BUILD)"
	work=$$(mktemp -d "$(BUILD)/.pack.XXXXXXXX")
	trap 'rm -rf "$$work"' EXIT
	cd "$$work"
	truncate -s 64M recovery-sd.img
	export MTOOLSRC="$$work/mtoolsrc"
	printf '%s\n' 'drive p: file="recovery-sd.img" partition=1' > "$$MTOOLSRC"
	mpartition -I -c -s 32 -h 64 -T 0x0c -b 2048 -a p:
	mformat -F -c 1 -v BOOTFIRM p:
	mcopy "$(SG2042_FIP_FILE)" "$(BUILD)/zsbl.bin" p:/
	mmd p:/riscv64
	for name in $(SG2042_DTBS); do
	  mcopy "$(BUILD)/$$name.dtb" p:/riscv64/
	done
	mv recovery-sd.img "$(BUILD)/"

source-info: sg2042-fip
	mkdir -p "$(BUILD)"
	for tree in coreboot opensbi edk2 edk2-ruyi edk2-platforms linux MultiArchUefiPkg unicorn; do
	  printf '%-20s %s\n' "$$tree" "$$(git -C "$(SOURCES)/$$tree" rev-parse HEAD)"
	done > "$(BUILD)/source-revisions.txt"
	cat "$(ROOT)/platforms/sg2042/SHA256SUMS" >> "$(BUILD)/source-revisions.txt"
	git -C "$(ROOT)" submodule status --recursive > "$(BUILD)/submodules.txt"
	$(CROSS_COMPILE)gcc --version > "$(BUILD)/toolchain.txt"
	printf 'BOARD=%s\nTARGET=%s\nX64EMU_ENABLE=%s\nCOREBOOT_LOGLEVEL=%s\nOPENSBI_FW_OPTIONS=%s\n' \
	  "$(BOARD)" "$(TARGET)" "$(X64EMU_ENABLE)" "$(COREBOOT_LOGLEVEL)" "$(SBI_FW_OPTIONS)" > "$(BUILD)/build-options.txt"

verify: all
	$(PYTHON) "$(ROOT)/platforms/sg2042/verify.py" "$(BUILD)" "$(SG2042_FIP_FILE)" "$(SBI_FIRMWARE)"
