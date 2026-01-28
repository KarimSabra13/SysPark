Language: English | [Français](../../fr/ai-vision/models.md)

# Vision Models and Inference Strategy (SysPark)

SysPark’s vision module is organized as a pipeline of model-driven steps. Instead of relying on a single “end-to-end” model, SysPark separates the problem into:
1) plate localization (detect the plate region),
2) character recognition (OCR),
3) post-processing (normalization and validation).

This modular approach makes the system easier to debug in real deployments and supports graceful fallback when confidence is low.

---

## 1) Model blocks (conceptual)

### 1.1 Plate detection model (localization)
Purpose:
- find the license plate region in an image.

Outputs:
- bounding box coordinates (x, y, w, h),
- detection confidence.

Operational requirements:
- robust to angle, partial occlusion, glare,
- stable detection for “near-plate” shots typical in a lane.

### 1.2 OCR model (characters)
Purpose:
- read characters inside the cropped plate region.

Outputs:
- one or multiple candidate strings,
- per-candidate confidence.

Operational requirements:
- handle plate fonts and spacing variability,
- remain usable under compression and moderate blur,
- avoid over-confident hallucinations.

### 1.3 Post-processing (rule-based)
Purpose:
- convert raw OCR into a clean plate string.

Typical operations:
- uppercase,
- remove spaces/separators,
- reject invalid characters,
- apply formatting heuristics conservatively.

Outputs:
- normalized plate string,
- validity flag,
- final confidence score.

---

## 2) Confidence strategy (how to decide “trust”)

SysPark treats vision output as probabilistic.

### 2.1 Confidence composition
Final confidence can be computed using:
- detection confidence,
- OCR confidence (best candidate),
- agreement across frames (temporal stability),
- format validity.

Example logic (conceptual):
- if the same plate appears across N frames with consistent OCR,
  increase confidence.
- if format validity fails, cap confidence.

### 2.2 Thresholds
Define at least:
- `LOW`: below this, do not use automatically.
- `HIGH`: above this, auto-use in session matching.
- between LOW and HIGH, treat as suggestion requiring confirmation.

Thresholds must be tuned per deployment because camera placement and lighting dominate performance.

---

## 3) Multi-frame inference (stability over time)

SysPark recommends multi-frame inference for better reliability:
- capture a short burst of frames around the trigger,
- run detection + OCR per frame,
- aggregate results:
  - majority vote for the plate string,
  - confidence boost when consensus is strong,
  - discard outliers.

Benefits:
- reduces “single-frame” glitches,
- mitigates transient blur and glare.

Constraints:
- CPU budget must stay compatible with real-time lane needs.
- the system must not block lane flow while waiting for too many frames.

---

## 4) Deployment constraints (edge reality)

### 4.1 Latency budget
Vision must return a result fast enough to support:
- session matching at exit,
- driver UI prompts.

If computation is slow:
- return “unknown” and fall back to RFID/PIN,
- do not block.

### 4.2 Resource usage
On edge hardware:
- inference competes with MQTT, streaming (if enabled), and general services.
- memory usage must remain stable over long runtimes.

### 4.3 Environmental conditions
Common real-world factors:
- night illumination changes,
- glare and reflections,
- dirty plates,
- rain, fog,
- vibration.

The model strategy must assume these will happen.

---

## 5) Output contract (what a model result must include)

Minimum payload fields to publish:
- lane (entry/exit),
- normalized plate,
- confidence score,
- validity flag,
- timestamp.

Optional:
- candidate list (top-K),
- frame id,
- bounding box (debug only).

Design rule:
- keep payload light on MQTT.
- do not publish raw images on MQTT.

---

## 6) Validation approach (without code)

SysPark validates vision using field-like scenarios rather than synthetic demos.

### 6.1 Dataset acquisition
Collect representative samples:
- day and night,
- different vehicle types and plate styles,
- varying speeds,
- glare scenarios.

### 6.2 Metrics
Track:
- detection success rate,
- OCR exact match rate,
- confidence calibration (how often high confidence is wrong),
- time-to-result.

### 6.3 On-site acceptance
The pipeline is accepted when:
- high-confidence results are rarely wrong,
- low-confidence results do not block the flow,
- fallback behaviors remain usable,
- operator intervention rate is reduced.

---

## 7) Failure handling policy

When vision fails or is uncertain:
- publish an event with `valid=false` or low confidence,
- do not attempt aggressive retries that increase system load,
- rely on RFID/PIN/operator fallback.

Vision should never cause unsafe actuation.

