# SPDX-License-Identifier: MIT
"""Ruyi release image policy, separate from each SoC's BootROM format.

Addresses and sizes here must match the selected coreboot and EDK2 build.
The build checks these contracts before packaging.
"""
from dataclasses import dataclass

@dataclass(frozen=True)
class StageLayout:
    image_bytes: int
    firmware_bytes: int
    coreboot_bytes: int
    scpu_address: int
    mcpu_address: int
    wait_address: int

STAGE_LAYOUTS = {
    'p550': StageLayout(0x800000, 0x600000, 0x400000,
                        0x59000000, 0x90000000, 0x80000000),
}

DEFAULT_LAYOUTS = {
    'k3': (0x20d000, 0x1000),
    'unmatched': (0x10000, 0x1000),
    'p550': (0x720000, 0x10000),
}

# Coreboot FU740 recovery contract. All consumers use the generated Tcl.
FU740_RECOVERY = {
    'lim_base': 0x08000000,
    'bootblock_limit': 0x10000,
    'rom_base': 0x90000000,
    'rom_size': 0x800000,
    'lim_work_area': 0x08060000,
    'dram_work_area': 0x8e000000,
    'work_area_size': 0x2000,
}
