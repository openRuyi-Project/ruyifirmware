# SPDX-License-Identifier: MIT
# Set fu740_image_dir to the extracted package directory.
if {![info exists fu740_image_dir]} {
    error "Set fu740_image_dir to the recovery package directory"
}
source [file join $fu740_image_dir recovery-addresses.tcl]
set fu740_rom [file join $fu740_image_dir recovery-jtag.rom]
if {[file size $fu740_rom] != $fu740_rom_size} {
    error "Invalid FU740 recovery image size"
}
source [file join $fu740_image_dir prepare-ddr.tcl]
fu740_guard {
    riscv set_ebreakm on
    load_image $fu740_rom $fu740_rom_base bin
    verify_image $fu740_rom $fu740_rom_base bin
    riscv set_ebreakm off
    fu740_resume_all
    echo "coreboot RAM recovery started; SPI contents are unchanged"
}
