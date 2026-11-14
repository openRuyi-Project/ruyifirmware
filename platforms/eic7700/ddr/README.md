# EIC7700 DDR sources

This directory contains the shared SCPU training code, PHY configuration
and ECC initialization. See [SOURCE.txt](SOURCE.txt) for the image layout
and retained helper offsets.

For P550 build and installation instructions, see the
[P550 guide](../../../docs/p550/README.md#build-from-source).

## Build inputs

The image builder uses the bundled `ddr_fw.bin` and the PHY program data
in `phy-data.inc`. It checks the firmware size and SHA256 before building.
Run `sha256sum -c SHA256SUMS` in this directory to verify the input files.

See `LICENSE`, `COPYING` and the source-file headers for license and
copyright notices.
