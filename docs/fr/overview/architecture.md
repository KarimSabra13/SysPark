Language: Français | [English](../../en/overview/architecture.md)

# Architecture système SysPark

SysPark est un système de parking intelligent conçu comme une solution complète, modulaire et orientée déploiement, plutôt que comme un simple assemblage de capteurs. L’architecture est volontairement distribuée, organisée en couches de responsabilités bien séparées, toutes interconnectées via Ethernet. Cette séparation permet de faire évoluer la logique métier sans fragiliser l’exécution temps réel et la sûreté des actions physiques.

## 1. Principe d’architecture : séparer les rôles, stabiliser les interfaces

SysPark repose sur trois niveaux complémentaires :

- **Niveau décision + supervision (Passerelle Edge)**  
  Un nœud de type BeagleY-AI sert de point d’intégration pour la logique haut niveau, la connectivité cloud, la vision, la supervision à distance et les services opérateur.

- **Niveau exécution temps réel (SoC sur FPGA)**  
  Un FPGA de type Nexys A7 avec un SoC LiteX assure l’exécution déterministe des commandes terrain et l’application des mécanismes de sûreté (timeouts, watchdogs, états sûrs). Il exécute de manière fiable, mais ne porte pas la décision métier complexe.

- **Niveau interface terrain (Nœud microcontrôleur)**  
  Un STM32F746G-DISCO sous RTOS gère les interactions locales au plus près des équipements : lecture RFID, séquencement ascenseur/actionneurs, affichage local, acquisition capteurs, avec une structure multi-tâches robuste.

Un bloc transverse supporte l’ensemble :

- **Énergie + continuité (Bus 12 V + conversion DC/DC + batterie + BMS)**  
  Un bus 12 V DC central simplifie la distribution, alimente les charges hétérogènes, et une batterie avec BMS garantit la continuité de service et la sûreté énergétique, afin d’atteindre un état sûr en cas de dégradation d’alimentation.

Règle d’architecture constante :

- **La passerelle décide (logique métier).**
- **Le FPGA exécute (temps réel + sûreté).**
- **La STM32 interfâce le terrain (I/O locales + tâches RTOS).**

## 2. Topologie système

### 2.1 Interconnexion réseau

Tous les modules communiquent via Ethernet, ce qui standardise l’intégration et limite le câblage point à point. En environnement de test, des adresses IPv4 statiques sont souvent utilisées pour la reproductibilité (valeurs indicatives, adaptables par site) :

- FPGA : `192.168.10.4/24`
- Passerelle : `192.168.10.5/24`
- STM32 : `192.168.10.7/24`

Ethernet sert à :

- transporter commandes, états et événements,
- échanger les statuts actionneurs/sécurités vers la passerelle,
- véhiculer les messages MQTT entre sous-systèmes (broker local et pont éventuel).

### 2.2 Distribution d’énergie et continuité

SysPark structure la puissance autour de :

- **12 V : rail principal** (puissance),
- **5 V : rail logique** (dérivé du 12 V par conversion DC/DC),
- une **batterie de secours** dimensionnée pour les pics et une autonomie de mise en sécurité,
- un **BMS** pour protection, mesure, équilibrage et supervision.

L’objectif n’est pas de remplacer durablement le secteur, mais de **maintenir le contrôle suffisamment longtemps pour terminer un cycle, sécuriser les actionneurs, puis basculer en état sûr**.

## 3. Colonne vertébrale de communication : MQTT hybride

MQTT est utilisé comme “bus système” pour les événements, commandes, télémétries et messages opérateur.

### 3.1 Intérêt du mode hybride (local + cloud)

L’architecture combine :

- **Un broker MQTT local** (sur le LAN du parking) :  
  latence faible, fonctionnement autonome même si l’accès Internet est instable, et contrôle mieux isolé.

- **Un relais public + un serveur cloud** :  
  supervision à distance, règles centralisées, tableaux de bord, paiements et administration.

Un **pont sélectif** synchronise uniquement les topics nécessaires entre local et cloud. Une politique de type whitelist évite les boucles et limite la surface exposée.

### 3.2 Taxonomie des topics (vue conceptuelle)

Les topics sont hiérarchiques sous une racine (ex : `parking/…`) pour rester extensibles. Familles usuelles :

- `parking/sensor_*` : présence, heartbeat, erreurs
- `parking/gate/*` : état barrière, fins de course, commandes
- `parking/display/*` : messages usagers (bandeau LED, IHM)
- `parking/camera/*` : commandes de positionnement et sorties vision
- `parking/config/*` : configuration contrôlée
- `parking/meteo` : contexte (optionnel)

Le QoS est choisi selon criticité :

- QoS 0 : télémetries non critiques,
- QoS 1 : commandes “au moins une fois”,
- QoS 2 : événements/configurations critiques si besoin d’exactement-une-fois.

## 4. Passerelle Edge (BeagleY-AI) : décision, fusion, supervision

