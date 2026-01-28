Language: Français | [English](../../en/hw/bom-highlevel.md)

# BOM matériel (haut niveau)

Ce document résume le matériel SysPark par blocs. Il sert à l’intégration, au câblage et à la préparation déploiement. Il ne remplace pas les datasheets.

SysPark repose sur une séparation claire :
- passerelle edge pour orchestration et bridge cloud
- nœud exécution FPGA pour contrôle actionneurs déterministe
- nœuds STM32 terrain pour temps réel proche équipements
- vision optionnelle pour lecture plaque
- sous-système puissance dimensionné pour moteurs et compute

---

## 1) Calcul et contrôle

### Passerelle edge
- BeagleBone AI / BeagleY-AI (classe passerelle edge)
- Rôles
  - broker MQTT local
  - bridge vers le cloud
  - machine d’états d’orchestration
  - accès maintenance
  - hôte vision optionnel

### Nœud exécution FPGA
- Digilent Nexys A7-100T
- Rôles
  - SoC soft LiteX RISC-V
  - Linux pour services
  - I/O CSR pour actionnement
  - surface de contrôle déterministe pour barrières

### Nœuds STM32
- STM32F746G-DISCO
- Rôles typiques
  - entrée : mécanisme ascenseur, UI, RFID
  - sortie : UI paiement, RFID, télémétrie réseau
- RTOS
  - Zephyr RTOS pour multi-threads déterministes et Ethernet

---

## 2) Actionnement

### Barrières
- mécanismes barrière entrée et sortie
- chaîne démo
  - sorties PMOD FPGA
  - étage driver (type ULN2003)
  - moteurs pas-à-pas (classe 28BYJ-48) ou équivalent

### Ascenseur ou lift (si utilisé)
- mécanisme motorisé pour la maquette
- piloté par STM32 en temps réel
- nécessite
  - driver moteur adapté
  - fin de course homing
  - butées mécaniques

---

## 3) Identification et interfaces

### Identification
- lecteur badge RFID sur STM32
- vision lecture plaque optionnelle
  - caméra par voie ou caméra partagée selon layout

### Feedback local
- LCD 20x4 sur STM32 pour prompts et statut
- OLED pour statut ascenseur ou debug
- bandeau LED pour messages conducteur

---

## 4) Réseau et interconnexions

### Ethernet (préféré)
- passerelle, FPGA, STM32 connectés sur un LAN privé
- switch ou routeur en mode bridge

### I/O physiques
- faisceaux PMOD FPGA vers drivers et capteurs
- capteurs vers GPIO STM32 selon besoin

---

## 5) Puissance (haut niveau)

Architecture puissance DC centralisée :
- rail batterie (classe 12 V en démo)
- conversion DC-DC vers 5 V pour compute et périphériques
- régulation locale vers 3.3 V si nécessaire

Blocs clés
- pack batterie
- BMS protection et équilibrage
- fusible principal et protection câbles
- DC-DC 12 V vers 5 V fort courant
- rails secondaires optionnels selon actionneurs

---

## 6) Consommables à prévoir pour les démos

Les démos tombent souvent sur des détails. Garder en spare :
- câbles Ethernet, petit switch
- jumpers PMOD et headers
- drivers moteurs et moteurs de rechange
- lecteur RFID de rechange
- fusibles, connecteurs, colliers
- cartes SD pour le nœud Linux FPGA

---

## 7) Références

- Présentation : references/pdf/SysPark_Présentation.pdf
- Puissance et BMS : references/pdf/BMS.pdf

