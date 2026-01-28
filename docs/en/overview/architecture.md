Language: English | [Français](../../fr/overview/architecture.md)

# SysPark System Architecture

SysPark is a modular smart-parking system designed as a complete, deployable solution rather than a loose set of sensors. The architecture is intentionally distributed and organized into clear responsibility layers, all interconnected over Ethernet. This separation keeps business decisions flexible while ensuring that safety-critical physical actions remain deterministic and robust.

## 1. Architectural principle: split responsibilities, keep interfaces stable

SysPark is built around three complementary execution layers:

- **Decision + supervision layer (Edge Gateway)**  
  A BeagleY-AI-class node is the integration point for high-level logic, cloud connectivity, vision/analytics, remote supervision, and operator-facing services.

- **Real-time execution layer (FPGA SoC)**  
  A Nexys A7 class FPGA running a LiteX SoC provides deterministic actuation and safety enforcement (timeouts, watchdogs, safe states). It executes commands reliably; it does not decide complex business rules.

- **Field interface layer (MCU node)**  
  An STM32F746G-DISCO class microcontroller running an RTOS handles local interactions near the equipment: RFID identification, elevator/actuator sequencing, local displays, and sensor acquisition, with predictable timing and structured multitasking.

A fourth cross-cutting block supports all layers:

- **Power + continuity layer (12 V bus + DC/DC + battery + BMS)**  
  A centralized 12 V DC bus simplifies distribution and supports heterogeneous loads. A backup battery and BMS provide continuity-of-service and energy safety, enabling controlled “safe shutdown” behavior.

This design rule stays constant across the project:

- **Beagle decides (business logic).**
- **FPGA executes (deterministic actuation + safety).**
- **STM32 interfaces with the field (local I/O + RTOS tasks).**

## 2. System-level topology

### 2.1 Networking and interconnection

All modules are connected using Ethernet, which standardizes integration and reduces point-to-point wiring complexity. A typical lab integration uses static IPv4 addressing for predictability (example values used during integration can be adapted per site):

- FPGA node: `192.168.10.4/24`
- Edge gateway: `192.168.10.5/24`
- STM32 node: `192.168.10.7/24`

Ethernet is used for:

- exchanging commands and acknowledgements,
- streaming sensor/actuator status to the gateway,
- transporting MQTT messages between subsystems (local broker and/or bridge).

### 2.2 Power distribution and continuity

SysPark uses:

- **12 V as the main distribution rail** (power domain),
- **5 V as the logic rail** (derived from 12 V via DC/DC conversion),
- a **backup battery** sized for peak power and safe-mode autonomy,
- a **BMS** ensuring protection, monitoring, and cell balancing.

The objective is not to replace mains permanently, but to **keep the system controllable long enough to finish a cycle, unlock safely, and enter a safe state** when supply conditions degrade.

## 3. Communication backbone: MQTT hybrid architecture

SysPark uses MQTT as the “system bus” for events, commands, telemetry, and operator messages.

### 3.1 Why hybrid (local + cloud)

The project uses a hybrid approach to get the best of both worlds:

- **Local MQTT broker** (inside the parking LAN):  
  fast local reactions, works even if internet is unstable, isolates sensitive equipment control.

- **Public broker relay + cloud server**:  
  enables remote supervision, centralized rule management, dashboards, payments and admin tools.

A **selective bridge** synchronizes only the required topics between local and cloud sides. A whitelist-based forwarding policy prevents loops and keeps the exposed surface minimal.

### 3.2 Topic taxonomy (conceptual)

Topics are structured hierarchically under a root (example: `parking/…`) to keep the system extensible. Typical families:

- `parking/sensor_*` for presence, gate sensors, health/heartbeat, errors
- `parking/gate/*` for barrier state, limit switches, commands
- `parking/display/*` for user-facing messages (LED banner, local UI)
- `parking/camera/*` for camera positioning commands and vision outputs
- `parking/config/*` for controlled configuration updates
- `parking/meteo` for contextual data (optional)

Quality-of-service is chosen per criticality:

- QoS 0 for non-critical periodic telemetry,
- QoS 1 for “must arrive at least once” commands,
- QoS 2 for critical configuration or safety events when exactly-once semantics matters.

## 4. Edge Gateway (BeagleY-AI): decision, fusion, supervision

