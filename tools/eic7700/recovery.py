# SPDX-License-Identifier: MIT
"""Immutable UART-loaded handoff code for P550 JTAG recovery."""
import struct

RISCV_J_SELF = 0x0000006f
SIFIVE_CFLUSH_D_L1 = 0xfc000073
RISCV_FENCE_RW_RW = 0x0330000f
RISCV_FENCE_I = 0x0000100f
RISCV_EBREAK = 0x00100073
RISCV_NOP = 0x00000013

# All harts initially execute the self-loop. OpenOCD runs the cache flush
# through EBREAK on each hart, then sets every PC to the ROM entry before
# starting coreboot. This keeps the stub safe from the later OpenSBI load.
WAIT_WORDS = (RISCV_J_SELF, SIFIVE_CFLUSH_D_L1, RISCV_FENCE_RW_RW,
              RISCV_FENCE_I, RISCV_EBREAK, RISCV_NOP, RISCV_NOP, RISCV_NOP)
MCPU_WAIT = struct.pack('<8I', *WAIT_WORDS)
HANDOFF_OFFSET = 4
HANDOFF_HALT_OFFSET = 16
WORK_AREA_OFFSET = 0x10000
WORK_AREA_SIZE = 0x2000


def recovery_values(layout):
    work = layout.wait_address + WORK_AREA_OFFSET
    if not (layout.wait_address + len(MCPU_WAIT) <= work and
            work + WORK_AREA_SIZE <= layout.mcpu_address):
        raise ValueError('recovery work area overlaps the handoff or ROM')
    return dict(rom_address=layout.mcpu_address, rom_size=layout.coreboot_bytes,
                wait_address=layout.wait_address,
                handoff_address=layout.wait_address + HANDOFF_OFFSET,
                handoff_halt_address=layout.wait_address + HANDOFF_HALT_OFFSET,
                work_area_address=work, work_area_size=WORK_AREA_SIZE)
