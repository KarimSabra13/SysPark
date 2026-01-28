Language: English | [Français](../../fr/hw/wiring-topology.md)

# Wiring Topology and Harnessing

SysPark wiring is split into two categories:
- Power wiring for battery, DC-DC, and motors
- Signal wiring for Ethernet and low voltage I/O

This document describes a clean wiring strategy for a reliable demo.

---

## 1) Physical layout principle

Keep blocks physically separated:
- Power block
  - battery, BMS, DC-DC, fuse
- Compute block
  - edge gateway, FPGA, STM32 boards, switch
- Actuation block
  - motor drivers, motors, end stops, moving mechanisms
- Vision block
  - camera and mounting

This separation reduces noise coupling and simplifies debugging.

---

## 2) Ethernet wiring

Preferred topology
- One small Ethernet switch in the platform
- Star connections
  - edge gateway
  - FPGA node
  - STM32 entry
  - STM32 exit
  - optional operator laptop

Rules
- keep cables short and strain relieved
- avoid routing Ethernet next to stepper driver wires
- label each cable by role

---

## 3) FPGA PMOD wiring (actuation and sensors)

PMOD wiring is sensitive to pin order.

Recommended practice
- one PMOD dedicated to outputs for motor driver inputs
- one PMOD dedicated to inputs for sensor reads
- use a consistent wire color convention
  - power
  - ground
  - signal group 0..7

Integration checks
- validate each PMOD line with a simple continuity test
- validate direction
- validate that sensor lines are not floating

---

## 4) Motor driver wiring

Stepper chain example
- FPGA outputs to driver inputs
- driver outputs to motor phases

Rules
- keep motor wires twisted
- keep motor wires away from Ethernet and camera cables
- add strain relief near moving parts
- add mechanical protection against cable rubbing

---

## 5) STM32 field wiring

Typical STM32 wiring per node
- Ethernet
- RFID reader interface
- UI displays
- motor driver interface for lift or mechanism
- limit switch and safety inputs

Rules
- separate power and signal bundles
- avoid long unshielded lines for limit switches
- add pull-ups or pull-downs as required to avoid floating inputs

---

## 6) Camera and vision wiring

Rules
- mount camera with stable angle and vibration control
- keep camera cable separated from motor cables
- avoid sharp bends in camera cable
- protect lens and keep it clean

---

## 7) Power wiring and distribution

Recommended harness structure
- short high current trunk from battery to distribution node
- branch lines to
  - DC-DC module
  - motor drivers
  - compute 5 V distribution

Rules
- fuse near the battery
- use thick wires for high current segments
- use reliable connectors rated for current
- label polarity clearly

---

## 8) Labeling and maintenance tips

Label everything
- each power branch
- each Ethernet cable
- each motor and driver
- each sensor

Keep a small service kit
- spare fuses
- spare Ethernet cable
- spare jumper wires
- small multimeter

---

## 9) Acceptance checklist

- No loose wires near moving mechanisms
- Actuation works without Ethernet interference
- Ethernet remains stable during motor motion
- No unexpected resets when motors start
- BMS does not trip under normal peaks
- All nodes boot and publish heartbeats

