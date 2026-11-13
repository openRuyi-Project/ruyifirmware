#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check recovery handoff bounds and fail-before-write loader behavior."""
from pathlib import Path
import os
import struct
import subprocess
import sys
import tempfile
import unittest

TOOLS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(TOOLS))
from eic7700.recovery import MCPU_WAIT, WAIT_WORDS, recovery_values
from image_layout import STAGE_LAYOUTS

MOCK = r'''
set current eic7700.cpu0
set eic7700_harts {0 1 2 3}
set trace {}
array set pcs {}
proc init {} {}
proc echo {args} {}
proc halt {args} { lappend ::trace halt }
proc targets {target} { set ::current $target }
foreach hart {0 1 2 3} {
    proc eic7700.cpu$hart {command args} {
        switch $command {
            was_examined { return [expr {$::scenario ne "tap-down"}] }
            configure { lappend ::trace workspace; return }
            read_memory {
                if {$::scenario eq "old-uart"} { return [lrepeat 8 0xa001a001] }
                return $::eic7700_wait_words
            }
            default { error "Unsupported target command $command" }
        }
    }
}
proc get_reg {flag registers} {
    set pc $::eic7700_wait_address
    if {[info exists ::pcs($::current)]} { set pc $::pcs($::current) }
    set pmp 0
    if {$::current eq "eic7700.cpu2"} {
        if {$::scenario eq "wrong-pc"} { set pc 0x90000000 }
        if {$::scenario eq "locked-pmp"} { set pmp 0x80 }
    }
    return [dict create pc $pc pmpcfg0 $pmp pmpcfg2 0]
}
proc load_image {args} { lappend ::trace load }
proc verify_image {args} {
    lappend ::trace verify
    if {$::scenario eq "verify-failed"} { error "verification failed" }
}
proc riscv {command value} {
    if {$command ni {set_ebreakm set_ebreaks set_ebreaku} || $value ni {on off}} {
        error "Unsupported RISC-V command $command"
    }
}
proc set_reg {values} {
    set pc [dict get $values pc]
    set ::pcs($::current) $pc
    if {$pc == $::eic7700_handoff_address} {
        lappend ::trace flush-$::current
    } elseif {$pc == $::eic7700_rom_address} {
        if {[dict get $values a0] != [string index $::current end] ||
            [dict get $values a1] != 0 || [dict get $values a2] != 0} {
            error "wrong entry arguments"
        }
        lappend ::trace handoff-$::current
    } else { error "wrong program counter" }
}
proc resume {} {
    if {$::pcs($::current) == $::eic7700_rom_address} {
        lappend ::trace boot-$::current
    } else { lappend ::trace run-cache-$::current }
}
proc wait_halt {timeout} {
    if {$::scenario eq "flush-timeout"} { error "timeout" }
    set ::pcs($::current) $::eic7700_handoff_halt_address
    if {$::scenario eq "wrong-handoff"} { incr ::pcs($::current) 4 }
}
set status [catch {source [file join [file dirname [info script]] load-ram.tcl]} message]
puts "STATUS:$status:$message"
puts "TRACE:$trace"
'''


class RecoveryTests(unittest.TestCase):
    def test_handoff_and_workspace_are_separate(self):
        from dataclasses import replace
        layout = STAGE_LAYOUTS['p550']
        values = recovery_values(layout)
        self.assertEqual(values['handoff_address'], layout.wait_address + 4)
        halt_offset = values['handoff_halt_address'] - layout.wait_address
        self.assertEqual(struct.unpack_from('<I', MCPU_WAIT, halt_offset)[0], 0x00100073)
        self.assertEqual(struct.unpack('<8I', MCPU_WAIT), WAIT_WORDS)
        # Self-loop, existing SiFive cache flush, fences, and debug EBREAK.
        self.assertEqual(WAIT_WORDS[:5],
                         (0x6f, 0xfc000073, 0x0330000f, 0x100f, 0x100073))
        self.assertLessEqual(layout.wait_address + len(MCPU_WAIT), values['work_area_address'])
        self.assertLessEqual(values['work_area_address'] + values['work_area_size'], layout.mcpu_address)
        with self.assertRaises(ValueError):
            recovery_values(replace(layout, mcpu_address=layout.wait_address + 16))

    def run_loader(self, scenario):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            (out / 'load-ram.tcl').write_bytes((TOOLS / 'eic7700/load-ram.tcl').read_bytes())
            values = recovery_values(STAGE_LAYOUTS['p550'])
            with (out / 'recovery-jtag.rom').open('wb') as f:
                f.truncate(values['rom_size'])
            (out / 'recovery-addresses.tcl').write_text(''.join(
                f'set eic7700_{key} 0x{value:x}\n' for key, value in values.items()) +
                'set eic7700_wait_words {' + ' '.join(hex(x) for x in WAIT_WORDS) + '}\n')
            (out / 'mock.tcl').write_text(MOCK)
            return subprocess.check_output([
                os.environ.get('OPENOCD', 'openocd'), '-c', 'set scenario ' + scenario,
                '-f', str(out / 'mock.tcl'), '-c', 'shutdown'],
                stderr=subprocess.STDOUT, text=True)

    def test_old_openocd_command_subset_and_handoff(self):
        result = self.run_loader('ok')
        self.assertIn('STATUS:0:', result)
        self.assertIn('workspace load verify', result)
        for hart in range(4):
            self.assertIn(f'handoff-eic7700.cpu{hart}', result)
        self.assertTrue(result.rstrip().endswith('boot-eic7700.cpu0'))
        self.assertLess(result.index('handoff-eic7700.cpu3'), result.index('boot-eic7700.cpu1'))
        for hart in (1, 2, 3):
            self.assertLess(result.index(f'boot-eic7700.cpu{hart}'), result.index('boot-eic7700.cpu0'))

    def test_bad_jtag_or_recovery_state_prevents_loading(self):
        for scenario in ('tap-down', 'wrong-pc', 'locked-pmp', 'old-uart'):
            with self.subTest(scenario=scenario):
                result = self.run_loader(scenario)
                self.assertIn('STATUS:1:', result)
                trace = result.split('TRACE:')[1]
                self.assertNotIn('load', trace)
                self.assertNotIn('boot-', trace)
                if scenario == 'tap-down':
                    self.assertNotIn('halt', trace)

    def test_verification_failure_prevents_execution(self):
        result = self.run_loader('verify-failed')
        self.assertIn('STATUS:1:', result)
        trace = result.split('TRACE:')[1]
        self.assertIn('verify', trace)
        self.assertNotIn('handoff', trace)
        self.assertNotIn('boot-', trace)

    def test_cache_handoff_failure_prevents_coreboot_start(self):
        for scenario in ('flush-timeout', 'wrong-handoff'):
            with self.subTest(scenario=scenario):
                result = self.run_loader(scenario)
                self.assertIn('STATUS:1:', result)
                self.assertNotIn('boot-', result.split('TRACE:')[1])


if __name__ == '__main__':
    unittest.main()
