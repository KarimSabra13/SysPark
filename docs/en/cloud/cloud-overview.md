Language: English | [Français](../../fr/cloud/cloud-overview.md)

# Cloud Backend Overview (Render)

SysPark uses a cloud backend to provide a single “source of truth” for access policy, sessions, payments, dashboards, and long-term traceability. The cloud does not directly drive hardware timing. Instead, it publishes high-level decisions and receives telemetry through MQTT.

This backend is designed for B2B deployments where supervision, auditability, and secure remote operations matter.

---

## 1) What the Cloud does (scope)

### Core responsibilities
- Persist system state and historical data (sessions, events, users, configuration).
- Compute decisions that require global context (tariffs, rules, occupancy, remote overrides).
- Manage payments (payment request, validation, proof, session closure).
- Provide an admin dashboard for operators (live state + history).
- Trigger alerts and notifications (operators, maintenance).

### What the Cloud does not do
- It does not implement low-level deterministic motion control.
- It does not replace local safety logic.
- It must not be a single point of failure for basic site safety.

---

## 2) Platform choice: Render (Web service + PostgreSQL)

SysPark cloud is hosted on Render with:
- A web service (the backend application runtime).
- A managed PostgreSQL database.

Operational benefits:
- Simple deployment from Git repository.
- Built-in environment variables management.
- Database provisioning and internal connectivity.

---

## 3) Real-time communications model (MQTT + Web UI)

SysPark cloud uses a public MQTT broker as a real-time relay between:
- the physical parking site (through an edge bridge),
- the cloud backend (decision engine + persistence).

### Why MQTT
- asynchronous event-driven model,
- low overhead,
- clean separation between producers (site) and consumers (cloud),
- easy to scale across multiple sites.

### Bridge principle
A selective bridge at the edge forwards only approved topics:
- avoids loops,
- limits exposure,
- keeps the local LAN independent.

For the canonical topic contract, see:
- `docs/en/cloud/mqtt-topics.md`

---

## 4) External services integrated in the Cloud

### 4.1 Payments (Stripe)
Role:
- compute amount and generate payment request context,
- validate payment confirmation from the payment provider,
- publish “payment success” to unlock the exit flow,
- attach proof to the session record.

Key design points:
- payments are validated by a dedicated webhook endpoint,
- no “trust” is placed in client-side confirmations.

### 4.2 Notifications (Telegram)
Role:
- push operational alerts (faults, safety events, abnormal states),
- send key events to operators without requiring them to stay on the dashboard.

### 4.3 Weather data (OpenWeatherMap + local client)
Role:
- provide contextual data used for display or analytics.
Implementation note:
- a small local client periodically fetches weather and posts it to the cloud, then it is published to MQTT.

### 4.4 Secure remote access (Tailscale)
Role:
- enable safe maintenance access (debug, video tunnel) without opening inbound ports on the site router.
Design intent:
- remote access should be explicit, temporary, and auditable.

---

## 5) Database responsibility and data model (conceptual)

The database stores the long-term record for:
- users and access credentials (logical identity and permissions),
- sessions (entry time, exit time, plate or badge reference, status),
- payments (amount, provider reference, validated timestamp),
- events and alarms (what happened, when, and outcome),
- configuration snapshots (tariffs, policy switches, ACL sync state).

Design principle:
- every critical action produces a traceable record,
- manual overrides are logged with operator identity (when applicable),
- the cloud remains the audit layer even if the site operates offline temporarily.

---

## 6) Admin dashboard (operator view)

The web interface provides:
- live occupancy indicators and last known states,
- recent events feed (entries, exits, alarms, overrides),
- session search and evidence (plate snapshots if enabled, payment proof),
- admin actions:
  - update policies and tariffs,
  - manage access rights,
  - trigger controlled commands (open/close requests) through MQTT.

Real-time updates:
- the dashboard subscribes to cloud-side state updates to remain responsive.

---

## 7) Configuration and secrets (environment variables)

SysPark cloud uses environment variables to store secrets and deployment parameters:
- database connection string,
- MQTT broker host/port and credentials,
- admin credentials,
- payment provider keys and webhook secret,
- notification bot token and chat ID,
- application-level shared secret used for sensitive remote updates.

Security baseline:
- secrets never committed to Git,
- rotate keys when needed,
- restrict who can change environment variables.

---

## 8) Deployment lifecycle (high-level)

1. Push documentation and server configuration to Git.
2. Render pulls the repository to build the web service.
3. Configure environment variables in Render.
4. Provision PostgreSQL and attach it to the service.
5. Connect cloud to the public MQTT broker (TLS).
6. Validate end-to-end flows:
   - telemetry arrives from the site,
   - decisions are published back,
   - payments and notifications work.

---

## 9) Failure modes and resilience expectations

### Internet outage
- site should keep basic operations with cached policies,
- cloud continues to accept updates when connectivity returns.

### Public broker outage
- site continues locally,
- cloud supervision may degrade until broker recovers.

### Cloud outage
- site must remain safe,
- operations fall back to local modes and operator procedures.

---

## 10) Where this fits in the documentation

- Architecture: `docs/en/overview/architecture.md`
- System flows: `docs/en/overview/system-flows.md`
- MQTT contract: `docs/en/cloud/mqtt-topics.md`

