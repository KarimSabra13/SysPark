Language: English | [Français](../../fr/ai-vision/validation.md)

# Vision Validation Plan (Field-Oriented)

This document defines a practical validation plan for SysPark’s license plate recognition module. The goal is not to achieve perfect OCR in all conditions, but to ensure the system behaves correctly:
- **high-confidence outputs are reliable enough to automate session matching**,
- **low-confidence outputs never block the lane**,
- **fallback identification remains smooth**,
- performance remains stable over long runtimes.

---

## 1) Validation objectives

### Core objectives
- Verify end-to-end plate event publishing to MQTT.
- Verify confidence thresholds behave as intended.
- Verify session matching benefits at exit (reduced operator interventions).
- Verify the system remains safe and usable when vision fails.

### Secondary objectives
- Characterize performance across lighting and weather conditions.
- Identify camera placement constraints and minimum quality requirements.
- Define regression tests to prevent future degradation.

---

## 2) Test environments (recommended set)

To avoid “lab-only” bias, test in multiple environments:

### A) Controlled indoor / lab
- consistent lighting,
- repeatable distances,
- useful for early debugging.

### B) Realistic outdoor lane
- day and night,
- variable lighting and glare,
- realistic vehicle approach angles.

### C) Stress environment
- moving vehicles with higher speed,
- poor weather (rain/fog) if possible,
- low-light conditions.

---

## 3) Test scenarios (what to run)

### Scenario 1: Static vehicle, ideal conditions
- Vehicle stopped at the expected capture point.
- Goal: verify baseline detection + OCR.

Expected:
- high confidence,
- stable plate across frames.

### Scenario 2: Slow approach, daytime
- Vehicle approaching slowly, slight motion blur.
- Goal: validate multi-frame aggregation.

Expected:
- consistent final plate,
- confidence improves with consensus.

### Scenario 3: Night mode with artificial lighting
- Low light, headlight glare.
- Goal: detect failure modes and ensure thresholds protect the flow.

Expected:
- more medium/low confidence,
- no lane blocking.

### Scenario 4: Occlusion and dirt
- Partially covered plate or dirty plate.
- Goal: ensure system does not “hallucinate” and over-trust.

Expected:
- low confidence or invalid plate,
- fallback triggered.

### Scenario 5: Multiple vehicles / reflections
- Vehicle with reflective surfaces or background patterns.
- Goal: validate detector false positives handling.

Expected:
- best-candidate selection stable,
- low confidence on false positives.

### Scenario 6: Exit session matching
- Real sessions created at entry then matched at exit.
- Goal: measure operational improvement.

Expected:
- high-confidence matches reduce manual selection.

---

## 4) Data collection method (practical)

For each run, collect:
- timestamp,
- lane (entry/exit),
- final plate and confidence,
- validity flag,
- top candidate list (optional),
- time-to-result (latency),
- ground-truth plate label (operator noted).

Important:
- avoid storing full video unless necessary.
- if storing frames for debugging, restrict access and retention.

---

## 5) Metrics (what to measure)

### Accuracy metrics
- **Detection success rate**: % of triggers where a plate region was detected.
- **OCR exact match rate**: % where final plate equals ground truth.
- **High-confidence precision**: when confidence >= HIGH, % correct.
- **Medium-confidence usefulness**: % where the correct plate appears in candidates.

### Calibration metrics
- **Confidence reliability**: high confidence should be rarely wrong.
- **False positive rate**: rate of valid-looking but wrong plates.

### Performance metrics
- **Time-to-result**: trigger → publish event.
- **CPU utilization** (edge device stability, qualitative is acceptable).
- **Memory stability** over long runtime.

---

## 6) Acceptance thresholds (deployment-oriented)

Because conditions vary per site, define acceptance per deployment, but a realistic baseline:

- High-confidence precision: very high (aim for “rarely wrong”).
- Low-confidence results must never block lane flow.
- Typical time-to-result: fast enough to keep driver experience smooth.
- Stable behavior for multi-hour runs (no memory leaks, no crash loops).

If a deployment cannot reach the target:
- adjust camera placement and lighting first,
- then tune thresholds.

---

## 7) Regression checklist (to prevent future breaks)

Whenever the vision module changes (models, camera, parameters), rerun:
- Scenario 1 (baseline),
- Scenario 3 (night/glare),
- Scenario 4 (occlusion),
- Exit session matching scenario (end-to-end).

Additionally verify:
- MQTT payload contract unchanged,
- thresholds unchanged or documented,
- fallback behavior still works.

---

## 8) Operational decision rules (how to use results)

- If high-confidence precision is not acceptable, raise HIGH threshold.
- If the system is too conservative and reduces automation too much, lower HIGH slightly but only if precision remains good.
- If false positives occur, tighten format validation and candidate filtering.
- If time-to-result is too high, reduce frame burst size or optimize the pipeline.

---

## 9) Final integration “pass” criteria

Vision is considered production-usable in SysPark when:
- it publishes reliable structured events,
- high-confidence results are trustworthy enough to automate matching,
- lane flows remain smooth under low-confidence conditions,
- the system does not depend on vision to remain safe.

