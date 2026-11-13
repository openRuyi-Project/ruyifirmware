# SPDX-License-Identifier: MIT
# Load only after recovery-ddr.ihex has initialized DRAM and parked all harts.
if {![info exists eic7700_harts]} {
    error "Use openocd.cfg from this package. Recovery requires independent hart targets."
}
if {![info exists eic7700_image_dir]} {
    set eic7700_image_dir [file dirname [file normalize [info script]]]
}
set eic7700_rom [file join $eic7700_image_dir recovery-jtag.rom]
foreach required_file {recovery-jtag.rom recovery-addresses.tcl} {
    if {![file isfile [file join $eic7700_image_dir $required_file]]} {
        error "Missing $required_file. Extract a complete recovery package before running load-ram.tcl."
    }
}
source [file join $eic7700_image_dir recovery-addresses.tcl]
foreach required {rom_address rom_size wait_address handoff_address handoff_halt_address work_area_address work_area_size wait_words} {
    if {![info exists eic7700_$required]} {
        error "Incomplete recovery package. Extract a complete current package and upload its recovery-ddr.ihex first."
    }
}
set eic7700_pmp_lock_mask 0x8080808080808080
if {[file size $eic7700_rom] != $eic7700_rom_size} {
    error "Invalid EIC7700 recovery image size"
}

proc eic7700_recovery_guard {script} {
    if {[catch {uplevel 1 $script} reason]} {
        foreach hart $::eic7700_harts {
            catch {targets eic7700.cpu$hart; halt 3000}
        }
        error "RAM recovery stopped: $reason. Repeat fresh UART recovery before retrying."
    }
}

init
foreach hart $eic7700_harts {
    if {![eic7700.cpu$hart was_examined]} {
        error "EIC7700 JTAG is unavailable. Check SoC power with sompower-g and use FT4232 channel A. No image was loaded. Repeat the UART recovery steps in INSTALL.txt after a power cycle."
    }
}
eic7700_recovery_guard {
    foreach hart $eic7700_harts {
        targets eic7700.cpu$hart
        halt 3000
    }
    foreach hart $eic7700_harts {
        targets eic7700.cpu$hart
        set state [get_reg -force {pc pmpcfg0 pmpcfg2}]
        if {[dict get $state pc] != $eic7700_wait_address ||
            ([dict get $state pmpcfg0] & $eic7700_pmp_lock_mask) ||
            ([dict get $state pmpcfg2] & $eic7700_pmp_lock_mask)} {
            error "Hart $hart is not in fresh UART recovery: $state. Power-cycle in UART boot mode and upload this package's recovery-ddr.ihex before running load-ram.tcl."
        }
    }
    targets eic7700.cpu0
    set actual [eic7700.cpu0 read_memory $eic7700_wait_address 32 [llength $eic7700_wait_words]]
    for {set index 0} {$index < [llength $eic7700_wait_words]} {incr index} {
        if {[lindex $actual $index] != [lindex $eic7700_wait_words $index]} {
            error "UART recovery code does not match this package. Power-cycle in UART boot mode and upload the matching recovery-ddr.ihex. No ROM was loaded."
        }
    }
    eic7700.cpu0 configure -work-area-phys $eic7700_work_area_address \
        -work-area-size $eic7700_work_area_size -work-area-backup 0
    echo "Loading coreboot into DRAM..."
    load_image $eic7700_rom $eic7700_rom_address bin
    verify_image $eic7700_rom $eic7700_rom_address bin
    echo "RAM image verified. Starting the UART-loaded cache handoff..."
    foreach hart $eic7700_harts {
        targets eic7700.cpu$hart
        # The UART-loaded code is immutable until all harts finish this step.
        # Debug EBREAK ends each native cache flush.
        riscv set_ebreakm on
        set_reg [list mstatus 0 satp 0 mie 0 pc $eic7700_handoff_address]
        resume
        wait_halt 3000
        set state [get_reg -force {pc}]
        if {[dict get $state pc] != $eic7700_handoff_halt_address} {
            error "Hart $hart did not complete the cache handoff: $state. No hart has started coreboot."
        }
        riscv set_ebreakm off
        riscv set_ebreaks off
        riscv set_ebreaku off
        set_reg [list mstatus 0 satp 0 mie 0 a0 $hart a1 0 a2 0 \
            pc $eic7700_rom_address]
    }
    echo "Cache handoff verified on all four harts."
    # Park the secondary harts in coreboot before its working hart runs.
    # coreboot's smp_resume() expects them to have reached smp_pause().
    foreach hart [lrange $eic7700_harts 1 end] {
        targets eic7700.cpu$hart
        resume
    }
    targets eic7700.cpu0
    resume
    echo "coreboot RAM recovery started; SPI contents are unchanged"
}
