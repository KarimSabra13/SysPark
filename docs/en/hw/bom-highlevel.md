Language: English | [Français](../../fr/hw/bom-highlevel.md)

# Hardware BOM (High-Level)

This document summarizes the SysPark hardware at block level. It is a field-oriented view meant for integration, wiring, and deployment planning. It does not replace detailed part datasheets.

SysPark is built around a clear separation:
- Edge gateway for orchestration and cloud bridge
- FPGA execution node for deterministic actuator control
- STM32 field nodes for real-time I/O close to equipment
- Optional vision node for plate recognition
- Power subsystem sized for motors and embedded compute

---

## 1) Core compute and control

### Edge gateway
- BeagleBone AI / BeagleY-AI class edge gateway
- Roles
  - MQTT broker (local bus)
  - Bridge to cloud services
  - Orchestration state machine
  - Remote maintenance entry point
  - Optional vision inference host

### FPGA execution node
- Digilent Nexys A7-100T FPGA board
- Roles
  - LiteX RISC-V soft SoC
  - Linux runtime for services
  - CSR-mapped I/O for actuator control
  - Deterministic control surface for barriers

### STM32 field nodes
- STM32F746G-DISCO boards
- Typical roles
  - Entry node: elevator or lane mechanism control, UI, RFID
  - Exit node: payment gating UI, RFID, network telemetry
- RTOS
  - Zephyr RTOS for deterministic multi-threading and Ethernet networking

---

## 2) Actuation hardware

### Barriers
- Barrier mechanisms for entry and exit lanes
- Drive chain in the demo setup
  - FPGA PMOD outputs
  - Driver stage (ULN2003 class)
  - Stepper motors (28BYJ-48 class) or equivalent small barrier actuator

### Elevator or lift mechanism (if used)
- Motorized lift for the demo platform
- Controlled by STM32 in real time
- Requires
  - motor driver matched to motor type
  - homing sensor or limit switch
  - mechanical end stops

---

## 3) Identification and user interfaces

### Identification
- RFID badge reader on STM32 nodes
- Optional vision-based plate recognition
  - camera per lane or shared camera depending on layout

### Local user feedback
- LCD 20x4 on STM32 for operator and lane prompts
- OLED display for lift or detailed status views
- LED banner display for driver-facing messages

---

## 4) Networking and interconnect

### Ethernet (preferred in SysPark)
- Edge gateway, FPGA node, STM32 nodes connected on a private LAN
- Switch or simple router in bridge mode

### Physical I/O wiring
- PMOD harness from FPGA to driver boards and sensors
- Sensor wiring to STM32 GPIO as needed

---

## 5) Power subsystem (high-level)

SysPark uses a centralized DC power architecture:
- Main battery rail (12 V class in the demo)
- DC-DC conversion to 5 V for compute and peripherals
- Additional local regulation to 3.3 V where required

Key blocks
- Battery pack
- BMS protection and balancing
- Primary fuse and wiring protection
- DC-DC 12 V to 5 V high current module
- Optional secondary DC-DC rails for specific actuators

---

## 6) Recommended spare parts for demos

Field demos fail on simple parts. Keep spares:
- Ethernet cables, small switch
- PMOD jumper wires and headers
- Motor drivers and spare motors
- RFID reader spare unit
- Fuses, connectors, cable ties
- SD cards for the FPGA Linux node

---

## 7) References

- Presentation PDF: references/pdf/SysPark_Présentation.pdf
- Power and BMS reference: references/pdf/BMS.pdf

