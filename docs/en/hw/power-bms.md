Language: English | [Français](../../fr/hw/power-bms.md)

# Power Architecture and BMS

SysPark includes motors and multiple compute nodes. Power must be designed for:
- peak motor current
- stable 5 V rail for edge compute
- safe behavior under wiring faults
- predictable demo operation

This document describes the power architecture and the BMS role at a system level.

---

## 1) Power goals

- Provide a stable 5 V rail for embedded compute and peripherals
- Provide a 12 V class rail for motors and high power loads when needed
- Prevent unsafe conditions
  - over-current
  - over-voltage
  - under-voltage
  - short circuits
- Keep wiring simple for fast demo bring-up

---

## 2) Power rails in SysPark

### Main rail
- Battery rail (12 V class in the demo)

### Distribution rails
- 12 V rail to motor drivers and high power modules
- 5 V rail for edge gateway, FPGA board, STM32 boards, sensors, and displays

### Local point-of-load rails
- 3.3 V rails generated locally on the boards or via small regulators
- Used for RFID modules, sensors, logic I/O when required

---

## 3) Battery and BMS block

### Battery pack
- LiFePO4 class pack used as primary source in the demo
- Sized to cover
  - compute baseline consumption
  - motor peaks
  - expected demo duration

### BMS role
A BMS is required to protect the pack and the system:
- over-current protection
- short-circuit protection
- under-voltage cutoff to protect cells
- balancing to keep cells aligned in SOC
- optional telemetry
  - pack voltage and current
  - per-cell voltages
  - temperature

SysPark selected a BMS solution that matches:
- the pack series count
- the expected peak current of the system
- the wiring simplicity needed for the demo platform

Reference document
- references/pdf/BMS.pdf

---

## 4) DC-DC conversion

### 12 V to 5 V high current module
- A high current DC-DC converter is used to generate the 5 V bus from the battery rail
- Sizing rules
  - sum all 5 V loads
  - apply margin for boot spikes and motor noise
  - keep thermal headroom

Common integration rules
- keep DC-DC close to the distribution point
- use thick conductors for high current segments
- keep ground returns low impedance

---

## 5) Protection and wiring safety

Recommended protection chain
- battery positive
- main fuse near the pack
- BMS
- distribution node
- per-branch fuses where practical

Add protection where needed
- reverse polarity protection
- TVS diode for transients on long cables
- proper strain relief for moving parts

---

## 6) Grounding and noise control

Motors can inject noise. Use simple rules:
- star ground at the main distribution node
- separate motor return paths from sensitive compute returns when possible
- twist motor wires to reduce radiated noise
- keep Ethernet away from stepper driver wiring
- add decoupling near motor drivers and sensitive boards

---

## 7) Power-up and power-down rules

Power-up
- bring up DC-DC first
- confirm stable 5 V rail under load
- then boot compute nodes
- only then enable actuation commands

Power-down
- disable actuation first
- shut down compute nodes if needed
- then remove power

---

## 8) Measurements to record during integration

Record these values on the bench:
- battery voltage at idle and under motor load
- 5 V rail voltage at the far end of harness
- peak current during barrier motion
- DC-DC temperature after long operation
- BMS cutoff threshold behavior in low battery

These measurements improve repeatability and prevent hidden resets.

