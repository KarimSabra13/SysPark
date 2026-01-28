Language: English | [Français](../../fr/stm32/stm32-overview.md)

# STM32 Subsystem Overview (STM32F746G-DISCO + Zephyr RTOS)

In SysPark, the STM32 subsystem is the **field node** deployed close to the physical lane equipment. It executes deterministic, safety-oriented tasks (motor control, limit switches, RFID, local UI) and synchronizes its state with the Edge gateway (BeagleY-AI) through **Ethernet + MQTT**.

SysPark separates responsibilities on purpose:
- **Edge gateway decides** (orchestrates flows, merges vision + policies, bridges cloud),
- **STM32 executes locally** (timing-sensitive control, reliable I/O handling, local UI),
- **Execution hardware remains safe by design** (watchdogs/timeouts handled where needed).

---

## 1) Role inside SysPark

### Real-time field control
The STM32 node runs the “close-to-hardware” logic:
- stepper motor control through a driver that supports STEP/DIR (and optional configuration interface),
- homing and motion safety using end-stop/limit switch feedback,
- RFID badge reading for local identification,
- local display updates for lane feedback,
- local persistence for critical parameters (PINs, whitelist).

### Network synchronization
The STM32 node publishes events and receives approved commands via MQTT over Ethernet:
- publishes identification and sensor/actuator states,
- subscribes to selected commands and authorizations (notably payment success in exit flow),
- remains usable even when cloud connectivity is degraded (LAN-first behavior).

---

## 2) Why Zephyr RTOS

Zephyr is used for three main reasons:

### Determinism
Field interactions need predictable latency:
- step timing and motor sequencing,
- limit switch handling,
- UI refresh without blocking critical tasks.

### Embedded networking maturity
Zephyr provides a structured networking stack (Ethernet + IPv4 + sockets + MQTT patterns) suitable for microcontrollers with explicit RAM/CPU trade-offs.

### Reproducibility
Zephyr encourages reproducible configuration and portability:
- consistent build/config model,
- hardware description decoupled from application logic,
- easy to align behavior between developer machines and integration setups.

---

## 3) Hardware platform choice: STM32F746G-DISCO

The STM32F746G-DISCO board was selected because it offers:
- a high-performance Cortex-M7 suitable for mixed I/O + networking workloads,
- an integrated ST-LINK for simple flashing/debug,
- convenient expansion headers for motor drivers, RFID readers, displays, and sensors,
- Ethernet connectivity supported by Zephyr (RMII PHY commonly used in this platform).

---

## 4) Interfaces and peripherals (SysPark configuration)

SysPark’s STM32 integration targets a clear set of peripherals:

### Motor and safety I/O
- Stepper motor driver interface (STEP/DIR) and configuration channel if needed
- Limit switch input used for homing and safety boundaries
- Clear “safe state” behavior when faults occur or commands are inconsistent

### Identification (RFID)
- RFID reader used to capture badge UID
- UIDs are normalized and forwarded to the system bus for authorization decisions

### Local user interfaces
- A character LCD (20×4) can present operational data (status, messages, contextual info)
- An OLED screen can be used to show elevator/motion status (floor, direction, homing progress)

### Storage (microSD)
A microSD card is used to persist key data across reboots:
- entry PIN and exit PIN (if those modes are enabled),
- whitelist of authorized badge UIDs,
- optional field logs (events and diagnostics) in a structured, low-write-rate pattern.

---

## 5) Networking model (Ethernet, static IP, and MQTT)

### Ethernet basics
- The STM32 is a LAN node and communicates directly with the Edge gateway.
- Static IPv4 addressing is used to keep integration simple and predictable during demos and testing.

### MQTT integration intent
The STM32 acts as an MQTT client:
- publishes local events (RFID, barrier/elevator state, limit switch state),
- consumes selected decisions coming from the orchestration layer.

A strict topic taxonomy must be shared with BeagleY-AI to prevent mismatches and to keep the bridge allowlist minimal.

---

## 6) Execution modes: entry vs exit roles

SysPark can assign the STM32 node a **lane role**:

### Entry role (with elevator/motion control)
- performs homing on startup,
- drives the elevator/motion sequence deterministically,
- publishes elevator state periodically for supervision and UI.

### Exit role (payment-gated exit)
- focuses on identification + UI + exit authorization,
- waits for a “payment validated” authorization event before allowing exit progression,
- keeps local safety rules independent from cloud availability.

---

## 7) Concurrency model (threads and synchronization)

The application is structured as cooperative modules running at different priorities:
- MQTT communications and routing
- RFID acquisition
- UI rendering (LCD and OLED)
- motion control (entry role only)
- payment UI routing (exit role)

Synchronization is implemented using:
- message queues for UID and payment events,
- a semaphore-like mechanism to unblock UI after payment confirmation,
- a lock to protect microSD access between concurrent activities.

The goal is to avoid blocking operations in time-critical paths and to keep networking/UI/logging isolated from motor timing.

---

## 8) Field logging and robustness principles

To remain reliable in a real site:
- logs are written in a controlled manner (buffered + periodic flush),
- critical buffers and file structures are kept stable in memory,
- stack sizing is treated as a first-class constraint (avoid runtime faults),
- network behavior is validated with isolated subnets to avoid lab/router conflicts.

A separate Ethernet test flow exists in SysPark work to validate:
- TCP reception behavior,
- UART display output,
- and safe storage to microSD (file rotation, periodic synchronization).

---

## 9) Optional audio exploration (project extension)

An audio module was explored to support voice prompts around the elevator system:
- first approach: external text-to-speech board controlled by the STM32,
- second approach: investigation of the on-board audio chain (SAI/I2S codec).

This module is considered optional and was primarily used to evaluate feasibility and integration cost under Zephyr constraints.

---

## 10) Integration expectations (what “good” looks like)

A correct STM32 subsystem integration should provide:
- predictable motion control and safe homing,
- reliable RFID UID reporting,
- consistent UI behavior aligned with lane states,
- stable Ethernet connectivity and MQTT publication/subscription,
- robust behavior in degraded modes (cloud unreachable, broker unreachable),
- traceable local persistence (PINs/whitelist) and minimal SD wear.

