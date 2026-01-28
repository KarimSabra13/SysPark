Language: English | [Français](../../fr/ai-vision/video-streaming.md)

# Video Streaming (Maintenance and Debug)

SysPark can optionally expose a live video stream to help maintenance, camera alignment, and vision pipeline debugging. Streaming is not required for normal operation. It is an operational tool that must follow strict security and privacy rules.

Core rule:
- **No public streaming endpoints.**
- Streams are reachable only through a secured maintenance channel (overlay VPN) and only when needed.

---

## 1) Purpose

### Why streaming exists
- Camera framing and focus validation during installation.
- Debugging vision failures (glare, motion blur, plate angle).
- Remote maintenance when an operator cannot physically access the camera.

### What streaming is not
- It is not a customer-facing feature.
- It is not a permanent monitoring feed.
- It should not become a dependency for lane safety.

---

## 2) Access model (VPN-only)

Streaming must be available only inside the secure maintenance network:
- overlay VPN access (example: Tailscale),
- restricted device membership,
- no inbound port forwarding on the site router.

Recommended approach:
- stream server runs on the Edge gateway,
- access limited to VPN identities authorized for maintenance.

---

## 3) Operational procedure (safe workflow)

1. Enable streaming only for a maintenance window.
2. Verify lane is in a safe condition (no active motion hazard).
3. Connect through the VPN and open the stream endpoint.
4. Perform camera alignment or debug observation.
5. Disable streaming after completion.

If remote access is unavailable:
- default to on-site maintenance procedure.

---

## 4) Privacy and compliance considerations

Video frames may contain:
- license plates,
- faces,
- vehicle identifiers.

Recommended privacy principles:
- avoid recording by default,
- limit stream access to authorized maintainers only,
- if snapshots are stored:
  - set a retention policy,
  - restrict access,
  - store minimal resolution and minimal time window.

Operator-visible UIs should avoid displaying full personal data unless required.

---

## 5) Network and performance constraints

Streaming can consume bandwidth and CPU/GPU resources on the edge device.
Guidelines:
- use moderate resolution and frame rate for debug (not full HD unless required),
- ensure streaming does not starve MQTT/vision computation,
- keep the streaming service optional and easy to turn off.

---

## 6) Failure modes

### Stream unavailable
- The parking must still operate normally.
- Vision pipeline should continue to run without the streaming service.

### Network unstable
- Streaming quality may degrade, but must not affect safety.
- Avoid reconnect storms that load the device.

### Security misconfiguration
- If streaming cannot be constrained to VPN-only, do not enable it.
- Prefer “closed” default behavior.

---

## 7) Acceptance criteria

Streaming integration is acceptable when:
- the stream is reachable only via VPN,
- streaming can be enabled/disabled quickly,
- privacy is respected (no uncontrolled recording),
- normal parking flows remain unaffected when streaming is enabled or disabled.

