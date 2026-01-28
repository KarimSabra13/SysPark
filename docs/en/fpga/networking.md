Language: English | [Français](../../fr/fpga/networking.md)

# Networking on the FPGA Linux Node (LAN + MQTT)

The SysPark FPGA node runs Linux on a LiteX RISC-V SoC. Networking is used to integrate the FPGA execution node into the parking LAN so it can:
- receive actuation commands (via MQTT),
- publish sensor and actuator states,
- participate in system supervision.

This document describes the network model, MQTT expectations, and robustness rules for the FPGA node.

---

## 1) Role of networking on the FPGA node

Networking enables the FPGA node to behave like a reliable “execution service” on the LAN:
- subscribe to approved control topics,
- publish barrier state and diagnostics,
- allow operators to monitor health remotely (inside the LAN).

The FPGA node should remain safe even if networking is unavailable.

---

## 2) LAN integration model

### Preferred approach
- The FPGA node is connected to the parking LAN (Ethernet).
- It uses a predictable IP configuration (static or reserved DHCP).
- It talks to the **local MQTT broker** (typically on the edge gateway).

Design goal:
- all time-critical actuation is local (CSR),
- networking provides command/telemetry, not tight real-time loops.

---

## 3) Addressing and isolation

### Addressing
Use one consistent subnet for the parking LAN and document it.
Recommended:
- static IP for FPGA node in demos,
- reserved DHCP in more managed deployments.

### Isolation
- keep the parking LAN private,
- do not expose the FPGA Linux services publicly,
- all cloud connectivity is mediated by the edge gateway and its bridge.

---

## 4) MQTT client responsibilities

The FPGA node MQTT client/service must:

### Subscribe
- barrier command topics (open/close),
- configuration topics if supported (timeouts, policies),
- optional: synchronization topics (global state).

### Publish
- actuator state:
  - open/closed/moving/fault,
- sensor snapshots:
  - limit switches, presence, fault inputs,
- heartbeat:
  - alive status, uptime, last error code.

### Contract rules
- strict topic naming (no ad-hoc topics),
- payload schema consistent with the rest of SysPark,
- idempotent command handling (avoid unsafe repeats).

---

## 5) Service supervision (Linux runtime robustness)

Linux services on the FPGA node should be supervised:
- automatic restart on crash,
- controlled logs (bounded, avoid filling RAM),
- startup ordering:
  - network up → MQTT connect → control service.

If the system uses initramfs:
- ensure services are started by a clear init script or supervisor.

---

## 6) Degraded mode behavior

### Broker unreachable
- retry with backoff,
- publish nothing until connected,
- do not hold outputs active indefinitely waiting for commands.

### Network down
- remain safe:
  - stop motion or return outputs to safe state,
  - keep hardware in a stable state.

### Cloud unreachable
- not a direct concern for FPGA node:
  - it relies on local broker,
  - edge gateway handles bridge/cloud.

---

## 7) Security expectations

Minimum security rules:
- the FPGA node talks only to the local broker (LAN address),
- credentials are not stored in Git,
- limit who can publish barrier commands by broker ACL if possible,
- keep command topics allowlisted at the bridge layer.

For demos, security may be simplified, but the architecture should remain compatible with production rules.

---

## 8) Acceptance checks

Networking integration is correct when:
- FPGA node can reliably connect to the local broker,
- commands arrive and trigger correct actuation,
- state and heartbeat are published consistently,
- failures (broker down, network down) do not create unsafe behavior,
- services recover after reconnect.

