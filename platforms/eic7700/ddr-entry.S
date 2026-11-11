/* SPDX-License-Identifier: Apache-2.0 */
.section .entry, "ax"
.option push
.option norvc
.option norelax
.global _start
_start:
	j ddr_dispatch
.option pop
