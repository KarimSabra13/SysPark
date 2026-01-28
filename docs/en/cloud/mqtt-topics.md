Language: English | [Français](../../fr/cloud/mqtt-topics.md)

# MQTT Topics and Data Contract

This document defines the MQTT interface of SysPark. It is the contract that keeps the system modular and interoperable across Edge, STM32, FPGA execution, and Cloud services.

The design principle is simple:
- Topics are stable APIs.
- Payloads are predictable and versionable.
- QoS and retain rules are explicit.
- The bridge acts as an application firewall between the site LAN and the public broker.

---

## 1) Namespace and naming rules

### Root
All SysPark topics are under a single root:
- `parking/`

This isolates SysPark from other applications sharing the same broker.

### Naming style
- Use lowercase.
- Use nouns for state streams, verbs or `cmd` for commands.
- Keep topic paths short but explicit.

Examples:
- `parking/sensor_gate/present` is a state stream.
- `parking/barriere/cmd` is a command channel.

---

## 2) Payload conventions

SysPark uses two payload styles:

### A) Simple payload (string or number)
Use for very small and frequent messages, or when parsing must stay minimal.
- Examples: `0`, `1`, `"110"`, `"LIBRE: 12"`

### B) JSON payload
Use when the message needs timestamps, metadata, or multiple fields.

Recommended shared fields:
- `ts`: Unix timestamp in milliseconds (or seconds if the system is constrained, but be consistent).
- `src`: publisher identifier (`edge`, `stm32_entry`, `stm32_exit`, `fpga`, `cloud`).
- `state`: boolean or string state.
- `code`: error code for alarms.

Security field used by access-control updates:
- `secret`: shared application secret used to reject unauthorized ACL changes.

---

## 3) QoS and retain policy

### QoS (delivery guarantee)
- QoS 0: telemetry where occasional loss is acceptable.
- QoS 1: control or events that must arrive at least once.
- QoS 2: critical alerts or configuration changes where duplicates must be avoided.

### Retain (last known value)
Use retain for “state” topics so new subscribers get an immediate snapshot.
Do not retain “commands” unless you explicitly want a command to re-apply after reconnect.

Recommended retain usage:
- Retain: presence state, actuator states, ACL list, weather snapshot.
- No retain: barrier commands, display text commands, camera real-time commands.

---

## 4) Bridge direction rules

SysPark typically runs a local broker on site and bridges selected topics to a public broker used as a relay to the Cloud.

The bridge must implement two explicit allowlists:
- Cloud to Local: only the minimum set of command topics.
- Local to Cloud: only relevant telemetry and state topics.

Everything else is dropped.

This prevents:
- infinite message loops,
- unintended exposure of internal debug traffic,
- malicious topic injection from the public side.

---

## 5) Topic map

### 5.1 Safety and presence sensing

| Topic | Direction | QoS | Retain | Payload | Meaning |
|---|---|---:|:---:|---|---|
| `parking/sensor_gate/present` | Local → Cloud | 1 | Yes | JSON or `0/1` | Vehicle presence near barrier. Retain ensures dashboards get the last known state. |
| `parking/sensor_gate/heartbeat` | Local → Cloud | 0 | No | JSON | Periodic health status for monitoring. |
| `parking/sensor_gate/error` | Local → Cloud | 2 | No | JSON | Critical sensor failure or safety alarm. |

### 5.2 User-facing messaging

| Topic | Direction | QoS | Retain | Payload | Meaning |
|---|---|---:|:---:|---|---|
| `parking/display/text` | Cloud → Local | 1 | No | string | Message to show to drivers on the local display. |

### 5.3 Barrier control

| Topic | Direction | QoS | Retain | Payload | Meaning |
|---|---|---:|:---:|---|---|
| `parking/barriere/cmd` | Cloud → Local | 1 | No | string | Barrier actuation command. Example payloads can be compact encoded commands. |
| `parking/barriere` | Local → Cloud | 1 | No | JSON | Entry identification event used by the entry flow. Typical content is RFID UID or equivalent. |

Notes:
- Keep commands and events separate.
- Do not retain `parking/barriere/cmd`.

### 5.4 Camera positioning

| Topic | Direction | QoS | Retain | Payload | Meaning |
|---|---|---:|:---:|---|---|
| `parking/camera/cmd` | Cloud → Local | 0 | No | JSON | Real-time pan/tilt control. QoS 0 is usually enough due to high update rate. |

### 5.5 Elevator control (entry side)

| Topic | Direction | QoS | Retain | Payload | Meaning |
|---|---|---:|:---:|---|---|
| `parking/ascenseur/cmd` | Cloud → Local | 1 | No | JSON | Request a target floor or action. |
| `parking/ascenseur/get` | Cloud → Local | 0 | No | JSON | Ask for a fresh state publish. |
| `parking/ascenseur/state` | Local → Cloud | 0 or 1 | Yes | JSON | Elevator state snapshot. Retain recommended. |

### 5.6 Payment flow (exit side)

| Topic | Direction | QoS | Retain | Payload | Meaning |
|---|---|---:|:---:|---|---|
| `parking/payment/req` | Cloud → Local | 1 | No | JSON | Cloud requests payment action or displays fee context. |
| `parking/payment/success` | Cloud → Local | 1 | No | JSON | Payment validated. Unblocks exit sequence. |

### 5.7 Access control list (ACL) management

| Topic | Direction | QoS | Retain | Payload | Meaning |
|---|---|---:|:---:|---|---|
| `parking/acl/add` | Cloud → Local | 2 | No | JSON | Add a badge/user entry. Must include `secret`. |
| `parking/acl/del` | Cloud → Local | 2 | No | JSON | Remove a badge/user entry. Must include `secret`. |
| `parking/acl/full` | Cloud → Local | 2 | No | JSON | Replace full ACL set. Must include `secret`. |
| `parking/acl/enroll` | Cloud → Local | 1 | No | JSON | Trigger local enrollment flow for a new badge. |
| `parking/acl/get` | Cloud → Local | 0 | No | JSON | Request the current ACL list to be published. |
| `parking/acl/list` | Local → Cloud | 0 or 1 | Yes | JSON | Full current ACL list. Retain recommended. |
| `parking/acl/event` | Local → Cloud | 1 | No | JSON | Acknowledgement of SD persistence or application of an update. |

### 5.8 Sync and operational control

| Topic | Direction | QoS | Retain | Payload | Meaning |
|---|---|---:|:---:|---|---|
| `parking/sync/req` | Local → Cloud | 1 | No | JSON | Local node requests policy re-sync after reboot or reconnect. |

### 5.9 Context data (weather)

| Topic | Direction | QoS | Retain | Payload | Meaning |
|---|---|---:|:---:|---|---|
| `parking/meteo` | Local → Cloud | 0 | Yes | JSON | Weather snapshot for display and analytics. Retain recommended. |

---

## 6) Security requirements

Minimum baseline:
- Local broker is not exposed to the public internet.
- Bridge to public broker uses TLS.
- Bridge enforces strict allowlists both directions.
- Sensitive updates use an application-level shared secret in payload.
- For production, require broker authentication and disable anonymous publishing.

Operational controls:
- Use heartbeats for monitoring.
- Alert topics use high QoS.
- Safety defaults should never rely on the cloud.

---

## 7) Compatibility notes and cleanup plan

Some deployments may still contain older topic variants for the same concept. The recommended approach:
- Keep one canonical topic per function.
- If legacy topics exist, treat them as aliases and phase them out with a planned migration window.
- Document every alias explicitly in this file.

