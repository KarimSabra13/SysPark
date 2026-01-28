Language: English | [Français](../../fr/stm32/storage-sd.md)

# microSD Storage and Persistence (STM32 Node)

SysPark uses a microSD card on the STM32 node to persist small but critical data across reboots. The goal is not to build a heavy database on the microcontroller, but to ensure local autonomy and predictable recovery when connectivity is unstable.

Key design intent:
- keep the parking usable in LAN-only mode,
- avoid losing access credentials (PINs/ACL) after reset,
- maintain minimal traceability without wearing out the SD card.

---

## 1) What is stored (persistence scope)

### Required persistent items
- **Entry PIN** (if PIN mode is enabled)
- **Exit PIN** (if PIN mode is enabled)
- **ACL whitelist** (authorized RFID UIDs)
- **Last applied configuration marker** (optional, for sync and debugging)

### Optional persistent items
- **Local event log** (small, low-frequency)
- **Last known network parameters** (only if needed, static IP is preferred for demos)
- **Calibration/homing markers** (if useful for boot speed, but safety must be preserved)

---

## 2) Why store locally (even with a cloud DB)

Local storage exists because:
- internet can fail,
- public broker can fail,
- the cloud can be unreachable,
- the STM32 must still allow basic flows under a site-defined offline policy.

The cloud remains the long-term audit layer, but the STM32 needs enough state to behave correctly without it.

---

## 3) File layout (recommended)

A simple file layout is preferred. Example directory:
- `/SYS_PARK/`

Recommended files:
- `/SYS_PARK/pins.json`
- `/SYS_PARK/acl.json`
- `/SYS_PARK/state.json` (optional)
- `/SYS_PARK/log/events.log` (optional)

### pins.json (example)
- `entry_pin`
- `exit_pin`
- `updated_ts`

### acl.json (example)
- `version`
- `updated_ts`
- `uids` (array of UID strings)

### state.json (optional)
- last boot timestamp
- last MQTT sync timestamp
- last known role (entry/exit)
- last fault code

Design rule:
- keep files small and easy to parse,
- prefer one “source of truth” file per category.

---

## 4) Update workflow (cloud → edge → STM32 persistence)

ACL and PIN updates can be driven by the cloud and delivered through MQTT.

### Step-by-step
1. Cloud publishes an update command (e.g., add/remove UID, replace full list).
2. Edge bridge forwards only allowlisted topics.
3. STM32 receives the command and validates it:
   - message schema
   - optional application secret field
4. STM32 applies update in RAM.
5. STM32 writes the updated file to microSD safely.
6. STM32 publishes an acknowledgement event:
   - success/failure
   - current version marker

This makes updates traceable and robust.

---

## 5) Safe write strategy (avoid corruption)

### Atomic update pattern
To avoid corrupting the only copy of the file:
1. Write new content to a temporary file:
   - `acl.json.tmp`
2. Flush and close.
3. Rename:
   - replace `acl.json` with the `.tmp` file

This provides a near-atomic update on most filesystems used on microSD.

### Validation before commit
- Validate JSON format before rename.
- Validate UID constraints (length, allowed chars).
- Validate PIN constraints (digits only, expected length).

### Recovery strategy
On boot:
- if the main file is missing or invalid,
  - attempt to load the `.tmp` file,
  - otherwise fall back to safe defaults (restricted mode).

---

## 6) SD access serialization (threading constraint)

Because multiple tasks may request persistence:
- only one storage thread performs SD operations,
- other threads communicate via a storage queue,
- a mutex protects the actual SD driver layer.

Never write to SD from:
- ISR contexts,
- high-priority motor timing threads,
- MQTT callback contexts if they can block.

---

## 7) Wear-aware policy (reduce write frequency)

microSD has finite write endurance. SysPark must avoid “write on every event”.

Recommended policies:
- batch ACL updates and write at most once per update transaction,
- debounce repetitive writes (e.g., multiple commands arriving within seconds),
- log only essential events,
- rotate logs with size limits,
- avoid rewriting large full-list files too often if add/remove commands suffice.

---

## 8) Data integrity and security notes

### Integrity
- Always publish an ack after applying updates so the cloud knows the real state.
- Include a version counter in ACL.
- Include timestamps for traceability.

### Security
- Sensitive updates should require an application secret and/or broker-level ACL.
- Avoid storing secrets in plaintext if not required.
- Do not store full personal data; store only what is needed (UID tokens).

---

## 9) Acceptance tests

A correct storage implementation should pass:
- power cycle recovery (PIN and ACL are still valid),
- repeated ACL updates without file corruption,
- concurrent event storm without SD deadlocks,
- safe fallback when SD is missing or unreadable,
- bounded log growth.

