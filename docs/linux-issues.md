# Linux PCIe framebuffer conflict

This issue is present in Linux 7.3.3 and 7.4-rc1. It affects K3 and
HiFive Unmatched when `sysfb` reserves a firmware framebuffer inside a
PCIe host bridge window.
The host bridge can then fail to initialize with error -12 and a message such as:

```text
resource collision: ... conflicts with BOOTFB ...
```

Devices behind the affected PCIe bridge are then unavailable to Linux.

See the [proposed sysfb fix][sysfb-fix].

## Workaround

Add this parameter to the Linux command line:

```text
initcall_blacklist=sysfb_init
```

In GRUB, press `e`, append the parameter to the `linux` line, then press
`Ctrl-x` to boot. This change applies only to that boot. To keep it, add the
parameter through the distribution's boot-loader configuration.

The parameter prevents Linux from registering the firmware framebuffer.
UEFI graphics remain available before Linux starts. Linux graphics require
a native graphics driver.

[sysfb-fix]: https://lore.kernel.org/all/20261107-sysfb-dt-pci-efifb-v1-1-86d6c598671a@iscas.ac.cn/
