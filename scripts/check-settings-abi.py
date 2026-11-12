#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compare image-tool contracts with the selected firmware C headers."""
import argparse
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import settings
from image_layout import STAGE_LAYOUTS


def check(sources, cross_compile):
    edk2 = sources / 'edk2'
    platform = sources / 'edk2-ruyi'
    includes = [edk2 / 'MdePkg/Include', edk2 / 'MdePkg/Include/RiscV64']
    includes += [platform / name / 'Include' for name in (
        'RuyiPlatformPkg', 'SpacemitPlatformPkg', 'SiFivePlatformPkg', 'EswinPlatformPkg')]
    # Compile the actual structs and macros. Do not parse #define text or
    # execute a target binary on the build host.
    fields = [
        ('magic', 'SETTINGS_RECORD_MAGIC', settings.DEFAULT_MAGIC),
        ('version', 'SETTINGS_RECORD_VERSION', settings.DEFAULT_VERSION),
        ('record size', 'sizeof (RUYI_SETTINGS_RECORD)', settings.DEFAULT_RECORD.size),
        ('commit marker', 'SETTINGS_RECORD_COMMIT', settings.DEFAULT_COMMIT),
        ('slot count', 'SETTINGS_SLOT_COUNT', settings.SLOT_COUNT),
        ('value mask', 'RUYI_SETTINGS_MASK', settings.DEFAULT_MASK),
    ]
    # The C CRC covers all bytes before Crc32. Python covers DEFAULT_BODY.
    for field, offset in [('Magic', 0), ('Version', 4), ('Size', 6),
                          ('Generation', 8), ('Values', 12),
                          ('Crc32', settings.DEFAULT_BODY.size), ('Commit', 20)]:
        fields.append((field + ' offset', f'OFFSET_OF (RUYI_SETTINGS_RECORD, {field})', offset))
    for flag, value in [('EMULATION', 1), ('PXE', 2), ('HTTP', 4)]:
        fields.append((flag, 'RUYI_SETTING_' + flag, value))
    for board, prefix in [('k3', 'K3'), ('unmatched', 'UNMATCHED'), ('p550', 'P550')]:
        for suffix, value in zip(('OFFSET', 'STRIDE'), settings.DEFAULT_LAYOUTS[board]):
            fields.append((board + ' ' + suffix, prefix + '_DEFAULTS_' + suffix, value))
    layout = STAGE_LAYOUTS['p550']
    fields += [
        ('P550 firmware area', 'P550_FIRMWARE_BYTES', layout.firmware_bytes),
        ('P550 NVRAM start', 'P550_NV_OFFSET', layout.firmware_bytes),
        ('EIC7700 ROM load', 'EIC7700_ROM_BUFFER', layout.mcpu_address),
    ]
    # A recognizable record also checks target byte order and field widths.
    source = '''#include <Uefi.h>
#include <Library/PlatformSettingsLib.h>
#include <Library/PremierP550NvFlashLib.h>
#include <IndustryStandard/K3FirmwareDefaults.h>
#include <IndustryStandard/UnmatchedFirmwareDefaults.h>
#include <IndustryStandard/P550FirmwareDefaults.h>
#include <IndustryStandard/Eic7700BootConfig.h>
#include "soc/addressmap.h"
__attribute__((section(".abi"), used))
const UINT32 Contract[] = {
'''
    source += ',\n'.join(expr for _, expr, _ in fields) + '\n};\n'
    source += '''STATIC_ASSERT (P550_NV_OFFSET + NV_TOTAL_SIZE <= EIC7700_BOOT_CONFIG_OFFSET,
  "NVRAM overlaps early boot settings");
STATIC_ASSERT (EIC7700_BOOT_CONFIG_OFFSET + EIC7700_BOOT_CONFIG_SLOT_SIZE *
  EIC7700_BOOT_CONFIG_SLOT_COUNT <= P550_DEFAULTS_OFFSET,
  "Early boot settings overlap platform defaults");
'''
    encoded = settings.encode(settings.DEFAULT_MASK, generation=0x12345678)
    crc = struct.unpack_from('<I', encoded, settings.DEFAULT_BODY.size)[0]
    source += f'''__attribute__((section(".record"), used))
const RUYI_SETTINGS_RECORD Record = {{SETTINGS_RECORD_MAGIC,
  SETTINGS_RECORD_VERSION, sizeof (RUYI_SETTINGS_RECORD), 0x12345678,
  RUYI_SETTINGS_MASK, {crc}U, SETTINGS_RECORD_COMMIT}};
'''
    includes.append(sources / 'coreboot/src/soc/eswin/eic7700/include')
    with tempfile.TemporaryDirectory(prefix='ruyi-abi-') as tmp:
        obj = Path(tmp) / 'abi.o'
        subprocess.run([cross_compile + 'gcc', '-x', 'c', '-c', '-std=c11',
                        '-ffreestanding', '-fshort-wchar', '-Wall', '-Werror',
                        *['-I' + str(p) for p in includes], '-o', str(obj), '-'],
                       input=source, text=True, check=True)
        results = {}
        for section in ('.abi', '.record'):
            output = Path(tmp) / (section + '.bin')
            subprocess.run([cross_compile + 'objcopy', '-O', 'binary',
                            '--only-section=' + section, str(obj), str(output)], check=True)
            results[section] = output.read_bytes()
        expected = struct.pack('<' + 'I' * len(fields), *[v for _, _, v in fields])
        if results['.abi'] != expected:
            actual = struct.unpack('<' + 'I' * len(fields), results['.abi'])
            errors = [f'{name}: C={got:#x}, Python={want:#x}'
                      for (name, _, want), got in zip(fields, actual) if got != want]
            raise ValueError('firmware/image ABI mismatch: ' + ', '.join(errors))
        if results['.record'] != encoded:
            raise ValueError('C and Python settings records differ')
    for board, (offset, stride) in settings.DEFAULT_LAYOUTS.items():
        image_bytes = STAGE_LAYOUTS[board].image_bytes if board in STAGE_LAYOUTS else settings.LAYOUTS[board][0]
        if stride < len(encoded) or offset + settings.SLOT_COUNT * stride > image_bytes:
            raise ValueError(board + ': settings slots exceed the image')
    return {'settings_abi': 'passed', 'checked_fields': len(fields),
            'c_record_matches_python': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('sources', type=Path)
    parser.add_argument('--cross-compile', required=True)
    args = parser.parse_args()
    print(json.dumps(check(args.sources.resolve(), args.cross_compile), indent=2))


if __name__ == '__main__':
    main()
