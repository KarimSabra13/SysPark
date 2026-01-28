Language: English | [Français](../../fr/edge/remote-access.md)

# Secure Remote Access and Debug Streaming

SysPark is designed to be maintainable without exposing the parking LAN to the public internet. Remote access is treated as an operational capability, not a permanent open door. The guiding idea is: **no inbound ports**, controlled access, and clear auditability.

This document describes the remote access model used in SysPark and how it supports:
- secure maintenance sessions,
- remote debugging,
- optional live video/debug streaming.

---

## 1) Goals and non-goals

### Goals
- Provide remote access for maintenance without router reconfiguration.
- Avoid exposing the local MQTT broker or device services directly on the internet.
- Enable “on-demand” remote support, including viewing debug streams.
- Keep the solution easy to deploy in a real site (hotel, mall, hospital).

### Non-goals
- Remote access is not intended to replace local safety controls.
- Remote access must not become a dependency for normal operation.
- Remote access should not bypass the bridge allowlist model.

---

## 2) Threat model (what we are protecting against)

- Untrusted internet clients trying to reach the parking LAN.
- Accidental exposure of local services (MQTT broker, SSH, camera streams).
- Credential leakage causing uncontrolled access.
- Unsafe remote operations that could affect the physical system.

---

## 3) Recommended approach: overlay VPN (example: Tailscale)

SysPark uses an overlay VPN approach, which provides:
- device identity via keys,
- encrypted tunnels by default,
- no inbound port forwarding on the site router,
- fine-grained access rules.

The edge gateway is enrolled into the VPN network and becomes the controlled entry point for maintenance.

Key benefits:
- the site network stays private,
- maintenance works even behind NAT,
- access can be limited to a small set of trusted devices/users.

---

## 4) Access scope and boundaries

Remote access is scoped to:
- the Edge gateway host (SSH, dashboards, logs),
- optionally: a debug view service (web endpoint) reachable only inside the VPN.

Remote access is not scoped to:
- direct public access to STM32 or FPGA nodes,
- direct public access to the local broker.

If remote access to internal devices is required, it is done through:
- the gateway as a jump host, or
- an explicit VPN policy that restricts exactly what is allowed.

---

## 5) Operational procedure (safe usage model)

### 5.1 Enable access
- Only enable remote access for a maintenance window.
- Ensure the operator knows access is active.

### 5.2 Authenticate and connect
- Use strong credentials (SSH keys, device enrollment).
- Ensure only approved devices are allowed.

### 5.3 Read-only first
Before sending any commands:
- inspect system state and health topics,
- confirm no active safety alarms,
- confirm the lane is not in an unsafe state.

### 5.4 Controlled actions
If an operator override is required:
- use the cloud dashboard (audited) if available, or
- use the approved local maintenance procedure.

### 5.5 Disable access
After the maintenance task:
- disable remote access if it was temporary,
- rotate keys if a compromise is suspected,
- keep logs for traceability.

---

## 6) Debug video / camera streaming (maintenance only)

SysPark can expose a debug video stream for maintenance. Principles:
- no public URL,
- stream reachable only inside the overlay VPN,
- stream is optional and can be turned off by default.

Privacy and compliance note:
- license plates and faces may be present in images.
- prefer to stream only when strictly required.
- consider masking or limiting stored snapshots depending on legal context.

---

## 7) Logging and traceability

At minimum, keep records of:
- when remote access was enabled/disabled,
- which identity connected (device/user),
- what critical actions were triggered (manual overrides, configuration changes).

If the cloud is available, operator commands should be logged there for audit.

---

## 8) Failure and safety behavior

Remote access failing must not impact:
- barrier safe behavior,
- local lane usability,
- emergency procedures.

If remote access is misconfigured:
- default to “closed” (no connectivity) rather than exposing services publicly.

---

## 9) Recommended hardening checklist

- Do not expose local broker ports publicly.
- Disable password SSH login; use SSH keys.
- Restrict VPN membership to trusted devices only.
- Use least privilege: do not grant broad access by default.
- Keep the gateway updated and supervised (auto-restart critical services).
- Keep an emergency on-site manual procedure that does not require remote access.

