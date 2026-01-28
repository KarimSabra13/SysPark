Language: Français | [English](../../en/fpga/csr-control.md)

# Contrôle CSR et interface actionnement (nœud FPGA)

Sur le nœud FPGA SysPark, le logiciel pilote les actionneurs via les **registres CSR** LiteX (Control and Status Registers). Cela crée une chaîne de contrôle simple et transparente :
- décisions via MQTT vers des services Linux,
- traduction en lectures/écritures CSR,
- CSR pilote les périphériques FPGA (GPIO PMOD, contrôle pas-à-pas, sûreté),
- lecture d’état via le même mécanisme.

Ce document décrit les surfaces de contrôle, règles d’intégration et attentes sûreté sans mention de code.

---

## 1) Ce que les CSR apportent dans SysPark

Les CSR sont une interface memory-mapped :
- expose des blocs FPGA sous forme de registres,
- latence déterministe comparée à une pile driver lourde,
- mapping clair “intention” → “action matérielle”.

SysPark utilise CSR pour :
- piloter sorties vers drivers moteurs (barrières),
- échantillonner entrées capteurs,
- exporter des flags d’état au logiciel.

---

## 2) Surfaces de contrôle

Le nœud FPGA expose typiquement :

### 2.1 Sorties (actionneurs)
- commandes ouverture/fermeture sous forme de patterns sorties.
- sorties séquences pas-à-pas (direct ou via driver externe).
- optionnel : PWM pour servo ou signalisation.

### 2.2 Entrées (capteurs)
- capteurs présence voie,
- fins de course barrière “ouverte/fermée”,
- entrées faute (ex : overcurrent driver).

### 2.3 Statut système
- alive/heartbeat,
- flags watchdog,
- timestamp dernière commande (optionnel),
- état faute sûreté.

---

## 3) Concept mapping PMOD

Les PMOD servent d’interface I/O physique simple :
- un PMOD pour sorties,
- un PMOD pour entrées.

La map CSR inclut :
- registre(s) pilotant les pins PMOD OUT,
- registre(s) lisant les pins PMOD IN.

Comme le câblage PMOD est sensible, la doc doit toujours préciser :
- quel connecteur (JB/JC/JD),
- direction (IN/OUT),
- ordre des bits/pins attendus.

---

## 4) Modèle commande (MQTT → CSR)

Chaîne explicite SysPark :

1. Commande validée reçue (souvent MQTT).
2. Le service vérifie :
   - type commande autorisé,
   - rôle voie correct,
   - rate limiting,
   - état système compatible.
3. Écritures CSR :
   - démarrer mouvement,
   - séquencer si nécessaire,
   - surveiller entrées pour arrêt sûr.
4. Publication statut :
   - accept/reject,
   - état actionneur (moving/open/closed),
   - faute éventuelle.

But : actionnement prévisible et traçable.

---

## 5) Règles sûreté (indispensables)

### 5.1 Timeouts
Tout mouvement a une durée max :
- feedback capteur absent,
- ou pas de progression détectée,
→ arrêt + état faute sûr.

### 5.2 Gating état
Interdire :
- commandes conflictuelles,
- toggles direction rapides,
- mouvement en état faute.

### 5.3 Idempotence
Un “open” répété ne doit pas relancer une séquence risquée si déjà ouvert.

### 5.4 Défauts sûrs en perte contrôle
Si le service contrôle ou MQTT tombe :
- sorties reviennent à l’état sûr,
- watchdog peut forcer l’arrêt.

### 5.5 Reporting faute clair
Causes visibles via MQTT/console :
- timeout,
- incohérence capteurs,
- commande invalide.

---

## 6) Checks intégration

### Map CSR correcte
- base adresses correctes.
- mismatch = rien ne bouge ou mauvais pins.

### Validation câblage PMOD
- test toggle sorties,
- test lecture entrées.

### Actionnement end-to-end
- commande MQTT → CSR → mouvement → capteur → publish état.

### Mode dégradé
- perte MQTT → safe,
- capteur KO → timeout safe stop.

---

## 7) Attendus documentation

Une doc CSR complète inclut :
- table map registres haut niveau (rôle, pas code),
- mapping pins par PMOD,
- séquences actionneurs sous forme de diagrammes d’état,
- contraintes sûreté,
- tests d’acceptance.

