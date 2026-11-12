# SPDX-License-Identifier: MIT
# Initialize DDR from the recovery bootblock before running a flash algorithm.
if {![info exists fu740_image_dir]} {
    error "Set fu740_image_dir to the firmware package directory"
}
source [file join $fu740_image_dir recovery-addresses.tcl]
set fu740_spi_image [file join $fu740_image_dir normal-spi.bin]
if {[file size $fu740_spi_image] != $fu740_rom_size} {
    error "Invalid FU740 SPI image size"
}
source [file join $fu740_image_dir prepare-ddr.tcl]
fu740_guard {
    fu740_spi_probe
    targets fu740.cpu1
    riscv set_ebreakm on
    flash write_image erase $fu740_spi_image 0x20000000 bin
    verify_image $fu740_spi_image 0x20000000 bin
    echo "Complete SPI image verified"
    foreach hart $::fu740_harts {
        targets fu740.cpu$hart
        riscv set_ebreakm off
        riscv set_ebreaks off
        riscv set_ebreaku off
    }
    reset run
}
