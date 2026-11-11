# SPDX-License-Identifier: MIT
SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c
.ONESHELL:
.NOTPARALLEL:
.DEFAULT_GOAL := all

ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
SOURCES := $(ROOT)/src
BOARD ?= k3
TARGET ?= RELEASE
BUILD ?= $(ROOT)/build/$(BOARD)/$(TARGET)
BUILD := $(abspath $(BUILD))
DIST ?= $(ROOT)/dist/$(BOARD)/$(TARGET)
JOBS ?= 2
PYTHON ?= python3
CROSS_COMPILE ?= riscv64-linux-gnu-
RISCV_ISA := rv64gc
SETTINGS_TOOL := tools/settings.py
EMULATION_ENABLE ?= TRUE
ifneq ($(EMULATION_ENABLE),TRUE)
ifneq ($(EMULATION_ENABLE),FALSE)
$(error EMULATION_ENABLE must be TRUE or FALSE)
endif
endif

ifeq ($(TARGET),DEBUG)
COREBOOT_LOGLEVEL := 7
SBI_FW_OPTIONS := 0
DEBUG_PRINT_ERROR_LEVEL ?= 0x80000047
else ifeq ($(TARGET),RELEASE)
COREBOOT_LOGLEVEL := 4
# SBI_SCRATCH_NO_BOOT_PRINTS; keep the generic platform configuration.
SBI_FW_OPTIONS := 1
DEBUG_PRINT_ERROR_LEVEL ?= 0x80000002
else
$(error TARGET must be DEBUG or RELEASE)
endif

EDK_WORK = $(BUILD)/edk2
MAU_BUILD = $(BUILD)/multiarch/Build/MultiArchUefiPkg/$(TARGET)_GCC/RISCV64
MAU_EFI = $(MAU_BUILD)/EmulatorDxe.efi
MAU_DEPEX = $(MAU_BUILD)/MultiArchUefiPkg/Drivers/Emulator/Emulator/OUTPUT/EmulatorDxe.depex
export CCACHE_DIR = $(BUILD)/ccache

BOARDS := $(basename $(notdir $(wildcard $(ROOT)/platforms/*.mk)))
ifeq ($(filter $(BOARD),$(BOARDS)),)
$(error Unsupported BOARD=$(BOARD))
endif
include $(ROOT)/platforms/$(BOARD).mk

include $(ROOT)/rules.mk
