Language: Français | [English](../../en/fpga/riscv-overview.md)

# Vue d’ensemble RISC-V sur FPGA (LiteX + SoC soft)

SysPark utilise un système RISC-V sur FPGA pour implémenter un nœud “exécution” déterministe, capable de piloter des actionneurs (barrières, moteurs) en sûreté tout en profitant d’un environnement Linux pour l’intégration, l’outillage et les services réseau.

L’idée : combiner
- **déterminisme matériel** pour le contrôle et l’I/O,
- **flexibilité logicielle** pour la messagerie, les logs et l’intégration.

---

## 1) Pourquoi RISC-V sur FPGA dans SysPark

### I/O bas niveau déterministes
L’actionnement (barrière open/close, séquences) bénéficie de :
- timing prévisible,
- accès direct registres memory-mapped,
- timeouts sûreté proches du hardware.

### Itération rapide sur interfaces custom
Sur FPGA, on peut ajouter/modifier :
- contrôleurs PWM/pas-à-pas,
- blocs GPIO mappés CSR,
- capteurs/encodeurs,
- watchdogs et machines d’état sûreté,
sans dépendre d’un contrôleur figé.

### Linux sans perdre le contrôle
Linux sur SoC soft permet :
- services MQTT,
- gestion payloads (chiffrement/auth),
- logs et maintenance,
- prototypage rapide.

Le FPGA reste l’endroit où l’exécution finale est contrôlée et sécurisée.

---

## 2) LiteX en une phrase

LiteX sert à générer un SoC custom sur FPGA :
- CPU RISC-V,
- interconnect bus,
- contrôleurs mémoire,
- et **registres CSR** exposant les blocs hardware au logiciel.

Dans SysPark, LiteX fait le lien entre logique HDL et services software.

---

## 3) Briques SoC soft (vue SysPark)

Un SoC FPGA SysPark typique contient :

### Sous-système CPU
- cœur RISC-V soft (type VexRiscv)
- ROM/BIOS (LiteX BIOS)
- contrôleur DDR (si DDR externe)

### Sous-système périphériques
- GPIO mappés CSR (PMOD IN/OUT)
- IP contrôle custom (séquences pas-à-pas, PWM)
- UART console
- Ethernet/MAC si utilisé
- timers + interrupts (Linux + services)

### Mémoire et stockage
- médium boot (SD / SPI selon setup)
- mémoire runtime (DDR)

---

## 4) CSR dans SysPark

CSR = Control and Status Registers :
- registres memory-mapped générés par LiteX,
- accessibles en read/write depuis le logiciel,
- utilisés pour piloter les blocs hardware.

Dans SysPark, les CSR sont l’interface actionneur :
- commandes barrières via écritures GPIO CSR,
- lecture capteurs via GPIO CSR,
- services Linux traduisent commandes MQTT → writes CSR.

Cela évite une pile driver complexe et garde un chemin de contrôle simple et transparent.

---

## 5) Séparation des responsabilités

SysPark sépare :
- **couche décision** (cloud + orchestration edge)
- **couche exécution** (FPGA + CSR)
- **couche terrain** (STM32 proche capteurs/moteurs)

Le nœud FPGA se focalise sur :
- exécution déterministe,
- limites sûreté,
- I/O fiables,
pas sur la logique métier.

---

## 6) Responsabilités typiques nœud exécution FPGA

- Abonnement au bus MQTT local (ou commandes via edge).
- Validation + traduction commandes en actions hardware.
- Pilotage sorties barrières.
- Lecture entrées capteurs + publication états.
- Timeouts et états sûrs en cas de faute ou heartbeat manquant.
- Interface software claire vers le reste du système.

---

## 7) Pourquoi RISC-V open est cohérent (philosophie projet)

RISC-V correspond bien car :
- ISA open, facile à expliquer/documenter,
- écosystème soft cores / SoC FPGA solide,
- aligné avec une démo d’ingé où la transparence compte,
- facilite l’itération pédagogique et R&D.

La valeur pratique : générer le SoC exact et exposer des surfaces de contrôle précises.

---

## 8) Critères d’acceptance nœud FPGA

Intégration correcte :
- boot stable vers Linux,
- accès CSR fiable (pas de mismatch adresses),
- contrôle actionneurs robuste sous charge MQTT,
- lecture capteurs et publication états correctes,
- recovery sûr en fautes/timeouts.

