Language: English | [Français](../../fr/fpga/riscv-overview.md)

# RISC-V on FPGA Overview (LiteX + Soft SoC)

SysPark uses a RISC-V system running on an FPGA to implement a deterministic “execution node” that can safely drive actuators (barriers, motors) while still supporting a Linux environment for integration, tooling, and network services.

The idea is to combine:
- **hardware determinism** for control and I/O,
- **software flexibility** for messaging, logging, and system integration.

---

## 1) Why run RISC-V on an FPGA in SysPark

### Deterministic and low-level I/O
Actuation (barrier open/close, motor sequences) benefits from:
- predictable timing,
- direct memory-mapped register access,
- the ability to implement safety timeouts close to the hardware.

### Fast iteration for custom hardware interfaces
On an FPGA, SysPark can add or modify:
- PWM/stepper controllers,
- CSR-mapped GPIO blocks,
- additional sensors/encoders,
- watchdog and safety state machines,
without relying on a fixed off-the-shelf controller.

### Linux integration without losing control
Running Linux on the soft SoC enables:
- MQTT client services,
- secure payload handling,
- remote logging and maintenance,
- fast prototyping of on-device logic.

The FPGA remains the place where the “last mile” execution is controlled and made safe.

---

## 2) LiteX in one sentence

LiteX is used to generate a customizable SoC on the FPGA:
- a RISC-V CPU core,
- bus interconnect,
- memory controllers,
- and **CSR registers** that expose custom hardware blocks to software.

In SysPark, LiteX is the bridge between custom control logic in HDL and software services running on the CPU.

---

## 3) Soft SoC building blocks (SysPark view)

A typical SysPark FPGA SoC contains:

### CPU subsystem
- RISC-V soft core (e.g., VexRiscv class)
- on-chip ROM/BIOS stage (LiteX BIOS)
- DRAM controller (when using external DDR)

### Peripheral subsystem
- CSR-mapped GPIO blocks (for PMOD inputs/outputs)
- custom control IP (stepper driver output sequencing, PWM, etc.)
- UART for console
- Ethernet or MAC support if used for networking
- timers and interrupts used by Linux and by low-level services

### Memory and storage
- boot medium (SD or SPI flash depending on setup)
- runtime memory (DDR)

---

## 4) What CSR means in SysPark

CSR stands for Control and Status Registers:
- memory-mapped registers created by LiteX,
- accessible by software through simple reads/writes,
- used to control custom hardware blocks (set outputs, read inputs, trigger actions).

In SysPark, CSR registers provide the “actuator interface”:
- barrier control outputs are written through CSR-mapped GPIO,
- sensor inputs are read through CSR-mapped GPIO,
- Linux services translate MQTT commands into CSR writes.

This architecture avoids complex driver stacks and keeps the control path simple and transparent.

---

## 5) Separation of concerns (why this architecture is clean)

SysPark intentionally separates:
- **Decision layer** (cloud policies, edge orchestration)
- **Execution layer** (FPGA + CSR control)
- **Field interaction layer** (STM32 nodes close to sensors/motors)

The FPGA node is focused on:
- deterministic execution,
- safety boundaries,
- reliable low-level I/O,
not on high-level business logic.

---

## 6) Typical responsibilities of the FPGA execution node

- Subscribe to the local MQTT bus (or receive commands via the edge gateway).
- Validate and translate commands into hardware actions.
- Drive barrier outputs (stepper or motor driver chain).
- Read sensor inputs and publish states.
- Enforce timeouts and safe states in case of faults or missing heartbeats.
- Provide a clear software interface to the rest of the system.

---

## 7) Why open RISC-V is a good match (project philosophy)

RISC-V fits SysPark’s approach because:
- open ISA, easy to explain and document,
- strong ecosystem for soft cores and FPGA SoCs,
- aligns with an engineering demo where transparency matters,
- simplifies educational and research-driven iteration.

In practice, the value is the ability to generate the exact SoC needed and expose precise hardware control surfaces.

---

## 8) Acceptance criteria for the FPGA node

A correct FPGA execution node integration provides:
- stable boot chain to Linux,
- predictable CSR access (no address mismatch),
- reliable actuator control under MQTT command load,
- correct sensor sampling and state publishing,
- safe recovery on faults and timeouts.