The gateway is the system integration hub:

### 4.1 Decision engine and orchestration

It aggregates:

- field events (RFID, sensors, actuator status),
- vision outputs (plate recognition / confidence / snapshots),
- cloud-side decisions or policies (rules, capacity, operator overrides).

It then orchestrates:

- user guidance (display messages),
- barrier/elevator sequencing requests toward execution nodes,
- notifications and logging.

### 4.2 Local user information and remote supervision

Two key operator-facing functions are emphasized:

- **Local display**: a LED banner driven locally provides immediate feedback (“available spots”, “welcome”, “full”, “please wait”, etc.). The display subscribes to MQTT to update in real time.

- **Remote supervision**: a secure remote access tunnel enables operators/engineers to view a debug video stream without opening inbound ports on the site router. This supports maintenance and reduces deployment friction.

## 5. Field controller (STM32 + RTOS): deterministic terrain interactions

The STM32 subsystem is the “near-machine” node. It concentrates the physical I/O close to the barrier/equipment, and it uses RTOS multitasking to keep behavior predictable and maintainable.

### 5.1 Main responsibilities

- **RFID access control**: read badges and inject identification events into the system flow.
- **Actuator control (elevator, motors, etc.)**: execute local motion profiles with acceleration/deceleration logic, including a boot-time calibration (homing).
- **Local interface**: small displays and immediate user feedback.
- **Sensor acquisition**: temperature/pressure and other safety signals.
- **State synchronization**: publish status and receive commands over the network (via MQTT over Ethernet).

### 5.2 Design intent

The STM32 does not own complex business rules. It provides:

- stable and deterministic field I/O,
- clean separation of tasks (acquisition / display / communication),
- robust behavior under timing constraints.

## 6. FPGA SoC (Nexys A7 + LiteX + RISC-V Linux): deterministic execution and safety

The FPGA block exists to guarantee:

- **deterministic actuation timing**, independent of OS jitter,
- **safety enforcement** via watchdogs/timeouts and safe states,
- **reliable command execution** with explicit control interfaces.

### 6.1 Conceptual structure

- A LiteX SoC provides a clean separation between:
  - hardware logic for strict real-time functions,
  - a lightweight supervisory software layer running on a RISC-V CPU (Linux) for coordination and networking.

- Control is exposed through stable memory-mapped registers (CSR-like control surface), enabling explicit “set/read” semantics for actuators and status signals.

### 6.2 Integration flows

The FPGA exchanges with the gateway via Ethernet:

- **receives commands** to execute (open/close, position, drive),
- **returns status continuously** (states, positions, alarms),
- **enforces safe behavior** on anomaly detection.

## 7. Safety and emergency handling

Safety is designed into SysPark at multiple layers:

- **Local mechanical safety**: presence detection around barriers and controlled motion sequencing reduce risks.
- **Execution safety (FPGA)**: watchdogs/timeouts enforce safe states if commands become inconsistent or stale.
- **Energy safety (BMS)**: cell protection and safe operating area enforcement reduce thermal/chemical risk.
- **Emergency channel independence**: a fire alert mechanism is designed to use an independent radio channel outside the main IP network, ensuring the emergency signal can still reach the system in critical conditions.

## 8. Energy subsystem: BMS, battery sizing, and DC/DC strategy

The energy design is driven by heterogeneous loads and transient peaks:

- The overall system power budget is around the order of a few tens of watts, with peaks driven by motors/servos.
- A 12 V / 6 Ah battery is sized to sustain peak power and provide more than enough time to transition the system into a safe mode.
- The BMS functions include:
  - per-cell voltage monitoring, current and temperature tracking,
  - protection against over/under-voltage and over-current (MOSFET isolation),
  - passive balancing,
  - SOC/SOH estimation for supervision.

A pragmatic path was followed: initial custom BMS exploration for learning and architecture validation, then a commercial integrated BMS for reliability and delivery constraints.

## 9. Modularity and evolution

SysPark is designed to scale:

- from small sites (tens of spots) to larger deployments,
- to multiple entries/exits,
- to higher security requirements (more cameras, stronger policies),
- to additional sensing and diagnostics.

Because responsibilities are separated and interfaces are stable (Ethernet + MQTT + explicit status/command boundaries), new features can be added without destabilizing the safety-critical execution core.
