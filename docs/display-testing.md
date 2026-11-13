# MS2130 capture cards

These two MS2130 cards gave different results. Both report USB ID
`345f:2130`.

| USB name | Result |
| --- | --- |
| UltraSemi USB3 Video | No pass |
| MACROSILICON USB3.0 UHD | Pass |

The MACROSILICON card worked with HiFive Unmatched and an RX550 Baffin
(`1002:67ff`) on 2026-11-13. Capture was kept running during the test.

The result can change with the card's firmware. We did not record the
firmware versions, so another card with the same name or USB ID may behave
differently.
