# SPDX-License-Identifier: MIT
# Set fu740_image_dir to the extracted package directory.
if {![info exists fu740_image_dir]} {
    error "Set fu740_image_dir to the recovery package directory"
}
set fu740_rom [file join $fu740_image_dir recovery-jtag.rom]
if {[file size $fu740_rom] != 0x800000} {
    error "Invalid FU740 recovery image size"
}
source [file join $fu740_image_dir prepare-ddr.tcl]
riscv smp off
riscv set_ebreakm on
load_image $fu740_rom $fu740_rom_base bin
verify_image $fu740_rom $fu740_rom_base bin
riscv set_ebreakm off
riscv smp on
resume
echo "coreboot RAM recovery started; SPI contents are unchanged"
