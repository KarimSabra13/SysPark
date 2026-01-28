# SysPark – Système de parking intelligent (dépôt documentation)

SysPark est un démonstrateur de parking intelligent construit comme un système embarqué distribué.  
Ce dépôt est **documentation-first** : il contient l’architecture, les flows, les procédures d’intégration, et les références. Le code source pourra être ajouté plus tard sans casser la structure.

## 1) Ce que fait SysPark

SysPark automatise les flows d’entrée et de sortie via plusieurs couches d’identification et de contrôle :

- **Voie entrée**
  - Identifier un utilisateur ou un véhicule (RFID et éventuellement lecture plaque)
  - Déclencher l’actionnement (barrière et/ou mécanisme ascenseur sur la maquette)
  - Créer une session de parking

- **Voie sortie**
  - Identifier le véhicule/la session
  - Valider le paiement (piloté côté cloud)
  - Débloquer la séquence de sortie
  - Clôturer la session

SysPark est conçu pour rester sûr et utilisable même si :
- le cloud est indisponible,
- la vision est indisponible,
- le réseau est dégradé.

## 2) Blocs système (haut niveau)

SysPark est découpé en blocs indépendants, intégrés principalement via MQTT.

### Passerelle Edge (BeagleY-AI / classe BeagleBone AI)
- Broker MQTT local (bus système sur le LAN parking)
- Bridge entre LAN local et cloud
- Orchestration (flows, supervision)
- Point d’entrée maintenance (VPN overlay recommandé)
- Hébergement optionnel du module IA/Vision

### Nœud exécution FPGA (Nexys A7-100T + LiteX RISC-V + Linux)
- Contrôle actionneurs déterministe via CSR (registres memory-mapped)
- Réception commandes MQTT et publication états barrières
- Linux pour services d’intégration tout en gardant un plan de contrôle simple
- Chaîne de boot structurée (LiteX BIOS → OpenSBI → Linux kernel + DTB + initramfs)

### Nœuds terrain STM32 (STM32F746G-DISCO + Zephyr RTOS)
- Nœuds Ethernet proches des équipements
- Modèle multi-threads déterministe (RFID, UI, stockage, contrôle mouvement)
- Persistance microSD pour autonomie locale (PIN, ACL whitelist, logs minimaux)
- Rôles entrée/sortie selon la voie

### IA / Vision (optionnel)
- Pipeline lecture plaque au niveau edge
- Publication MQTT avec score de confiance
- Ne bloque jamais la voie : fallbacks systématiques

### Matériel et puissance
- Batterie + BMS (protection et équilibrage)
- Conversion DC-DC (rail classe 12 V vers distribution 5 V stable)
- Topologie de câblage orientée robustesse démo (bruit, étiquetage, sûreté)

## 3) Structure du dépôt

Ce dépôt est organisé comme un système documentaire.

- `README.md`  
  Vue globale en anglais

- `README.fr.md`  
  Vue globale en français (ce fichier)

- `docs/en/`  
  Documentation en anglais par sous-système

- `docs/fr/`  
  Documentation en français (miroir de `docs/en/`)

- `references/pdf/`  
  PDFs de référence (présentation, BMS, datasheets)

- `assets/`  
  Images, schémas, exports (architecture, captures, figures)

- `CHANGELOG.md`  
  Historique des évolutions documentation

- `LICENSE`  
  Licence du dépôt

### Sections documentation
Dans `docs/*/` :
- `overview/` : architecture, exigences, flows, sécurité, tests, déploiement
- `edge/` : passerelle, bridge MQTT, accès distant, bandeau LED
- `fpga/` : RISC-V sur FPGA, boot chain, CSR, réseau
- `stm32/` : vue nœuds, threads RTOS, Ethernet, microSD
- `cloud/` : cloud overview, paiement, taxonomie topics MQTT
- `ai-vision/` : pipeline, streaming, modèles, validation
- `hw/` : BOM haut niveau, puissance/BMS, topologie câblage


## 6) Lecture recommandée (navigation)

Commencer par :
- `docs/fr/overview/architecture.md`
- `docs/fr/overview/system-flows.md`
- `docs/fr/overview/deployment.md`
- `docs/fr/overview/testing.md`

Puis par sous-système :
- `docs/fr/edge/beagley-ai.md`
- `docs/fr/fpga/riscv-overview.md`
- `docs/fr/stm32/stm32-overview.md`
- `docs/fr/hw/power-bms.md`

Les versions anglaises sont dans `docs/en/`.

## 7) Documents de référence

- Présentation : `references/pdf/SysPark_Présentation.pdf`
- Puissance et BMS : `references/pdf/BMS.pdf`

