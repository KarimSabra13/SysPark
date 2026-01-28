Language: English | [Français](../../fr/edge/beagley-ai.md)

# Edge Gateway (BeagleY-AI) Overview

The Edge Gateway is the on-site “brain connector” of SysPark. It sits inside the parking LAN and bridges the physical subsystems (STM32 field nodes and FPGA execution node) with cloud services. Its role is to orchestrate flows, fuse data sources (sensors + vision + policies), and keep the site usable even when the internet is unstable.

The Edge Gateway follows three rules:
- **Local-first operations**: the parking must keep working in LAN mode.
- **Cloud-enhanced**: cloud adds dashboards, payments, long-term traceability, and remote supervision.
- **Safety never depends on the cloud**: time-critical actuation and safe states stay on the execution side.

---

## 1) Responsibilities

### 1.1 Control-plane hub
- Receives field events: presence, RFID identification, actuator states, alarms.
- Publishes decisions and operator-facing messages: guidance text, lane states.
- Maintains a stable messaging boundary between local subsystems and the cloud.

### 1.2 Data fusion and decision support
- Combines:
  - “who” (RFID / PIN / plate),
  - “where” (entry or exit lane),
  - “what is happening” (sensor presence, barrier state),
  - “what is allowed” (policy and ACL, online or cached),
  to drive the correct flow (entry, exit, manual override).

### 1.3 Supervision and maintenance
- Provides secure remote access for debugging and supervision without opening inbound ports on the site router.
- Supports live status visibility: health, heartbeats, lane readiness.

### 1.4 AI / Vision integration (optional but key feature)
- Runs the on-site vision pipeline used for license plate recognition and contextual decision support.
- Publishes recognized plate and confidence to the system bus (MQTT) for cloud/session linkage.

---

## 2) Local MQTT broker and hybrid architecture

SysPark uses MQTT as the internal system bus.
The Edge Gateway hosts (or supervises) the **local broker** to keep the parking operational even if the internet is down.

### Local broker role
- Low-latency event distribution inside the parking LAN.
- Decouples producers (STM32, FPGA, sensors) from consumers (gateway, display, bridge).
- Allows “island mode” operations.

### Bridge role (local ↔ public broker)
A selective bridge forwards only whitelisted topics between:
- the local broker (site LAN),
- the public broker (used by the cloud backend).

Design intent:
- avoid topic loops,
- expose only what is necessary,
- keep local debug traffic private.

---

## 3) Interfaces to subsystems

### 3.1 STM32 field nodes (entry and exit)
The Edge Gateway interacts with STM32 nodes through MQTT topics to:
- receive identification events (RFID, PIN status),
- receive elevator or actuator state (entry side),
- receive exit authorization readiness (exit side),
- send commands or configuration updates only when required and authorized.

STM32 nodes remain responsible for deterministic field interaction (RTOS tasks, local I/O).

### 3.2 FPGA execution node (deterministic actuation)
The Edge Gateway exchanges command requests and state telemetry with the FPGA execution node.
The FPGA node:
- executes barrier/actuator sequences deterministically,
- enforces safe states with timeouts/watchdogs,
- returns status continuously.

The Edge Gateway:
- requests actions (open/close/position),
- updates lane messages and logs based on executor outcomes.

### 3.3 Cloud backend
The Edge Gateway connects the site to the cloud through the public broker:
- uploads telemetry and events,
- receives high-level decisions (payment success, operator commands, config updates),
- keeps “cloud-enhanced” features available when internet is present.

---

## 4) Driver-facing local display

A local display provides immediate user feedback in the lane:
- “Welcome”
- “Identify”
- “Proceed”
- “Payment required”
- “Wait”
- “Fault, call operator”

Design intent:
- feedback must work locally (LAN mode),
- updates are driven by MQTT messages so any decision source (edge or cloud) can control it.

---

## 5) Vision and camera functions (optional module)

### 5.1 Vision pipeline (LPR)
The gateway can run a license plate recognition pipeline:
- capture frames,
- detect plate region,
- OCR,
- normalize and validate result format,
- publish result with confidence.

Usage:
- entry: optional second factor or pre-identification
- exit: session linkage and fee computation support

Failure behavior:
- low confidence must not block the lane,
- fall back to RFID/PIN/operator flows.

### 5.2 Camera positioning (pan/tilt)
If a motorized camera is present, the gateway can relay positioning commands:
- operator-driven adjustments during maintenance,
- predefined viewpoints per lane.

---

## 6) Secure remote supervision (no open ports)

SysPark’s design avoids exposing the parking LAN directly to the internet.
Remote supervision is done through a secure tunnel approach (VPN overlay / controlled exposure).

Goals:
- no router configuration needed on site,
- access can be enabled/disabled explicitly,
- maintenance can view debug streams safely.

---

## 7) Reliability and operational behavior

The gateway is expected to run as a set of supervised services:
- local broker availability,
- bridge availability,
- display service availability,
- vision service (if enabled),
- monitoring/heartbeat reporting.

Operational expectations:
- auto-restart on crash,
- clear logs,
- predictable startup order (network → broker → bridge → applications).

---

## 8) Security baseline

Minimum baseline for a realistic deployment:
- local broker not accessible from the public internet,
- TLS used for cloud-side broker connectivity,
- strict allowlists in the bridge,
- sensitive remote updates require authentication rules (shared secret, admin controls),
- operator override actions are traceable.

---

## 9) Failure modes (edge perspective)

### Internet down
- local broker continues,
- local flows continue with cached rules,
- cloud supervision and payments may degrade.

### Public broker down
- site continues locally,
- cloud cannot receive updates until broker recovers.

### Vision down
- no blocking; fall back to RFID/PIN.

### Local broker down
- system should enter a controlled restricted mode until broker returns (or switch to a defined fallback if implemented).

