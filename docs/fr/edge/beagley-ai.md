Language: Français | [English](../../en/edge/beagley-ai.md)

# Passerelle Edge (BeagleY-AI) — Vue d’ensemble

La passerelle Edge est le “connecteur” central sur site. Elle vit dans le LAN du parking et relie les sous-systèmes physiques (nœuds STM32 terrain et nœud FPGA d’exécution) aux services cloud. Son rôle est d’orchestrer les flows, fusionner les sources (capteurs + vision + politiques), et maintenir un fonctionnement local même si l’accès Internet est instable.

Trois règles :
- **Local-first** : le parking doit fonctionner en mode LAN.
- **Cloud-enhanced** : le cloud apporte dashboard, paiement, historique, supervision.
- **La sûreté ne dépend jamais du cloud** : l’exécution temps réel et les états sûrs restent côté exécution.

---

## 1) Responsabilités

### 1.1 Hub de plan de contrôle
- Réception événements terrain : présence, identifiants RFID, états actionneurs, alarmes.
- Publication décisions et messages usagers : guidage, état voie.
- Frontière stable entre sous-systèmes locaux et cloud.

### 1.2 Fusion et support décision
- Combine :
  - “qui” (RFID / PIN / plaque),
  - “où” (entrée/sortie),
  - “ce qui se passe” (présence, état barrière),
  - “ce qui est autorisé” (politique + ACL, online ou cache),
  pour déclencher le bon flow (entrée, sortie, override).

### 1.3 Supervision et maintenance
- Accès distant sécurisé sans ouverture de ports entrants sur la box du site.
- Visibilité état système : santé, heartbeats, readiness.

### 1.4 IA / Vision (optionnel)
- Exécute sur site le pipeline de lecture plaque.
- Publie plaque + confiance sur MQTT pour rattachement session et décisions.

---

## 2) Broker MQTT local et architecture hybride

MQTT est le bus interne SysPark.
La passerelle héberge (ou supervise) le **broker local** afin que le parking reste opérationnel même en cas de coupure Internet.

### Rôle du broker local
- Diffusion événements faible latence sur le LAN.
- Découplage producteurs (STM32, FPGA, capteurs) / consommateurs (passerelle, affichage, bridge).
- Mode “island” autonome.

### Rôle du bridge (local ↔ broker public)
Un bridge sélectif relaie uniquement les topics whitelistés entre :
- broker local (LAN),
- broker public (relais vers le cloud).

Intentions :
- éviter les boucles,
- n’exposer que le nécessaire,
- garder le trafic interne privé.

---

## 3) Interfaces vers les sous-systèmes

### 3.1 Nœuds STM32 (entrée et sortie)
Interaction via MQTT pour :
- recevoir événements d’identification (RFID, statut PIN),
- recevoir états ascenseur/actionneurs (côté entrée),
- recevoir readiness sortie (côté sortie),
- envoyer commandes/config uniquement quand requis et autorisés.

Les STM32 gardent la responsabilité des interactions terrain déterministes (tâches RTOS, I/O locales).

### 3.2 Nœud FPGA d’exécution (actionnement déterministe)
La passerelle échange commandes et états avec le FPGA :
- exécution déterministe séquences barrière/actionneurs,
- sûreté via timeouts/watchdogs,
- retour d’état continu.

La passerelle :
- demande actions,
- met à jour l’affichage et la traçabilité selon résultats.

### 3.3 Backend cloud
Connexion au cloud via broker public :
- upload télémétrie/événements,
- réception décisions (paiement validé, commandes opérateur, configs),
- disponibilité des fonctions “cloud-enhanced” quand Internet est présent.

---

## 4) Affichage local usager

Un affichage local fournit un retour immédiat :
- “Bienvenue”
- “Identifiez-vous”
- “Passez”
- “Paiement requis”
- “Patientez”
- “Erreur, contactez opérateur”

Intentions :
- feedback opérationnel en local (mode LAN),
- pilotage via MQTT pour permettre un contrôle depuis edge ou cloud.

---

## 5) Vision et fonctions caméra (module optionnel)

### 5.1 Pipeline vision (lecture plaque)
Pipeline typique :
- capture frames,
- détection plaque,
- OCR,
- normalisation + validation format,
- publication résultat + confiance.

Usages :
- entrée : facteur complémentaire ou pré-identification
- sortie : rattachement session et support calcul tarif

Comportement en échec :
- ne pas bloquer la voie,
- fallback RFID/PIN/opérateur.

### 5.2 Caméra motorisée (pan/tilt)
Si présent, la passerelle relaie des commandes de positionnement :
- réglages maintenance,
- points de vue prédéfinis par voie.

---

## 6) Supervision distante sécurisée (sans ports ouverts)

SysPark évite l’exposition directe du LAN au public.
La supervision se fait via tunnel sécurisé (VPN overlay / exposition contrôlée).

Objectifs :
- pas de configuration routeur nécessaire,
- accès activable/désactivable explicitement,
- debug/flux accessibles en sécurité.

---

## 7) Fiabilité et exploitation

La passerelle fonctionne comme un ensemble de services supervisés :
- disponibilité broker local,
- disponibilité bridge,
- service affichage,
- service vision (si activé),
- monitoring/heartbeats.

Attentes :
- redémarrage automatique,
- logs clairs,
- ordre de démarrage prévisible (réseau → broker → bridge → applications).

---

## 8) Baseline sécurité

Baseline réaliste :
- broker local non accessible depuis Internet,
- TLS côté broker public,
- allowlists strictes dans le bridge,
- mises à jour sensibles avec règles d’auth (secret, admin),
- overrides opérateur traçables.

---

## 9) Modes défaillance (côté passerelle)

### Coupure Internet
- broker local OK,
- flows locaux OK via cache,
- supervision/paiement cloud dégradés.

### Panne broker public
- site continue localement,
- cloud ne reçoit plus jusqu’au retour broker.

### Panne vision
- aucune voie bloquée ; fallback RFID/PIN.

### Panne broker local
- mode restreint contrôlé jusqu’au retour broker (ou fallback défini si implémenté).

