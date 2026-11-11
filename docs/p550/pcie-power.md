# PCIe power checks

Insufficient or unstable power can prevent a PCIe card from establishing
a link on the HiFive Premier P550. A training failure alone does not
identify a power fault.

Check the card's seating and auxiliary power connections. Use a power
supply rated for the board and all attached devices. If training still
fails, try a known working power supply and card.

For electrical diagnosis, measure the slot's 12 V and 3.3 V rails during
startup. Check that PERST# changes from low to high. Compare results with
the same firmware and peripheral configuration.
