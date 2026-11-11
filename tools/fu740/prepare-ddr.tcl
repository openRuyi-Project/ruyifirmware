# SPDX-License-Identifier: MIT
# Check capabilities before connecting to or resetting the board.
if {[command mode riscv smp] ne "exec"} {
    error "Use an OpenOCD build with riscv smp support"
}
# Memory contract from coreboot's FU740 memlayout.ld and Unmatched cbfs_ram.c.
set fu740_lim_base 0x08000000
set fu740_bootblock_limit 0x10000
set fu740_rom_base 0x90000000
set fu740_rom_size 0x800000
# OpenOCD scratch space stays outside the bootblock and loaded ROM.
set fu740_lim_work_area 0x08060000
set fu740_dram_work_area 0x8e000000
set fu740_work_area_size 0x2000
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
reset halt
adapter speed 5000
targets fu740.cpu1
riscv set_mem_access progbuf sysbus abstract
fu740.cpu1 configure -work-area-phys $fu740_lim_work_area \
    -work-area-size $fu740_work_area_size -work-area-backup 1
riscv set_ebreakm on
load_image $fu740_bootblock $fu740_lim_base bin
riscv smp off
verify_image $fu740_bootblock $fu740_lim_base bin
riscv smp on
bp $fu740_ddr_ready 4 hw
foreach hart {0 1 2 3 4} {
    targets fu740.cpu$hart
    # OpenSBI probes semihosting with EBREAK; it must trap in M-mode.
    riscv set_ebreakm off
    riscv set_ebreaks off
    riscv set_ebreaku off
    reg a0 $hart
    reg a1 0
    reg pc $fu740_lim_base
}
targets fu740.cpu1
resume
wait_halt $fu740_ddr_timeout_ms
# SMP halt events may select a different hart as the current target.
targets fu740.cpu1
set fu740_pc [dict get [get_reg -force {pc}] pc]
if {$fu740_pc != $fu740_ddr_ready} {
    error "coreboot stopped at $fu740_pc, expected $fu740_ddr_ready"
}

fu740.cpu1 configure -work-area-phys $fu740_dram_work_area \
    -work-area-size $fu740_work_area_size -work-area-backup 1
rbp $fu740_ddr_ready
