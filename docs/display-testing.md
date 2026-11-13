# Capture-card sample results

These results describe two tested samples, not compatibility guarantees.
Availability depends on the product firmware version. The firmware
versions were not recorded, so the results do not establish support for
other units, including units with the same product name or USB VID/PID.

| USB product string | USB VID/PID | Recorded result |
| --- | --- | --- |
| UltraSemi USB3 Video | `345f:2130` | **no pass**, reported by the operator |
| MACROSILICON USB3.0 UHD | `345f:2130` | **pass**, tested on 2026-11-13 |

The MACROSILICON pass result used HiFive Unmatched, an RX550 Baffin
(`1002:67ff`) and continuous capture. The UltraSemi result is the
operator's record of the other sample. The underlying firmware or
implementation difference has not been verified.
