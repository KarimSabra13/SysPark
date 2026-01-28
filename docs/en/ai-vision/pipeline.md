Language: English | [Français](../../fr/ai-vision/pipeline.md)

# AI / Vision Pipeline (License Plate Recognition)

SysPark uses an optional AI/Vision module to support **license plate recognition (LPR/ANPR)** and enrich the parking flows with a second identification signal. The vision module runs at the edge (on-site), publishes results to MQTT, and integrates with the Cloud to link a vehicle to a parking session when needed.

Design principles:
- Vision improves usability and automation, but **must not be a single point of failure**.
- The lane must keep operating using fallback identifiers (RFID/PIN/operator mode).
- Results must include **confidence** and be treated as probabilistic.

---

## 1) Where the vision module fits

### On-site execution
The vision pipeline runs on the Edge gateway (or a dedicated edge compute node). It interacts with:
- camera capture (entry/exit lane),
- local MQTT broker (publish results),
- orchestration logic (state machine),
- cloud backend (session matching, billing context).

### Responsibilities
- capture images or frames,
- detect plate region(s),
- read characters (OCR),
- normalize and validate formatting,
- compute confidence,
- publish result events to the system bus.

---

## 2) End-to-end pipeline stages

### Stage A: Capture
Input:
- still image capture on trigger (presence detected), or
- short frame burst around the trigger.

Recommendations:
- capture multiple frames to increase success probability,
- keep exposure stable (avoid motion blur),
- timestamp each capture event.

### Stage B: Plate detection (localization)
Goal:
- find the plate region in the image.

Output:
- bounding box(es),
- detection confidence.

Notes:
- handle multiple detections (front + rear reflections, false positives),
- keep the “best candidate” but preserve metadata when possible.

### Stage C: OCR (character recognition)
Goal:
- read characters inside the plate crop.

Output:
- raw OCR string(s),
- OCR confidence per candidate.

Notes:
- OCR can produce common confusions (O/0, I/1, B/8).
- Using multiple frames can stabilize the result.

### Stage D: Normalization and validation
Goal:
- convert raw OCR output into a clean plate string usable by the rest of the system.

Typical operations:
- uppercase normalization,
- remove separators and spaces,
- reject illegal characters,
- country-specific formatting rules (optional),
- heuristic corrections (only if conservative).

Output:
- `plate_normalized`,
- `format_valid` (boolean),
- `final_confidence` (combined score).

### Stage E: Publish result to MQTT
The vision module publishes a result event with:
- normalized plate,
- confidence score,
- timestamp,
- lane identifier (entry/exit),
- optional: frame id, bounding box metadata (not required for core flow).

---

## 3) MQTT data contract (vision events)

Recommended topic naming (one of the two approaches):

### Option A: Dedicated vision topic
- `parking/vision/plate`

### Option B: Lane-scoped vision topics
- `parking/entry/vision/plate`
- `parking/exit/vision/plate`

Payload (JSON recommended):
- `ts`: timestamp
- `src`: `vision`
- `lane`: `entry` or `exit`
- `plate`: normalized plate string
- `confidence`: numeric score (0..1 or 0..100, but be consistent)
- `valid`: boolean
- optional: `frame_id`, `bbox`, `candidates` (keep optional to avoid heavy payloads)

QoS:
- QoS 1 recommended (event should arrive)

Retain:
- No (events are not “state”)

---

## 4) How the plate is used in SysPark flows

### Entry flow (optional enhancement)
Possible uses:
- associate plate with a new session at entry,
- provide a second factor next to RFID,
- reduce operator interventions.

Rules:
- low confidence must not block entry automatically.
- if RFID is present, use RFID as the primary stable identifier.

### Exit flow (high value)
Primary use:
- match the exiting vehicle to an existing session and compute the fee.

Rules:
- a plate read may be used to propose a session match,
- but payment authorization remains cloud-validated,
- fallback paths are mandatory if plate read fails.

---

## 5) Confidence thresholds and fallback behavior

Define at least two thresholds:

### High-confidence threshold
If `confidence >= HIGH` and `valid == true`:
- auto-use plate for session match,
- proceed in the normal automated flow.

### Medium-confidence threshold
If `LOW <= confidence < HIGH`:
- treat as “suggestion”:
  - show to operator dashboard,
  - request confirmation through a secondary identifier (RFID/PIN).

### Low-confidence threshold
If `confidence < LOW` or `valid == false`:
- discard automatic decision use,
- fall back to RFID/PIN/operator flow.

Important:
- thresholds must be tuned per camera placement and lighting conditions.
- do not over-trust OCR output.

---

## 6) Operational constraints (camera placement and lighting)

Vision quality depends strongly on:
- observed plate size in pixels,
- angle (tilt, perspective),
- night illumination and glare,
- motion blur from slow shutter,
- dirty plates and occlusions.

Recommendations:
- mount camera with stable framing per lane,
- aim for a close-enough crop (plate not too small),
- add consistent lighting if needed,
- keep lens clean and stable.

---

## 7) Privacy and compliance notes

License plates are personal data in many contexts. Recommended handling:
- avoid storing raw frames unless required for debugging,
- if storing snapshots, restrict access and retention,
- prefer storing only the normalized plate and confidence,
- consider masking in operator views if required by policy.

---

## 8) Acceptance checks

A vision pipeline is considered integrated when:
- it publishes structured plate events reliably to MQTT,
- confidence thresholds behave predictably (no blocking due to low confidence),
- exit flow can match sessions when confidence is high,
- the system remains usable when vision is disabled or failing.

