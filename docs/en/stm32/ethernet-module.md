Language: English | [Français](../../fr/stm32/ethernet-module.md)

# Ethernet Networking (STM32 Node)

SysPark uses Ethernet to connect the STM32 field nodes to the parking LAN. Ethernet is chosen for robustness, predictable latency compared to Wi-Fi, and easier multi-device integration during demos (gateway + FPGA + multiple STM32s).

This document describes the STM32 Ethernet networking model: addressing, topology, MQTT connectivity expectations, and a practical test method.

---

## 1) Why Ethernet in SysPark

- Stable physical link in a noisy environment (motors, power converters).
- Predictable integration: fixed IPs, no Wi-Fi roaming issues.
- Easy to segment the demo LAN from external networks.
- Supports MQTT reliably with clear failure signals (link up/down).

---

## 2) LAN topology (typical SysPark demo)

A common SysPark LAN includes:
- Edge gateway (BeagleY-AI)
- FPGA execution node
- STM32 entry node
- STM32 exit node
- Optional: local operator laptop

All devices are connected through:
- a small Ethernet switch, or
- a router configured as a simple LAN bridge.

Design preference:
- keep the parking LAN private and independent from the public internet.
- add internet access only through the edge gateway/bridge path.

---

## 3) IP addressing strategy (static IPv4 recommended)

Static IPv4 is recommended for repeatable demos:
- easy to document,
- avoids DHCP surprises,
- makes troubleshooting simpler.

Recommended approach:
- choose one private subnet (e.g., `192.168.X.0/24`),
- assign fixed addresses per role:
  - gateway: `.10`
  - FPGA: `.20`
  - STM32 entry: `.30`
  - STM32 exit: `.31`

Important rule:
- do not mix lab DHCP networks with the parking LAN during testing.
- isolate to avoid conflicts.

---

## 4) MQTT connectivity model over Ethernet

The STM32 acts as an MQTT client over TCP/IP.

### Basic behavior
- connect to the broker using a known IP/hostname,
- subscribe to role-specific topics (commands/authorizations),
- publish telemetry and events (RFID UID, elevator state, heartbeats).

### Expected properties
- reconnect logic with backoff if broker is down,
- “last will” or heartbeat strategy to show node liveness,
- bounded queues to avoid memory pressure during reconnect storms.

---

## 5) Bring-up checklist (field-friendly)

When Ethernet “doesn’t work”, check in this order:

1. **Physical**
   - cable seated, switch powered,
   - link LEDs on the board and on the switch.

2. **Addressing**
   - correct static IP, mask, gateway (if used),
   - no conflict with another node.

3. **Broker reachability**
   - broker running on gateway and bound to LAN,
   - topics visible from a known working MQTT client (on a laptop in the same LAN).

4. **STM32 side**
   - node publishes heartbeat after boot,
   - subscriptions are active (commands are received when tested).

5. **Traffic sanity**
   - no publish loops,
   - no flood due to reconnect misconfiguration.

---

## 6) Test methodology (recommended SysPark practice)

### A) Connectivity sanity test
- Use a laptop on the same LAN.
- Confirm broker is reachable.
- Subscribe to STM32 topics and look for heartbeats.

### B) TCP reception validation
- Verify the STM32 can receive and parse a message reliably.
- Ensure messages do not block time-sensitive threads.

### C) MQTT end-to-end test
- Publish a known test command on a subscribed topic.
- Verify:
  - STM32 receives it,
  - state machine reacts,
  - an acknowledgement is published.

### D) Long-run stability test
- Keep the system running for hours.
- Verify no memory growth, no deadlocks, stable heartbeats.

---

## 7) Common failure cases

### Link up but no traffic
- wrong IP/mask,
- broker not reachable (wrong address),
- switch VLAN/port isolation (rare in simple switches).

### Works initially then dies
- memory pressure due to unbounded queues,
- SD operations blocking network thread,
- reconnection storms causing thread starvation.

### Random disconnects
- power noise on LAN equipment,
- loose cables,
- unshielded wiring near stepper drivers.

---

## 8) Integration with the rest of SysPark

Ethernet on STM32 is not isolated:
- it must coexist with motor control and UI threads,
- MQTT traffic must not affect motion timing,
- the node must remain safe if network disappears.

Correct behavior:
- network loss does not produce unsafe actuation,
- node enters a clear degraded state,
- UI indicates loss of connectivity to help operators.

