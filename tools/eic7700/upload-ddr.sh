#!/bin/sh
# SPDX-License-Identifier: MIT
set -eu
if [ "$#" -ne 1 ]; then
    printf 'Usage: %s SOC_UART_DEVICE\nClose the channel C terminal first.\n' "$0" >&2
    exit 2
fi
device=$1
package_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
image=$package_dir/recovery-ddr.ihex
for tool in stty ascii-xfr; do
    command -v "$tool" >/dev/null 2>&1 || {
        printf 'Missing %s. On Debian 13, install minicom.\n' "$tool" >&2
        exit 1
    }
done
test -c "$device" || { printf 'Not a serial device: %s\n' "$device" >&2; exit 1; }
test -r "$image" || { printf 'Missing %s. Use a complete package.\n' "$image" >&2; exit 1; }
if command -v fuser >/dev/null 2>&1 && fuser -s "$device"; then
    printf '%s is in use. Close the channel C terminal before uploading.\n' "$device" >&2
    exit 1
fi
saved=$(stty -F "$device" -g)
trap 'stty -F "$device" "$saved"' EXIT
trap 'exit 1' HUP INT TERM
printf 'Sending DDR recovery to %s. Keep board power connected.\n' "$device" >&2
stty -F "$device" 115200 raw -echo ixon -ixoff -crtscts
ascii-xfr -dsv "$image" <"$device" >"$device"
printf '\nUpload finished. Reopen channel C, then run the JTAG loader.\n' >&2
