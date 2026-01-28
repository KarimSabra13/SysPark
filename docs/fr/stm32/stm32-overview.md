Language: Français | [English](../../en/stm32/stm32-overview.md)

# Vue d’ensemble du sous-système STM32 (STM32F746G-DISCO + Zephyr RTOS)

Dans SysPark, le sous-système STM32 est le **nœud terrain** au plus près des équipements physiques de voie. Il exécute les tâches déterministes et orientées sûreté (pilotage moteur, fins de course, RFID, interface locale) et synchronise son état avec la passerelle Edge (BeagleY-AI) via **Ethernet + MQTT**.

SysPark sépare volontairement les responsabilités :
- **la passerelle décide** (orchestration, vision, politiques, bridge cloud),
- **le STM32 exécute localement** (contrôle I/O, temps réel, UI),
- **les mécanismes sûreté restent locaux** (comportement fiable en défaut).

---

## 1) Rôle dans l’architecture SysPark

### Contrôle terrain temps réel
Le STM32 gère la logique “proche matériel” :
- pilotage d’un moteur pas-à-pas via une interface driver de type STEP/DIR (et configuration si besoin),
- homing et limites mécaniques via fin de course,
- lecture badge RFID pour identification locale,
- mise à jour d’un affichage local,
- persistance locale des paramètres critiques (PIN, whitelist).

### Synchronisation réseau
Le STM32 publie des événements et reçoit des commandes approuvées via MQTT sur Ethernet :
- publication UID RFID et états capteurs/actionneurs,
- réception de certaines décisions (dont la validation de paiement en mode sortie),
- fonctionnement local prioritaire même en mode cloud dégradé.

---

## 2) Pourquoi Zephyr RTOS

Trois raisons principales :

### Déterminisme
Les interactions terrain demandent une latence maîtrisée :
- cadence moteur et séquences,
- lecture fin de course,
- rafraîchissement UI sans bloquer le critique.

### Réseau embarqué mature
Zephyr propose une pile réseau structurée (Ethernet + IPv4 + patterns MQTT) adaptée à microcontrôleur avec compromis explicites RAM/CPU.

### Reproductibilité
Modèle de configuration et d’intégration cohérent :
- configuration homogène,
- description matériel découplée,
- intégration reproductible en dev et en démo.

---

## 3) Plateforme matérielle : STM32F746G-DISCO

Choisie car :
- Cortex-M7 performant pour combiner I/O + réseau,
- ST-LINK intégré (flash/debug),
- headers pratiques pour driver moteur, RFID, écrans, capteurs,
- Ethernet compatible avec Zephyr (PHY RMII couramment utilisé sur cette carte).

---

## 4) Interfaces et périphériques (configuration SysPark)

SysPark cible un ensemble clair de périphériques :

### Moteur et sûreté I/O
- interface driver moteur (STEP/DIR) + canal de configuration si nécessaire
- fin de course pour homing et limites sûreté
- comportement en état sûr en cas d’anomalie ou de commande incohérente

### Identification (RFID)
- lecteur RFID pour récupérer l’UID badge
- normalisation de l’UID et publication sur le bus système pour décision d’accès

### Interfaces locales
- LCD 20×4 pour messages opérationnels (statut, informations contextualisées)
- OLED pour suivi ascenseur/mouvement (étage, direction, homing)

### Stockage (microSD)
La microSD sert à persister des éléments clés :
- PIN entrée et PIN sortie (si ces modes sont activés),
- liste whitelist des badges autorisés,
- logs terrain optionnels, structurés, à faible fréquence d’écriture.

---

## 5) Modèle réseau (Ethernet, IP statique, MQTT)

### Ethernet
- Le STM32 est un nœud LAN et dialogue avec la passerelle.
- L’adressage IPv4 statique simplifie les intégrations et les démos.

### Intentions MQTT
Le STM32 agit comme client MQTT :
- publie les événements locaux (RFID, états barrière/ascenseur, fin de course),
- consomme certaines décisions issues de l’orchestration.

Une taxonomie de topics strictement partagée avec BeagleY-AI est nécessaire pour éviter les désalignements et garder l’allowlist du bridge minimale.

---

## 6) Modes d’exécution : rôle entrée vs rôle sortie

SysPark peut assigner un **rôle de voie** au STM32 :

### Rôle entrée (avec ascenseur/mouvement)
- homing au démarrage,
- séquences de mouvement déterministes,
- publication régulière de l’état ascenseur pour supervision et UI.

### Rôle sortie (sortie conditionnée au paiement)
- priorité à l’identification + UI + autorisation sortie,
- attente d’un événement “paiement validé” avant de progresser,
- sûreté locale indépendante de la disponibilité cloud.

---

## 7) Modèle de concurrence (threads et synchronisation)

L’application est organisée en modules à priorités distinctes :
- communication et routage MQTT
- acquisition RFID
- rendu UI (LCD et OLED)
- pilotage mouvement (uniquement rôle entrée)
- routage UI paiement (rôle sortie)

Synchronisation via :
- files de messages pour UID et événements paiement,
- mécanisme type sémaphore pour débloquer l’UI après confirmation paiement,
- verrou pour protéger l’accès microSD en concurrence.

Objectif :
- éviter le blocage dans les chemins critiques,
- isoler réseau/UI/logging du timing moteur.

---

## 8) Logs terrain et principes de robustesse

Pour rester fiable :
- écriture logs contrôlée (buffer + flush périodique),
- structures mémoire stables pour éviter comportements indésirables,
- dimensionnement des piles traité comme contrainte centrale,
- validation réseau sur sous-réseaux isolés pour éviter conflits routeur/lab.

Un flow Ethernet de test a été utilisé pour valider :
- réception réseau,
- affichage UART,
- stockage microSD robuste (rotation, sync périodique).

---

## 9) Extension audio (optionnelle)

Une piste audio a été explorée pour des prompts autour de l’ascenseur :
- solution externe text-to-speech pilotée par le STM32,
- étude de la chaîne audio intégrée (SAI/I2S codec).

Cette brique est optionnelle et a surtout servi à évaluer la faisabilité et le coût d’intégration sous Zephyr.

---

## 10) Attendus d’intégration (critères de bon fonctionnement)

Une intégration STM32 correcte doit fournir :
- homing et contrôle mouvement prévisibles et sûrs,
- reporting UID RFID fiable,
- UI cohérente avec les états de voie,
- connectivité Ethernet stable et échanges MQTT corrects,
- comportement robuste en modes dégradés (cloud/broker indisponibles),
- persistance traçable (PIN/whitelist) et usure SD minimisée.

