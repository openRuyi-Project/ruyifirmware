# SPDX-License-Identifier: MIT
# Load only after recovery-ddr.ihex has initialized DRAM and parked all harts.
if {![info exists eic7700_image_dir]} {
    error "Set eic7700_image_dir to the recovery package directory"
}
set eic7700_rom [file join $eic7700_image_dir recovery-jtag.rom]
set eic7700_rom_address 0x90000000
set eic7700_rom_size 0x400000
set eic7700_wait_address 0x80000000
set eic7700_pmp_lock_mask 0x8080808080808080
if {[file size $eic7700_rom] != $eic7700_rom_size} {
    error "Invalid EIC7700 recovery image size"
}

init
halt 3000
foreach hart {0 1 2 3} {
    targets eic7700.cpu$hart
    set state [get_reg -force {pc pmpcfg0 pmpcfg2}]
    if {[dict get $state pc] != $eic7700_wait_address ||
        ([dict get $state pmpcfg0] & $eic7700_pmp_lock_mask) ||
        ([dict get $state pmpcfg2] & $eic7700_pmp_lock_mask)} {
        error "Hart $hart is not in fresh UART recovery: $state"
    }
}
targets eic7700.cpu0
load_image $eic7700_rom $eic7700_rom_address bin
verify_image $eic7700_rom $eic7700_rom_address bin
foreach hart {0 1 2 3} {
    targets eic7700.cpu$hart
    # Flush the data cache, then FENCE RW,RW, FENCE.I and debug EBREAK.
    riscv exec_progbuf 0xfc000073 0x0330000f 0x0000100f 0x00100073
    riscv set_ebreakm off
    riscv set_ebreaks off
    riscv set_ebreaku off
    set_reg [list mstatus 0 satp 0 mie 0 a0 $hart a1 0 a2 0 pc $eic7700_rom_address]
}
targets eic7700.cpu0
resume
echo "coreboot RAM recovery started; SPI contents are unchanged"
