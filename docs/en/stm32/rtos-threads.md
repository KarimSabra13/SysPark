Language: English | [Français](../../fr/stm32/rtos-threads.md)

# Zephyr RTOS Threading Model (STM32 Node)

This document explains how the STM32 SysPark application is structured into Zephyr threads and synchronization objects. The goal is to keep time-sensitive tasks deterministic while still handling Ethernet/MQTT networking, UI refresh, and microSD persistence reliably.

Key design targets:
- motor timing must not be blocked by network or storage,
- RFID acquisition must remain responsive,
- UI must reflect the state machine clearly,
- MQTT messages must be routed without deadlocks,
- SD writes must be serialized to avoid corruption.

---

## 1) Thread map (conceptual)

A typical SysPark STM32 node is structured around these thread families:

### A) Communications and routing
- **MQTT client thread**
  - maintains broker connection,
  - handles subscribe/publish,
  - parses inbound command messages.

- **Event router / state machine thread**
  - consumes “input events” (RFID UID, payment success, sensor signals),
  - updates the lane state machine,
  - publishes resulting state topics and UI messages.

### B) Acquisition
- **RFID acquisition thread**
  - reads the RFID device interface,
  - extracts UID and formats it,
  - pushes UID into a message queue.

- **Sensor sampling thread (optional)**
  - reads limit switch, presence inputs, or analog sensors,
  - publishes snapshots or triggers alarms.

### C) User interfaces
- **LCD update thread**
  - displays lane prompts (identify, wait, proceed, pay),
  - shows network status and faults,
  - must never block critical control loops.

- **OLED update thread (optional)**
  - dedicated to elevator status or detailed debug view.

### D) Motion control (entry role)
- **Elevator control thread**
  - implements homing at startup,
  - executes deterministic motion sequences,
  - monitors limit switches and timeouts,
  - publishes state periodically.

### E) Persistence
- **Storage thread**
  - serializes microSD reads/writes,
  - stores PINs and ACL updates,
  - can store periodic logs with wear-aware policy.

Not every build uses all threads; exit-only role may disable motion.

---

## 2) Priority and timing guidelines

A safe priority ordering is:

1. **Motion control / safety monitoring**
   - highest priority
   - must meet timing constraints

2. **RFID acquisition**
   - high priority
   - should remain responsive

3. **Event router / state machine**
   - medium-high priority
   - should keep UI and MQTT coherent

4. **MQTT communication**
   - medium priority
   - connection maintenance, publish/sub handling

5. **UI rendering**
   - low/medium
   - should not impact motor or RFID

6. **Storage**
   - low priority
   - can run in background with controlled scheduling

Design note:
- if MQTT is heavy, it must not starve the control threads.
- SD writes must not run in a high-priority context.

---

## 3) Synchronization objects (what is used and why)

SysPark uses a small set of synchronization primitives:

### Message queues
Used for decoupling producers from consumers:
- RFID acquisition → UID queue
- MQTT inbound → command queue
- state machine → UI queue
- state machine → storage queue

Benefits:
- avoids blocking calls in acquisition threads,
- provides backpressure and bounded memory usage.

### Semaphores / flags
Used for one-shot authorizations:
- payment success can “unlock” the exit flow,
- an enroll mode can be toggled for new badge enrollment.

### Mutex (storage lock)
Used to protect microSD access:
- prevents concurrent writes from different tasks,
- reduces corruption risk.

### Timers
Used for:
- periodic publishing (heartbeat, elevator state),
- timeouts (motion deadline, broker reconnect),
- UI refresh scheduling.

---

## 4) Event-driven state machine (central logic)

The STM32 behavior is easiest to maintain when centralized as a state machine.
This state machine consumes input events and produces:
- actuator commands (only inside allowed boundaries),
- MQTT publish events,
- UI updates,
- storage update requests.

### Example input events
- `UID_DETECTED(uid)`
- `PIN_OK` / `PIN_FAIL`
- `PAYMENT_SUCCESS(session_id)`
- `LIMIT_SWITCH_HIT`
- `MOTION_TIMEOUT`
- `MQTT_DISCONNECTED`

### Example output actions
- publish identification event,
- update LCD/OLED prompt,
- trigger motion sequence (entry role),
- block/unblock exit gate sequence (exit role),
- persist ACL updates to microSD.

---

## 5) Entry role details (elevator thread integration)

In entry mode, the elevator thread typically runs:
1. startup homing:
   - moves until limit switch is hit,
   - sets position reference to known “floor 0” (or equivalent),
   - publishes “homed” status.

2. commanded motion:
   - receives a target floor from state machine,
   - converts to steps,
   - executes controlled stepping,
   - monitors timeout and limit switch.

3. publish:
   - periodic state update topic (position, floor, direction, fault status).

Safety rules:
- any timeout or unexpected limit switch triggers safe stop.
- state machine is notified so UI can show “fault”.

---

## 6) Exit role details (payment gating using semaphore-like sync)

In exit mode, the node uses a “gate unlock” logic:
- when `payment/success` arrives:
  - signal an authorization flag/semaphore,
  - update UI prompt (“PAID PROCEED”),
  - allow the next step in the exit sequence.

Idempotency:
- repeated payment success messages for same session must not re-trigger unsafe behavior.
- the state machine should check whether the exit is already authorized.

---

## 7) Storage thread: safe persistence strategy

### What must be persisted
- PIN values (entry/exit if enabled),
- ACL list (authorized badge UIDs),
- last applied config version (optional),
- minimal logs (optional).

### Wear-aware policy
- avoid writing on every event if not necessary,
- batch updates and flush periodically,
- keep a simple structured format (e.g., one JSON file or line-based records).

### Robustness
- never write from an ISR or a high-priority motor context,
- always validate file operations and publish an “ACL sync OK/FAIL” event.

---

## 8) Observability (how to debug threading problems)

Recommended debug signals:
- publish periodic heartbeat with:
  - free memory estimate,
  - MQTT connection state,
  - last error code.
- record fault transitions in a small ring buffer.
- ensure stack sizes are explicitly configured and verified under stress.

Common failure patterns:
- SD access blocks UI and starves MQTT,
- MQTT parsing blocks the router thread,
- unbounded queues grow and cause memory pressure.

---

## 9) Minimal acceptance checks

A threading model is considered correct when:
- motor timing remains stable during heavy MQTT traffic,
- RFID reads remain responsive while UI is updating,
- SD writes do not corrupt files under reconnect storms,
- payment success reliably unlocks exit without duplication issues,
- the node recovers cleanly after broker reconnect.

