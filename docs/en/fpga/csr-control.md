Language: English | [Français](../../fr/fpga/csr-control.md)

# CSR Control and Actuation Interface (FPGA Execution Node)

On the SysPark FPGA node, the software controls hardware actuators through LiteX **CSR registers** (Control and Status Registers). This creates a very simple, transparent control plane:
- decisions arrive via MQTT to Linux services,
- services translate decisions into CSR reads/writes,
- CSR accesses drive FPGA peripherals (PMOD GPIO, stepper control, safety logic),
- hardware state is read back the same way.

This document explains the control surfaces, integration rules, and safety expectations without referencing implementation code.

---

## 1) What CSR provides in SysPark

CSR is a memory-mapped interface that:
- exposes FPGA hardware blocks as software-readable/writable registers,
- guarantees deterministic access latency compared to high-level driver stacks,
- enables clear mapping between “command intent” and “hardware action”.

SysPark uses CSR to:
- toggle outputs driving motor drivers (barrier actuation),
- sample inputs from sensors,
- export status flags to software.

---

## 2) Control surfaces (what is controllable)

The FPGA node typically exposes:

### 2.1 Output control (actuators)
- Barrier open/close commands expressed as output patterns.
- Stepper sequencing outputs (direct or through an external driver chain).
- Optional: PWM outputs for servos or signaling.

### 2.2 Input sampling (sensors)
- Lane presence sensors (IR, ultrasonic, simple switches).
- Barrier end-stop or “fully open/closed” sensors.
- Fault inputs (overcurrent flags from external driver, if available).

### 2.3 System status
- Alive/heartbeat status,
- watchdog flags,
- last command timestamp (optional),
- safety fault state.

---

## 3) PMOD mapping concept

PMOD connectors are used as a simple physical I/O interface:
- one PMOD may be allocated for outputs (driving motor driver inputs),
- another PMOD may be allocated for inputs (reading sensors).

The CSR map includes:
- one register (or register group) that drives PMOD output pins,
- one register (or register group) that reads PMOD input pins.

Because PMOD pinouts are easy to mis-wire, SysPark documentation should always include:
- which PMOD connector is used (e.g., JB/JD/JC),
- direction (input vs output),
- expected bit ordering.

---

## 4) Command model (from MQTT to CSR)

SysPark’s control path is designed to be explicit:

1. A validated command arrives (usually via MQTT).
2. The execution service checks:
   - command type is allowed,
   - lane role matches,
   - rate limits are respected,
   - current state allows actuation.
3. The service performs CSR writes:
   - sets output pins to start motion,
   - optionally sequences steps over time,
   - monitors input pins to stop safely.
4. The service publishes a status update:
   - command accepted/rejected,
   - actuator state (moving, open, closed),
   - fault if any.

The goal is “predictable actuation with traceability.”

---

## 5) Safety rules (must-have)

CSR access is powerful because it directly affects the physical system. SysPark enforces safety rules at the execution layer:

### 5.1 Timeouts
Any motion must have a maximum duration:
- if sensor feedback is missing,
- or no progress is detected,
then stop and enter a safe fault state.

### 5.2 State gating
Do not allow:
- conflicting commands (open and close simultaneously),
- rapid direction toggling,
- movement when the lane is in a fault state.

### 5.3 Idempotency
Repeated “open” should not restart a dangerous sequence if already open.

### 5.4 Safe defaults on loss of control
If the control service or MQTT connectivity is lost:
- outputs must return to safe state,
- watchdog logic can enforce safe stop.

### 5.5 Clear fault reporting
Fault causes must be visible via MQTT and/or local console:
- timeout,
- sensor inconsistency,
- invalid command.

---

## 6) Integration checks (what to verify)

### CSR map correctness
- Software reads/writes to the correct base addresses.
- A mismatch causes “nothing happens” or wrong pins toggling.

### PMOD wiring validation
- A basic pin-toggle test confirms the mapping.
- Input sampling test confirms sensors are read correctly.

### End-to-end actuation
- MQTT command → CSR change → physical motion → sensor feedback → status publish.

### Degraded mode
- if MQTT stops, the system goes safe.
- if a sensor fails, timeout triggers safe stop.

---

## 7) Documentation expectations

A complete SysPark CSR documentation should include:
- a high-level register map table (names and roles, not code),
- pin mapping per PMOD,
- actuator sequences as state diagrams,
- safety constraints (timeouts, fault states),
- acceptance tests.

