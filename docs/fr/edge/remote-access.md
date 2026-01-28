Language: Français | [English](../../en/edge/remote-access.md)

# Accès distant sécurisé et debug streaming

SysPark est conçu pour être maintenable sans exposer le LAN du parking à Internet. L’accès distant est une capacité d’exploitation, pas une porte ouverte permanente. Principe : **pas de ports entrants**, accès contrôlé et traçabilité claire.

Ce document décrit le modèle d’accès distant utilisé dans SysPark et comment il supporte :
- des sessions maintenance sécurisées,
- du debug à distance,
- un flux vidéo/debug optionnel.

---

## 1) Objectifs et non-objectifs

### Objectifs
- Maintenance à distance sans configuration routeur.
- Éviter l’exposition directe de services locaux (broker MQTT, SSH, caméra).
- Support “à la demande”, y compris visualisation debug.
- Déploiement réaliste (site derrière NAT).

### Non-objectifs
- L’accès distant ne remplace pas la sûreté locale.
- L’accès distant ne doit pas être requis pour le fonctionnement normal.
- L’accès distant ne doit pas contourner le modèle allowlist du bridge.

---

## 2) Modèle de menace (contre quoi on se protège)

- Clients internet non fiables tentant d’atteindre le LAN.
- Exposition accidentelle de services (MQTT, SSH, streams).
- Fuite d’identifiants entraînant un accès non contrôlé.
- Actions à distance pouvant impacter le système physique.

---

## 3) Approche recommandée : VPN overlay (ex : Tailscale)

Un VPN overlay apporte :
- identité par clés,
- chiffrement par défaut,
- pas de port forwarding sur la box du site,
- règles d’accès fines.

La passerelle Edge est enrôlée et devient le point d’entrée contrôlé pour la maintenance.

Bénéfices :
- réseau site privé,
- fonctionne derrière NAT,
- accès limité à des devices/utilisateurs approuvés.

---

## 4) Périmètre d’accès et frontières

L’accès distant couvre :
- la passerelle Edge (SSH, dashboard, logs),
- optionnel : service debug (web) accessible uniquement via VPN.

L’accès distant ne couvre pas :
- l’accès public direct aux STM32 ou au FPGA,
- l’accès public direct au broker local.

Si un accès aux équipements internes est requis :
- via la passerelle comme jump host, ou
- via une politique VPN explicite et restrictive.

---

## 5) Procédure d’exploitation (usage sûr)

### 5.1 Activer l’accès
- Activer uniquement durant une fenêtre maintenance.
- Informer l’opérateur que l’accès est actif.

### 5.2 Authentifier et se connecter
- Auth forte (clés SSH, enrollement device).
- Autoriser uniquement les devices approuvés.

### 5.3 D’abord lecture seule
Avant toute action :
- inspecter l’état système et topics santé,
- vérifier absence d’alarmes sûreté,
- confirmer que la voie n’est pas en situation risquée.

### 5.4 Actions contrôlées
Si override nécessaire :
- utiliser le dashboard cloud (audit) si disponible, ou
- appliquer la procédure maintenance locale approuvée.

### 5.5 Désactiver
Après intervention :
- désactiver si temporaire,
- rotation clés en cas de suspicion,
- conserver logs.

---

## 6) Flux vidéo / streaming debug (maintenance uniquement)

Un flux vidéo debug peut être exposé pour maintenance :
- pas d’URL publique,
- accessible uniquement via VPN overlay,
- optionnel et désactivable par défaut.

Note conformité :
- plaques/visages peuvent apparaître.
- streamer uniquement si nécessaire.
- envisager masquage ou limitation des snapshots selon contexte légal.

---

## 7) Logs et traçabilité

Au minimum :
- timestamps activation/désactivation accès,
- identité connectée (device/user),
- actions critiques (override, config).

Si cloud disponible, journaliser les commandes opérateur côté cloud.

---

## 8) Pannes et sûreté

Une panne d’accès distant ne doit pas impacter :
- la sûreté barrière,
- l’usage local,
- les procédures d’urgence.

Si mauvais paramétrage :
- défaut “fermé” (pas de connectivité) plutôt que service exposé publiquement.

---

## 9) Checklist durcissement

- Ne jamais exposer le port du broker local publiquement.
- SSH sans mot de passe, clés uniquement.
- Limiter la membership VPN à des devices de confiance.
- Principe du moindre privilège.
- Passerelle à jour et services supervisés.
- Procédure manuelle sur site sans dépendance à l’accès distant.

