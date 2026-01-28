Language: Français | [English](../../en/cloud/mqtt-topics.md)

# Topics MQTT et Contrat de Données

Ce document définit l’interface MQTT de SysPark. C’est le contrat qui garantit l’interopérabilité entre passerelle Edge, STM32, couche d’exécution FPGA et services Cloud.

Principe :
- Les topics sont des APIs stables.
- Les payloads sont prévisibles et versionnables.
- Les règles QoS et retain sont explicites.
- Le bridge joue le rôle de pare-feu applicatif entre LAN site et broker public.

---

## 1) Namespace et règles de nommage

### Racine
Tous les topics SysPark sont sous :
- `parking/`

### Style
- minuscules.
- noms pour les états, verbes ou `cmd` pour les commandes.
- chemins courts mais explicites.

Exemples :
- `parking/sensor_gate/present` est un flux d’état.
- `parking/barriere/cmd` est un canal de commande.

---

## 2) Conventions de payload

SysPark utilise deux styles :

### A) Payload simple (string ou nombre)
Pour messages très courts et fréquents, ou parsing minimal.
- Exemples : `0`, `1`, `"110"`, `"LIBRE: 12"`

### B) Payload JSON
Pour timestamps, métadonnées, plusieurs champs.

Champs recommandés :
- `ts` : timestamp Unix en millisecondes (ou secondes si contrainte forte, mais rester cohérent).
- `src` : identifiant du publisher (`edge`, `stm32_entry`, `stm32_exit`, `fpga`, `cloud`).
- `state` : booléen ou état texte.
- `code` : code d’erreur pour alarmes.

Champ sécurité utilisé par les mises à jour ACL :
- `secret` : secret applicatif partagé pour rejeter des changements non autorisés.

---

## 3) Politique QoS et retain

### QoS
- QoS 0 : télémétrie tolérant une perte ponctuelle.
- QoS 1 : commandes ou événements devant arriver au moins une fois.
- QoS 2 : alertes critiques ou configuration où les doublons doivent être évités.

### Retain
Retain est utilisé pour les topics d’état afin qu’un nouveau client obtienne un snapshot immédiat.
Les commandes ne doivent pas être retain, sauf besoin explicite de re-appliquer une commande après reconnexion.

Recommandations :
- Retain : présence, états actionneurs, liste ACL, météo.
- Pas retain : commandes barrière, commandes affichage, commandes caméra temps réel.

---

## 4) Règles de direction du bridge

SysPark utilise typiquement un broker local sur site, et synchronise une partie des topics vers un broker public servant de relais pour le Cloud.

Le bridge doit implémenter deux allowlists :
- Cloud → Local : uniquement les topics de commande indispensables.
- Local → Cloud : uniquement les états et télémétries utiles.

Tout le reste est ignoré.

Objectifs :
- éviter les boucles,
- limiter l’exposition de trafic interne,
- empêcher l’injection de topics depuis le public.

---

## 5) Topic map

### 5.1 Sûreté et présence

| Topic | Sens | QoS | Retain | Payload | Rôle |
|---|---|---:|:---:|---|---|
| `parking/sensor_gate/present` | Local → Cloud | 1 | Oui | JSON ou `0/1` | Présence véhicule proche barrière. Retain utile pour dashboard. |
| `parking/sensor_gate/heartbeat` | Local → Cloud | 0 | Non | JSON | Heartbeat périodique pour monitoring. |
| `parking/sensor_gate/error` | Local → Cloud | 2 | Non | JSON | Panne capteur ou alarme critique. |

### 5.2 Messages usagers

| Topic | Sens | QoS | Retain | Payload | Rôle |
|---|---|---:|:---:|---|---|
| `parking/display/text` | Cloud → Local | 1 | Non | string | Texte affiché sur l’affichage local. |

### 5.3 Commande barrière

