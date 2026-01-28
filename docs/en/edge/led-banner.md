Language: English | [Français](../../fr/edge/led-banner.md)

# LED Banner / Driver-Facing Display

SysPark includes a driver-facing display (LED banner) to provide immediate, unambiguous feedback at the entry and exit lanes. This is a key usability and safety element: drivers must understand what the system expects from them without needing an operator.

The display is controlled through MQTT so that any validated decision source (Edge orchestration or Cloud policy) can update the message consistently.

---

## 1) Purpose

### Core goals
- Reduce confusion at the barrier (clear instructions).
- Make the flow state visible (identify, wait, proceed, pay).
- Provide immediate feedback in degraded situations (fault, offline).
- Support B2B deployment needs (operators want predictable messaging).

### Constraints
- Must remain functional in local-only mode (LAN).
- Must not block safety behavior (display is informational, not an actuator).

---

## 2) Display control model

### Message-driven design
The display is updated by publishing text messages on an MQTT topic.

Canonical topic:
- `parking/display/text`

Direction:
- Cloud → Local (through the bridge), or Edge → Local (directly on the LAN broker)

QoS:
- QoS 1 recommended (message must arrive, duplicates acceptable)

Retain:
- No retain by default (messages are transient instructions)

---

## 3) Message format

Two practical options exist:

### A) Plain text payload (minimal)
- Payload is a string, directly displayed.

Examples:
- `WELCOME`
- `PLEASE IDENTIFY`
- `PAYMENT REQUIRED`
- `PROCEED`
- `WAIT`
- `CALL OPERATOR`

### B) JSON payload (for richer control)
If richer behavior is needed, use JSON such as:
- `text`: displayed content
- `ttl_s`: time-to-live before auto-clear
- `lane`: entry/exit identifier
- `prio`: priority level

Design note:
- keep JSON optional; plain text is often enough for reliability.

---

## 4) Recommended message catalog

To keep user experience consistent, SysPark should standardize a small message set.

### Entry lane messages
- Welcome / idle:
  - “WELCOME”
- Prompt identification:
  - “PRESENT BADGE”
  - “ENTER PIN”
- Access granted:
  - “PROCEED”
- Access denied:
  - “ACCESS DENIED”
- Full parking:
  - “FULL”
- Busy / processing:
  - “WAIT”
- Fault:
  - “FAULT CALL OPERATOR”

### Exit lane messages
- Idle:
  - “EXIT”
- Payment required:
  - “PAYMENT REQUIRED”
- Payment in progress:
  - “PAYING…”
- Payment confirmed:
  - “PAID PROCEED”
- Unknown session / fallback:
  - “SEE OPERATOR”
- Fault:
  - “FAULT CALL OPERATOR”

---

## 5) Update rules and priorities

### Priority concept (recommended)
Some messages should override others:
1. Emergency / safety: “STOP”, “EVACUATE”, “FAULT…”
2. Fault states: “CALL OPERATOR”
3. Flow prompts: “PAYMENT REQUIRED”, “PRESENT BADGE”
4. Informational: “WELCOME”, “EXIT”

### TTL behavior (optional)
If TTL is implemented:
- short TTL for prompts to avoid stale instructions,
- long TTL for fault states until cleared.

### Lane separation
If the site has multiple lanes, messages should be lane-scoped:
- either by topic hierarchy (e.g., `parking/entry/display/text`)
- or by payload field `lane`.

---

## 6) Failure behavior

### MQTT unavailable
- If the display cannot receive updates:
  - show a safe default message (e.g., “WAIT” or “CALL OPERATOR”),
  - do not attempt uncontrolled retries that flood the broker.

### Cloud unavailable
- Edge can drive the display locally.
- Messages degrade gracefully (e.g., payment disabled → “SEE OPERATOR”).

### Conflicting publishers
To prevent message fights:
- define one authoritative publisher per lane (usually Edge),
- allow Cloud to publish only specific classes (e.g., payment confirmed),
- enforce bridge allowlist rules accordingly.

---

## 7) Operational guidelines (text quality)

- Use short words, high contrast, and consistent vocabulary.
- Avoid ambiguous sentences.
- Prefer uppercase and fixed-width formatting if the banner supports it.
- Keep messages language-consistent per deployment (EN or FR).
- Avoid displaying personal data (full plate number) on the public banner.

---

## 8) Where this fits in the system

- The display is an output device controlled by the orchestration layer.
- It reflects the system state but does not control it.
- It should be testable independently by publishing messages to the topic.

