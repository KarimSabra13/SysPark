Language: English | [Français](../../fr/fpga/boot-chain.md)

# Boot Chain on the FPGA Node (LiteX BIOS → OpenSBI → Linux)

SysPark’s FPGA execution node runs Linux on a RISC-V soft SoC generated with LiteX. To make this reliable and explainable, the boot chain is kept explicit: each stage has a clear responsibility and loads the next stage.

High-level idea:
- the FPGA bitstream creates the SoC,
- an early boot environment initializes the platform,
- then the Linux kernel boots with its device tree and root filesystem.

---

## 1) Boot chain components (roles)

### 1.1 FPGA bitstream (hardware stage)
- Programs the FPGA with the LiteX SoC design.
- Defines:
  - CPU core,
  - memory map,
  - CSR peripherals,
  - DDR controller and clocking,
  - UART, Ethernet (if enabled), etc.

Without the bitstream, nothing exists for software.

### 1.2 LiteX BIOS (early boot monitor)
LiteX BIOS is the first software stage that runs on the soft CPU. It:
- initializes clocks and memory interfaces,
- provides a serial console for boot commands,
- can load binaries from storage (often SD),
- hands off execution to the next stage.

You can think of it as a minimal firmware/monitor dedicated to LiteX SoCs.

### 1.3 OpenSBI (RISC-V supervisor runtime)
OpenSBI is the firmware layer that provides RISC-V “Supervisor Binary Interface” services required by a Linux kernel running in supervisor mode. It:
- handles low-level platform services,
- provides a standardized environment for Linux on RISC-V.

In this chain:
- LiteX BIOS loads OpenSBI,
- OpenSBI launches the Linux kernel.

### 1.4 Linux kernel (+ Device Tree)
Linux needs:
- the kernel image,
- a device tree blob (DTB) describing the hardware (memory map, peripherals),
- boot arguments (console, rootfs mode, etc.).

The DTB must match the FPGA bitstream design. If not, peripherals and memory mapping will break.

### 1.5 Root filesystem (initramfs)
SysPark commonly boots Linux with an initramfs:
- a compressed root filesystem embedded with the kernel or loaded alongside it,
- contains the minimal userspace services needed (MQTT client, control daemon),
- supports fast deployment without a complex disk partition model.

---

## 2) Typical “who loads what” sequence

A practical sequence used in SysPark:

1. Program FPGA bitstream (SoC appears).
2. Reset / start CPU into LiteX BIOS.
3. LiteX BIOS loads:
   - OpenSBI,
   - Linux kernel,
   - DTB,
   - initramfs (if not built into the kernel).
4. LiteX BIOS jumps to OpenSBI.
5. OpenSBI boots Linux in supervisor mode.
6. Linux starts userspace (initramfs) and runs SysPark services.

---

## 3) SD card role (boot storage)

When SD boot is used, the SD card contains the binaries needed by LiteX BIOS:
- OpenSBI payload (or firmware image),
- Linux kernel image,
- DTB file,
- initramfs archive (if separate).

Key design guideline:
- keep filenames and layout stable,
- document it so recovery is fast after changes.

---

## 4) The critical dependency: DTB ↔ bitstream alignment

The DTB describes:
- UART address,
- CSR base addresses,
- Ethernet MAC presence,
- interrupt mapping,
- memory size and layout.

If you change the FPGA design and rebuild the bitstream:
- you typically must regenerate the DTB accordingly.

Symptoms of mismatch:
- Linux boots but peripherals do not work,
- kernel cannot mount initramfs properly,
- CSR addresses used by control apps are wrong.

SysPark documentation should always tie:
- a given bitstream build to its matching DTB.

---

## 5) Why initramfs is used (SysPark rationale)

Initramfs is used because:
- simplest deployment for a demo platform,
- no need for persistent root partition,
- boot is fast and reproducible,
- easy to include only required tools.

Trade-off:
- updating rootfs means rebuilding/replacing the initramfs image.

---

## 6) Operational checks (quick sanity)

A boot chain is considered healthy if:
- BIOS prompt appears on UART reliably,
- OpenSBI banner appears,
- Linux kernel prints to console,
- initramfs launches expected services,
- CSR control paths work (barrier control).

---

## 7) Failure patterns and how to interpret them

### No BIOS output
- bitstream not loaded,
- wrong UART or baud,
- power/clock issue.

### BIOS output but Linux fails early
- missing kernel/DTB/initramfs on SD,
- wrong filenames,
- corrupted SD.

### Linux boots but peripherals missing
- DTB mismatch with bitstream,
- wrong CSR address map.

### Linux runs but SysPark control fails
- user services not started,
- MQTT connectivity missing,
- CSR apps using wrong addresses.