La passerelle est le point d’intégration du système :

### 4.1 Moteur de décision et orchestration

Elle fusionne :

- événements terrain (RFID, capteurs, états actionneurs),
- sorties vision (lecture plaque, confiance, captures),
- règles et décisions issues du cloud (politiques, overrides opérateur).

Elle orchestre ensuite :

- guidage usager (messages d’affichage),
- demandes de séquences (barrières/ascenseur) vers les nœuds d’exécution,
- notifications et traçabilité.

### 4.2 Information locale et supervision à distance

Deux fonctions opérateur sont clés :

- **Affichage local** : un bandeau LED piloté localement fournit un retour immédiat (“places disponibles”, “bienvenue”, “complet”, etc.). Il est mis à jour en temps réel via abonnement MQTT.

- **Supervision à distance** : un accès distant sécurisé permet d’ouvrir un flux vidéo de debug sans ouvrir de ports entrants sur la box du site. Cela facilite maintenance, debug et déploiement.

## 5. Contrôleur terrain (STM32 + RTOS) : exécution locale et I/O déterministes

La STM32 est le nœud “au plus près” des équipements. Elle regroupe les entrées/sorties terrain et s’appuie sur une architecture RTOS multi-tâches pour garantir un comportement prévisible et maintenable.

### 5.1 Responsabilités principales

- **Contrôle d’accès RFID** : lecture badges et émission d’événements d’identification.
- **Commande actionneurs (ascenseur, moteurs, etc.)** : profils de mouvement avec accélération/décélération, et calibration (homing) au démarrage.
- **Interface locale** : affichages et retours utilisateur immédiats.
- **Acquisition capteurs** : température/pression et signaux de sûreté.
- **Synchronisation réseau** : publication d’états et réception de commandes via Ethernet/MQTT.

### 5.2 Intention de conception

La STM32 ne porte pas la logique métier complexe. Elle fournit :

- un socle terrain déterministe,
- un découpage clair des tâches (acquisition / affichage / communication),
- une robustesse temporelle adaptée aux contraintes réelles.

## 6. SoC FPGA (Nexys A7 + LiteX + RISC-V Linux) : déterminisme et sûreté d’exécution

Le FPGA garantit :

- **des temps d’exécution maîtrisés**, indépendants de la gigue OS,
- **des mécanismes de sûreté** (watchdogs, timeouts, états sûrs),
- **une exécution fiable** des commandes reçues.

### 6.1 Organisation conceptuelle

- Le SoC LiteX sépare :
  - la logique matérielle (fonctions strictement temps réel),
  - une couche de supervision légère (CPU RISC-V sous Linux) utile pour coordination et réseau.

- Le contrôle est exposé via une interface stable de type registres mémoire-mappés, offrant des commandes explicites et des retours d’état clairs.

### 6.2 Flux d’intégration

Le FPGA échange avec la passerelle via Ethernet :

- **réception de commandes** à exécuter,
- **retour continu d’état** (statuts, positions, alarmes),
- **passage en état sûr** lors de détection d’anomalies.

## 7. Sûreté et gestion d’urgence

La sûreté est traitée à plusieurs niveaux :

- **Sécurité locale** : capteurs de présence autour des barrières et séquences de mouvement contrôlées.
- **Sûreté d’exécution (FPGA)** : watchdogs/timeouts et états sûrs en cas d’incohérence.
- **Sûreté énergétique (BMS)** : protection cellules et respect de la zone de fonctionnement sûre.
- **Indépendance du canal d’urgence** : un mécanisme d’alerte incendie est pensé via un canal radio indépendant du réseau IP principal, afin de garantir la réception de l’alerte même en cas de panne réseau.

## 8. Énergie : BMS, dimensionnement batterie, conversion DC/DC

La conception énergie est dictée par des charges hétérogènes et des pics transitoires :

- un budget global de puissance de l’ordre de quelques dizaines de watts, avec des pics liés aux moteurs/servos,
- une batterie 12 V / 6 Ah dimensionnée pour tenir les pics et laisser le temps d’atteindre un état sûr,
- un BMS assurant :
  - mesure tension cellule, courant et température,
  - protection surcharge/sous-tension/surintensité (isolation par MOSFETs),
  - équilibrage passif,
  - estimation SOC/SOH exploitable en supervision.

La démarche a été pragmatique : exploration d’un BMS custom pour valider l’architecture, puis choix d’une solution commerciale intégrée pour sécuriser fiabilité et planning.

## 9. Modularité et évolutions

SysPark est conçu pour évoluer :

- du petit parking au multi-sites,
- en multipliant entrées/sorties,
- en renforçant sécurité et vision,
- en ajoutant capteurs, diagnostics et outils maintenance.

Grâce à la séparation des rôles et à des interfaces stables (Ethernet + MQTT + frontières commande/état), les nouvelles fonctionnalités peuvent être ajoutées sans déstabiliser le cœur d’exécution temps réel.
