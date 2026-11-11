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


class ImageTests(unittest.TestCase):
    def test_stage_alignment(self):
        for size in (16, 31, 32, 33, 256, 4096, 65535, 65536, 65537):
            with self.subTest(size=size):
                data = bytes(range(256)) * (size // 256) + bytes(range(size % 256))
                stages = [(data, 'sys', image.SCPU_ADDRESS),
                          (b'ddr', 'ddr', image.SCPU_ADDRESS),
                          (b'rom', 'rom', image.MCPU_ADDRESS)]
                spi = image.pack(stages)
                entries = image.entries(spi)
                self.assertEqual(len(spi), image.IMAGE_BYTES)
                previous = image.HEADER.size + 3 * image.ENTRY.size
                for record, (payload, _, _) in zip(entries, stages):
                    offset, length, *_ = record
                    self.assertEqual(offset % 32, 0)
                    self.assertGreaterEqual(offset - previous, 0)
                    self.assertEqual(spi[previous:offset], b'\xff' * (offset - previous))
                    self.assertEqual(spi[offset + 256:offset + 256 + length], payload)
                    previous = offset + 256 + length
                self.assertEqual(spi[image.FIRMWARE_BYTES:],
                                 b'\xff' * (image.IMAGE_BYTES - image.FIRMWARE_BYTES))

    def test_uart_has_separate_signature_and_payload_transfers(self):
        for size in (1, 15, 16, 65535, 65536, 65537):
            with self.subTest(size=size):
                payloads = [b's' * size, b'd' * 65537, image.MCPU_WAIT]
                stages = [(p, str(i), a) for i, (p, a) in enumerate(
                    zip(payloads, image.UART_STAGE_ADDRESSES))]
                encoded = image.pack(stages, uart=True)
                self.assertEqual(image.check_uart(encoded), payloads)
                transfers = image.uart_images(encoded)
                self.assertEqual([a for a, _ in transfers], [image.UART_TABLE_ADDRESS,
                    *[a for a in image.UART_STAGE_ADDRESSES for _ in range(2)]])

    def test_uart_record_does_not_cross_a_64k_boundary(self):
        encoded = image.uart_transfer(0x3000fff9, b'x' * 32)
        for line in encoded.splitlines():
            record = bytes.fromhex(line[1:])
            length, address, kind = struct.unpack_from('>BHB', record)
            self.assertEqual(sum(record) & 255, 0)
            if kind == 0:
                self.assertLessEqual(address + length, 0x10000)

    def test_invalid_stage_sizes(self):
        for payload in (b'', b'x' * image.FIRMWARE_BYTES):
            with self.assertRaises(ValueError):
                image.pack([(payload, 'sys', image.SCPU_ADDRESS),
                            (b'ddr', 'ddr', image.SCPU_ADDRESS),
                            (b'rom', 'rom', image.MCPU_ADDRESS)])
        with self.assertRaises(ValueError):
            image.pack([])

    def test_uart_address_overflow(self):
        with self.assertRaises(ValueError):
            image.uart_transfer(0xfffffff0, b'x' * 17)


if __name__ == '__main__':
    unittest.main()
