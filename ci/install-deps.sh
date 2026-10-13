#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Run as root on Ubuntu 26.04.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends \
    ca-certificates git build-essential gcc-riscv64-linux-gnu \
    binutils-riscv64-linux-gnu bc bison flex pkg-config \
    libssl-dev libelf-dev libfdt-dev zlib1g-dev uuid-dev \
    device-tree-compiler acpica-tools nasm xz-utils \
    python3 python3-yaml python3-pyelftools python3-packaging \
    python3-jsonschema python3-pykwalify
