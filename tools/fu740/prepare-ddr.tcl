# SPDX-License-Identifier: MIT
if {![info exists fu740_harts]} {
    error "Use openocd.cfg and recovery scripts from the same package"
}
set fu740_ddr_timeout_ms 10000

# Set fu740_image_dir to the directory containing the recovery package.
if {![info exists fu740_image_dir]} {
    error "Set fu740_image_dir to the recovery package directory"
}
set fu740_bootblock [file join $fu740_image_dir recovery-bootblock.bin]
source [file join $fu740_image_dir recovery-addresses.tcl]
if {[file size $fu740_bootblock] > $fu740_bootblock_limit ||
    $fu740_ddr_ready < $fu740_lim_base ||
    $fu740_ddr_ready >= $fu740_lim_base + $fu740_bootblock_limit} {
    error "Invalid FU740 recovery image or DDR checkpoint"
}

init
fu740_guard {
    reset halt
    targets fu740.cpu1
    riscv set_mem_access progbuf sysbus abstract
    fu740.cpu1 configure -work-area-phys $fu740_lim_work_area \
        -work-area-size $fu740_work_area_size -work-area-backup 1
    riscv set_ebreakm on
    load_image $fu740_bootblock $fu740_lim_base bin
    verify_image $fu740_bootblock $fu740_lim_base bin
    bp $fu740_ddr_ready 4 hw
    foreach hart $::fu740_harts {
        targets fu740.cpu$hart
        # OpenSBI probes semihosting with EBREAK; it must trap in M-mode.
        riscv set_ebreakm off
        riscv set_ebreaks off
        riscv set_ebreaku off
        reg a0 $hart
        reg a1 0
        reg pc $fu740_lim_base
    }
    fu740_resume_all
    wait_halt $fu740_ddr_timeout_ms
    # The breakpoint stops hart 1 only. Park every other hart before using DRAM.
    fu740_halt_all
    set fu740_pc [dict get [get_reg -force {pc}] pc]
    if {$fu740_pc != $fu740_ddr_ready} {
        error "coreboot stopped at $fu740_pc, expected $fu740_ddr_ready"
    }

    fu740.cpu1 configure -work-area-phys $fu740_dram_work_area \
        -work-area-size $fu740_work_area_size -work-area-backup 1
    rbp $fu740_ddr_ready
}
