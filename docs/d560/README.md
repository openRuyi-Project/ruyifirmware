# ESWIN D560

The D560 uses an ESWIN EIC7702X with eight SiFive P550 cores. Both CPU
clusters start at 1.8 GHz. The J30 and J29 PCIe slots each provide four
lanes. Leave pins 1 and 2 open on J12 and J40 to use the slots for PCIe
cards.

Follow the [installation guide](INSTALL.txt) to update both dies with
one firmware image. Allow about 20 minutes for the first automatic D2D
calibration. Stay with the board throughout calibration.

## Build

```sh
make BOARD=eic7702 TARGET=RELEASE package
```

The package is in `dist/d560/RELEASE/`. For an offline build, set
`D560_ESWIN_DIR` to the directory containing the two ESWIN bootloader
containers. [ESWIN bootloader download](https://github.com/eswincomputing/ebc7702-dev-board-ubuntu/releases/tag/2025.12.30)