| Topic | Sens | QoS | Retain | Payload | Rôle |
|---|---|---:|:---:|---|---|
| `parking/barriere/cmd` | Cloud → Local | 1 | Non | string | Commande d’actionnement barrière. Payload compact possible. |
| `parking/barriere` | Local → Cloud | 1 | Non | JSON | Événement d’identification utilisé dans le flow entrée. Contenu typique : UID RFID. |

Notes :
- Séparer commande et événement.
- Ne pas retain `parking/barriere/cmd`.

### 5.4 Pilotage caméra

| Topic | Sens | QoS | Retain | Payload | Rôle |
|---|---|---:|:---:|---|---|
| `parking/camera/cmd` | Cloud → Local | 0 | Non | JSON | Pan/tilt temps réel. QoS 0 adapté aux mises à jour fréquentes. |

### 5.5 Ascenseur (côté entrée)

| Topic | Sens | QoS | Retain | Payload | Rôle |
|---|---|---:|:---:|---|---|
| `parking/ascenseur/cmd` | Cloud → Local | 1 | Non | JSON | Demande d’étage ou action. |
| `parking/ascenseur/get` | Cloud → Local | 0 | Non | JSON | Demande de re-publication d’état. |
| `parking/ascenseur/state` | Local → Cloud | 0 ou 1 | Oui | JSON | Snapshot état ascenseur. Retain recommandé. |

### 5.6 Paiement (côté sortie)

| Topic | Sens | QoS | Retain | Payload | Rôle |
|---|---|---:|:---:|---|---|
| `parking/payment/req` | Cloud → Local | 1 | Non | JSON | Demande de paiement ou contexte tarif. |
| `parking/payment/success` | Cloud → Local | 1 | Non | JSON | Paiement validé. Débloque la sortie. |

### 5.7 Gestion ACL

| Topic | Sens | QoS | Retain | Payload | Rôle |
|---|---|---:|:---:|---|---|
| `parking/acl/add` | Cloud → Local | 2 | Non | JSON | Ajout badge/utilisateur. Inclure `secret`. |
| `parking/acl/del` | Cloud → Local | 2 | Non | JSON | Suppression badge/utilisateur. Inclure `secret`. |
| `parking/acl/full` | Cloud → Local | 2 | Non | JSON | Remplacement complet ACL. Inclure `secret`. |
| `parking/acl/enroll` | Cloud → Local | 1 | Non | JSON | Déclenchement enroll local d’un badge. |
| `parking/acl/get` | Cloud → Local | 0 | Non | JSON | Demande de publication ACL. |
| `parking/acl/list` | Local → Cloud | 0 ou 1 | Oui | JSON | Liste ACL courante. Retain recommandé. |
| `parking/acl/event` | Local → Cloud | 1 | Non | JSON | Accusé de persistance SD ou application update. |

### 5.8 Sync et contrôle opérationnel

| Topic | Sens | QoS | Retain | Payload | Rôle |
|---|---|---:|:---:|---|---|
| `parking/sync/req` | Local → Cloud | 1 | Non | JSON | Demande de resynchronisation après reboot/reco. |

### 5.9 Contexte (météo)

| Topic | Sens | QoS | Retain | Payload | Rôle |
|---|---|---:|:---:|---|---|
| `parking/meteo` | Local → Cloud | 0 | Oui | JSON | Snapshot météo pour affichage et analytics. Retain recommandé. |

---

## 6) Exigences sécurité

Baseline :
- broker local non exposé à Internet.
- bridge vers broker public en TLS.
- allowlists strictes dans les deux sens.
- secret applicatif pour les updates sensibles.
- en production : authentification broker et publication anonyme désactivée.

Exploitation :
- heartbeats pour supervision.
- QoS élevé pour alertes.
- sûreté locale indépendante du cloud.

---

## 7) Notes compatibilité et plan de nettoyage

Certaines intégrations peuvent contenir des variantes historiques de topics. Approche recommandée :
- un topic canonique par fonction,
- variantes traitées comme alias temporaires,
- migration planifiée avec fenêtre de transition,
- alias documentés explicitement ici.

