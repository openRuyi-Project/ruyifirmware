# EIC7700 DDR firmware

These unmodified binaries come from the ESWIN firmware repository at
commit `8ad2177026e982acc0e14ef1e9ebe682aff6dfca`:

[Esbd-77serial-firmware](https://github.com/eswincomputing/Esbd-77serial-firmware/tree/8ad2177026e982acc0e14ef1e9ebe682aff6dfca/ddr)

| File | Mode |
| --- | --- |
| `ddr_fw.bin` | Non-ECC |
| `ddr_fw_ecc.bin` | Inline ECC |

Both programs run at `0x59000000` on the SCPU. SPI boot uses the DDR
dispatcher to select a program. UART recovery always uses `ddr_fw.bin`.

The binaries use Apache-2.0. `LICENSE` and `COPYING` are copied unchanged
from the same upstream commit. `SHA256SUMS` records all four files.
To verify them, run `sha256sum -c SHA256SUMS` in this directory.
