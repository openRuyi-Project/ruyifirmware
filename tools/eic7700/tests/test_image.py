#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check ROM container boundaries and ordered UART records."""
import importlib.util
from pathlib import Path
import struct
import unittest

spec = importlib.util.spec_from_file_location(
    'p550_image', Path(__file__).resolve().parents[1] / 'image.py')
image = importlib.util.module_from_spec(spec)
spec.loader.exec_module(image)
layout = image.STAGE_LAYOUTS['p550']


class ImageTests(unittest.TestCase):
    def test_stage_alignment(self):
        for size in (16, 31, 32, 33, 256, 4096, 65535, 65536, 65537):
            with self.subTest(size=size):
                data = bytes(range(256)) * (size // 256) + bytes(range(size % 256))
                stages = [(data, 'sys', layout.scpu_address),
                          (b'ddr', 'ddr', layout.scpu_address),
                          (b'rom', 'rom', layout.mcpu_address)]
                spi = image.pack(stages, layout)
                entries = image.entries(spi, firmware_bytes=layout.firmware_bytes,
                                        stage_addresses=tuple(s[2] for s in stages))
                self.assertEqual(len(spi), layout.image_bytes)
                previous = image.HEADER.size + 3 * image.ENTRY.size
                for record, (payload, _, _) in zip(entries, stages):
                    offset, length, *_ = record
                    self.assertEqual(offset % 32, 0)
                    self.assertGreaterEqual(offset - previous, 0)
                    self.assertEqual(spi[previous:offset], b'\xff' * (offset - previous))
                    self.assertEqual(spi[offset + 256:offset + 256 + length], payload)
                    previous = offset + 256 + length
                self.assertEqual(spi[layout.firmware_bytes:],
                                 b'\xff' * (layout.image_bytes - layout.firmware_bytes))

    def test_uart_has_separate_signature_and_payload_transfers(self):
        for size in (1, 15, 16, 65535, 65536, 65537):
            with self.subTest(size=size):
                payloads = [b's' * size, b'd' * 65537, image.MCPU_WAIT]
                stages = [(p, str(i), a) for i, (p, a) in enumerate(
                    zip(payloads, image.uart_addresses(layout)))]
                encoded = image.pack(stages, layout, uart=True)
                self.assertEqual(image.check_uart(encoded, layout), payloads)
                transfers = image.uart_images(encoded)
                self.assertEqual([a for a, _ in transfers], [image.UART_TABLE_ADDRESS,
                    *[a for a in image.uart_addresses(layout) for _ in range(2)]])

    def test_uart_record_does_not_cross_a_64k_boundary(self):
        encoded = image.uart_transfer(0x3000fff9, b'x' * 32)
        for line in encoded.splitlines():
            record = bytes.fromhex(line[1:])
            length, address, kind = struct.unpack_from('>BHB', record)
            self.assertEqual(sum(record) & 255, 0)
            if kind == 0:
                self.assertLessEqual(address + length, 0x10000)

    def test_invalid_stage_sizes(self):
        for payload in (b'', b'x' * layout.firmware_bytes):
            with self.assertRaises(ValueError):
                image.pack([(payload, 'sys', layout.scpu_address),
                            (b'ddr', 'ddr', layout.scpu_address),
                            (b'rom', 'rom', layout.mcpu_address)], layout)
        with self.assertRaises(ValueError):
            image.pack([], layout)

    def test_format_accepts_another_release_layout(self):
        from dataclasses import replace
        other = replace(layout, image_bytes=0x400000, firmware_bytes=0x200000,
                        mcpu_address=0xa0000000)
        addresses = (other.scpu_address, other.scpu_address, other.mcpu_address)
        stages = [(b'payload', 'stage', address) for address in addresses]
        encoded = image.pack(stages, other)
        self.assertEqual(len(encoded), other.image_bytes)
        self.assertEqual(len(image.entries(encoded, firmware_bytes=other.firmware_bytes,
                                          stage_addresses=addresses)), 3)
        with self.assertRaises(ValueError):
            image.entries(encoded, firmware_bytes=other.firmware_bytes,
                          stage_addresses=(layout.scpu_address, layout.scpu_address,
                                           layout.mcpu_address))

    def test_uart_address_overflow(self):
        with self.assertRaises(ValueError):
            image.uart_transfer(0xfffffff0, b'x' * 17)


if __name__ == '__main__':
    unittest.main()
