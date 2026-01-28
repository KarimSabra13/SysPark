Language: English | [Français](../../fr/edge/mqtt-bridge.md)

# MQTT Bridge (Local ↔ Cloud Relay)

SysPark uses a hybrid MQTT architecture: a **local broker** on the parking LAN for low-latency and offline-capable operation, plus a **public broker** used as a relay to the Cloud backend. The MQTT bridge is the controlled link between these two worlds.

The bridge is a security-critical component. It must behave like an application firewall:
- forward only what is required,
- prevent loops,
- reduce exposure,
- keep the local system safe even if the public side is noisy or compromised.

---

## 1) Why the bridge exists

### Goals
- Keep the parking usable without internet (local broker is enough).
- Enable cloud supervision and payment only when connectivity is available.
- Avoid exposing the local broker to the public internet.
- Control exactly which topics can cross the boundary.

### What the bridge is not
- It is not a general-purpose “sync everything” tool.
- It must not allow arbitrary topic forwarding.

---

## 2) Topology and roles

### Local side
- Broker running inside the parking LAN.
- Producers: STM32 nodes, FPGA executor telemetry, local sensors.
- Consumers: Edge applications (display, vision), local tools.

### Public side
- Broker reachable from the internet (TLS).
- Cloud backend subscribes/publishes there.
- Potentially multiple sites can publish to the same broker (multi-tenant model).

### Bridge
- A single service running on the Edge gateway.
- Connects as a client to both brokers.
- Subscribes to allowlisted topics on one side and republishes to the other side.

---

## 3) Direction policy (allowlists)

The bridge must define two explicit allowlists:

### A) Local → Cloud
Forward only telemetry and state needed by the cloud:
- presence and safety events,
- actuator state snapshots,
- ACL list/state,
- sync requests,
- selected diagnostics (heartbeats).

Never forward:
- internal debug spam,
- raw video streams,
- high-rate noise topics unless explicitly required.

### B) Cloud → Local
Forward only the minimal control-plane topics:
- user display messages (optional, if cloud drives them),
- payment success and payment request context,
- controlled configuration updates (ACL changes),
- explicit actuator commands (if cloud is allowed to command lanes).

Never forward:
- arbitrary wildcard commands,
- topics that could overwrite local safe-state logic.

---

## 4) Loop prevention

Loop prevention is mandatory because:
- both sides may publish the same topic names,
- bridging can create infinite republish cycles.

Recommended strategies:
- Use allowlists with exact topic matches only (no broad wildcards).
- Tag republished messages with a `src` field and drop messages already coming from the bridge.
- If the bridge uses symmetric topic names, enforce “one-way ownership”:
  - some topics are owned by local side (only forwarded up),
  - some topics are owned by cloud side (only forwarded down).

---

## 5) QoS and retain rules in a bridged system

### QoS
- Keep QoS consistent with the topic contract.
- For critical commands and safety events, QoS 1 or QoS 2 may be used, but:
  - duplicates must be handled idempotently,
  - messages should carry session IDs or correlation IDs.

### Retain
- Avoid retaining commands on the public broker.
- Prefer retaining last-known states on the local side.
- If states are retained on the public broker, ensure they cannot trigger actions by themselves.

---

## 6) Authentication and encryption

Minimum requirements:
- Public broker connectivity must use TLS.
- Bridge credentials must be unique per site.
- Bridge should not accept unauthenticated public inbound connections.
- Secrets and credentials must be stored in environment variables (not in Git).

Recommended for production:
- separate username/password per site and per direction,
- topic-level ACLs on the broker (publish/subscribe permissions),
- broker-side rate limiting.

---

## 7) Failure behavior (what happens when connectivity breaks)

### Public broker unreachable
- Bridge enters retry mode with backoff.
- Local broker continues → parking keeps running in LAN mode.
- Cloud features degrade (payments/remote dashboard updates).

### Local broker unreachable
- Bridge cannot operate; system should enter a restricted mode.
- Recommendation: supervise the local broker as a critical service with auto-restart.

### Cloud backend unreachable
- Public broker may still be reachable, but no “decisions” will arrive.
- Site continues with offline policy if supported.

---

## 8) Operational checklist

Before enabling the bridge in a deployment:
- Confirm local broker is bound to LAN only (not public).
- Confirm TLS to public broker works.
- Confirm allowlists are minimal and reviewed.
- Confirm loop prevention strategy works (no republish storms).
- Confirm safety defaults: if the bridge dies, actuators do not misbehave.

---

## 9) Where the bridge fits in SysPark docs

- Architecture: `docs/en/overview/architecture.md`
- MQTT contract: `docs/en/cloud/mqtt-topics.md`
- Edge overview: `docs/en/edge/beagley-ai.md`

