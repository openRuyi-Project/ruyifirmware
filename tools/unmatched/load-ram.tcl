# SPDX-License-Identifier: MIT
# Memory contract from coreboot's FU740 memlayout.ld and Unmatched cbfs_ram.c.
set unmatched_lim_base 0x08000000
set unmatched_bootblock_limit 0x10000
set unmatched_rom_base 0x90000000
set unmatched_rom_size 0x2000000
# OpenOCD scratch space stays outside the bootblock and loaded ROM.
set unmatched_lim_work_area 0x08060000
set unmatched_dram_work_area 0x8e000000
set unmatched_work_area_size 0x2000
set unmatched_ddr_timeout_ms 10000

# Set unmatched_image_dir to the directory containing the recovery package.
if {![info exists unmatched_image_dir]} {
    error "Set unmatched_image_dir to the recovery package directory"
}
set unmatched_bootblock [file join $unmatched_image_dir recovery-bootblock.bin]
set unmatched_rom [file join $unmatched_image_dir recovery-jtag.rom]
source [file join $unmatched_image_dir recovery-addresses.tcl]
if {[file size $unmatched_bootblock] > $unmatched_bootblock_limit ||
    [file size $unmatched_rom] != $unmatched_rom_size ||
    $unmatched_ddr_ready < $unmatched_lim_base ||
    $unmatched_ddr_ready >= $unmatched_lim_base + $unmatched_bootblock_limit} {
    error "Invalid Unmatched recovery image or DDR checkpoint"
}

init
reset halt
adapter speed 5000
targets fu740.cpu1
riscv set_mem_access progbuf sysbus abstract
fu740.cpu1 configure -work-area-phys $unmatched_lim_work_area \
    -work-area-size $unmatched_work_area_size -work-area-backup 1
riscv set_ebreakm on
load_image $unmatched_bootblock $unmatched_lim_base bin
verify_image $unmatched_bootblock $unmatched_lim_base bin
bp $unmatched_ddr_ready 4 hw
foreach hart {0 1 2 3 4} {
    targets fu740.cpu$hart
    # OpenSBI probes semihosting with EBREAK; it must trap in M-mode.
    riscv set_ebreakm off
    riscv set_ebreaks off
    riscv set_ebreaku off
    reg a0 $hart
    reg a1 0
    reg pc $unmatched_lim_base
}
targets fu740.cpu1
resume
wait_halt $unmatched_ddr_timeout_ms
# SMP halt events may select a different hart as the current target.
targets fu740.cpu1
set unmatched_pc [dict get [get_reg -force {pc}] pc]
if {$unmatched_pc != $unmatched_ddr_ready} {
    error "coreboot stopped at $unmatched_pc, expected $unmatched_ddr_ready"
}

fu740.cpu1 configure -work-area-phys $unmatched_dram_work_area \
    -work-area-size $unmatched_work_area_size -work-area-backup 1
riscv set_ebreakm on
load_image $unmatched_rom $unmatched_rom_base bin
verify_image $unmatched_rom $unmatched_rom_base bin
riscv set_ebreakm off
rbp $unmatched_ddr_ready
resume
echo "coreboot RAM recovery started; SPI contents are unchanged"
