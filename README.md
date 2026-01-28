# SysPark – Smart Parking System (Documentation Repository)

SysPark is a smart parking demonstrator built as a distributed embedded system.  
This repository is a **documentation-first** deliverable: it contains architecture, flows, integration procedures, and reference documents. Source code can be added later without changing the documentation structure.

## 1) What SysPark does

SysPark automates entry and exit flows using multiple identification and control layers:

- **Entry lane**
  - Identify a user or a vehicle (RFID and optionally license plate)
  - Trigger actuation (barrier and/or elevator mechanism in the demonstrator)
  - Create a parking session

- **Exit lane**
  - Identify the vehicle/session
  - Validate payment (cloud-driven)
  - Unlock the exit sequence
  - Close the session

SysPark is designed to remain safe and usable even when:
- the cloud is unavailable,
- vision is unavailable,
- network connectivity is degraded.

## 2) System blocks (high-level)

SysPark is split into independent blocks that communicate mainly through MQTT.

### Edge Gateway (BeagleY-AI / BeagleBone AI class)
- Local MQTT broker (system bus on the parking LAN)
- Bridge between local LAN and the cloud
- Orchestration logic (system flows, supervision)
- Remote maintenance entry point (VPN overlay recommended)
- Optional hosting of AI/Vision inference

### FPGA Execution Node (Nexys A7-100T + LiteX RISC-V + Linux)
- Deterministic actuator control via CSR (memory-mapped control registers)
- Receives commands from MQTT and publishes barrier states
- Runs Linux to host integration services while keeping a simple control plane
- Uses a structured boot chain (LiteX BIOS → OpenSBI → Linux kernel + DTB + initramfs)

### STM32 Field Nodes (STM32F746G-DISCO + Zephyr RTOS)
- Ethernet-connected nodes close to lane equipment
- Real-time threading model (RFID acquisition, UI updates, storage, motion control)
- microSD persistence for local autonomy (PINs, ACL whitelist, minimal logs)
- Entry vs Exit roles supported depending on the lane

### AI / Vision (optional)
- License plate recognition pipeline at the edge
- Confidence-aware publishing to MQTT
- Never blocks the lane: always has fallback identifiers

### Power and Hardware
- Battery pack + BMS for protection and balancing
- DC-DC conversion (12 V class rail to stable 5 V distribution)
- Wiring topology designed for demo robustness (noise isolation, labeling, safety)

## 3) Repository structure

This repo is organized as a documentation system.

- `README.md`  
  Global overview (this file)

- `README.fr.md`  
  French version of the global overview

- `docs/en/`  
  English documentation by subsystem

- `docs/fr/`  
  French documentation by subsystem (mirrors `docs/en/`)

- `references/pdf/`  
  Reference PDFs used for the project (presentation, BMS, datasheets)

- `assets/`  
  Images, diagrams, exports (architecture visuals, screenshots, figures)

- `CHANGELOG.md`  
  Documentation evolution history

- `LICENSE`  
  Repository license

### Documentation sections
Inside `docs/*/` you will find:
- `overview/` : architecture, requirements, system flows, security, testing, deployment
- `edge/` : gateway role, MQTT bridge, remote access, LED banner integration
- `fpga/` : RISC-V on FPGA, boot chain, CSR control, networking
- `stm32/` : node overview, RTOS threads, Ethernet, storage microSD
- `cloud/` : cloud overview, payments, MQTT topic taxonomy
- `ai-vision/` : pipeline, streaming, models, validation
- `hw/` : high-level BOM, power and BMS, wiring topology

## 4) Where to add source code (when you are ready)

This repo already has a clean separation for future code.  
Add code under a dedicated `src/` tree, keeping documentation untouched.

Recommended layout:

- `src/edge/`  
  Gateway services (MQTT broker configuration, bridge, orchestration, dashboards, APIs)

- `src/fpga/`  
  FPGA-related work split into:
  - `src/fpga/hw/` : HDL / LiteX SoC generation, CSR peripherals, bitstreams
  - `src/fpga/sw/` : Linux-side services and utilities on the FPGA node
  - `src/fpga/fw/` : boot artifacts generation (OpenSBI packaging, images if needed)

- `src/stm32/`  
  Zephyr projects, board configs, app logic per node (entry/exit)

- `src/cloud/`  
  Backend services (sessions, billing, auth, dashboards)

- `src/ai-vision/`  
  Vision inference pipeline, model packaging, evaluation utilities

Also recommended:
- `scripts/` : build and deployment scripts (flash, image generation, provisioning)
- `configs/` : MQTT topics allowlists, network IP maps, service configs
- `tests/` : non-hardware unit tests, integration tests, validation tools

## 5) How to keep documentation and code consistent

- Keep docs in `docs/en` and `docs/fr` as the authoritative reference.
- For each subsystem, match doc pages to the code folders:
  - `docs/en/fpga/*` ↔ `src/fpga/*`
  - `docs/en/stm32/*` ↔ `src/stm32/*`
  - etc.
- Avoid duplicating the same information in multiple places.
- Put design rationales and integration rules in docs, not in code comments.

## 6) Getting started (documentation navigation)

Start here:
- `docs/en/overview/architecture.md`
- `docs/en/overview/system-flows.md`
- `docs/en/overview/deployment.md`
- `docs/en/overview/testing.md`

Then read per subsystem:
- `docs/en/edge/beagley-ai.md`
- `docs/en/fpga/riscv-overview.md`
- `docs/en/stm32/stm32-overview.md`
- `docs/en/hw/power-bms.md`

French equivalents are mirrored under `docs/fr/`.

## 7) Reference documents

- Presentation: `references/pdf/SysPark_Présentation.pdf`
- Power and BMS reference: `references/pdf/BMS.pdf`

