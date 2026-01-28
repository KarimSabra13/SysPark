Language: Français | [English](../../en/cloud/cloud-overview.md)

# Vue d’ensemble Backend Cloud (Render)

SysPark s’appuie sur un backend cloud pour fournir une “source de vérité” sur les règles d’accès, les sessions, les paiements, la supervision et la traçabilité long terme. Le cloud ne pilote pas le temps réel. Il publie des décisions haut niveau et reçoit la télémétrie via MQTT.

Ce backend vise un usage B2B où la supervision, l’auditabilité et l’exploitation sécurisée sont prioritaires.

---

## 1) Rôle du Cloud (périmètre)

### Responsabilités principales
- Persistance des données (sessions, événements, utilisateurs, configuration).
- Décisions nécessitant un contexte global (tarifs, règles, occupation, overrides).
- Paiement (demande, validation, preuve, clôture de session).
- Dashboard admin (état live + historique).
- Alertes et notifications (exploitation, maintenance).

### Ce que le Cloud ne fait pas
- Pas de commande bas niveau déterministe d’actionneurs.
- Pas de remplacement de la sûreté locale.
- Ne doit pas devenir un point de défaillance unique pour la sécurité site.

---

## 2) Plateforme : Render (Web service + PostgreSQL)

Le cloud SysPark est hébergé sur Render avec :
- un service web (runtime applicatif),
- une base PostgreSQL managée.

Bénéfices :
- déploiement simple depuis un dépôt Git,
- gestion native des variables d’environnement,
- provisioning base et connectivité interne.

---

## 3) Modèle de communication temps réel (MQTT + UI Web)

SysPark utilise un broker MQTT public comme relais temps réel entre :
- le site physique (via un bridge edge),
- le backend cloud (décision + persistance).

### Pourquoi MQTT
- modèle asynchrone orienté événements,
- overhead faible,
- séparation claire producteurs (site) / consommateurs (cloud),
- extensible multi-sites.

### Principe du bridge
Un bridge sélectif côté edge relaie uniquement des topics autorisés :
- évite les boucles,
- réduit l’exposition,
- garde le LAN autonome.

Pour le contrat topic canonique :
- `docs/fr/cloud/mqtt-topics.md`

---

## 4) Services externes intégrés

### 4.1 Paiements (Stripe)
Rôle :
- calculer le montant et publier un contexte de paiement,
- valider la confirmation côté serveur,
- publier “paiement validé” pour débloquer la sortie,
- rattacher une preuve à la session.

Points clés :
- validation via un webhook dédié,
- aucune confiance dans une confirmation côté client.

### 4.2 Notifications (Telegram)
Rôle :
- envoyer alertes exploitation (pannes, sûreté, états anormaux),
- informer sans obligation de surveiller en continu le dashboard.

### 4.3 Météo (OpenWeatherMap + client local)
Rôle :
- fournir un contexte exploitable pour affichage ou analytics.
Note :
- un client local récupère périodiquement la météo et la pousse vers le cloud, puis publication MQTT.

### 4.4 Accès distant sécurisé (Tailscale)
Rôle :
- accès maintenance sécurisé (debug, tunnel vidéo) sans ouvrir de ports entrants.
Intention :
- accès explicite, contrôlé, et traçable.

---

## 5) Responsabilité base de données et modèle (conceptuel)

La base stocke :
- utilisateurs et droits d’accès,
- sessions (entrée, sortie, badge/plaque, statut),
- paiements (montant, référence, timestamp validation),
- événements et alarmes (quoi/quand/résultat),
- snapshots configuration (tarifs, politiques, état sync ACL).

Principe :
- chaque action critique est traçable,
- les overrides manuels sont journalisés (identité opérateur si applicable),
- le cloud reste la couche d’audit même si le site tourne temporairement en offline.

---

## 6) Dashboard admin (vue opérateur)

L’interface web fournit :
- occupation et états “last known”,
- fil d’événements récents (entrées/sorties/alarmes/overrides),
- recherche sessions et preuves (plaque, paiement, etc.),
- actions admin :
  - règles et tarifs,
  - gestion accès,
  - commandes contrôlées via MQTT (demande d’ouverture, reset, etc.).

Les mises à jour “live” s’appuient sur l’état consolidé côté cloud.

---

## 7) Configuration et secrets (variables d’environnement)

Le cloud SysPark utilise des variables d’environnement pour :
- URL base de données,
- broker MQTT (hôte/port/identifiants),
- identifiants admin,
- clés paiement + secret webhook,
- token bot notification + chat ID,
- secret applicatif pour certaines mises à jour sensibles.

Baseline sécurité :
- jamais de secrets dans Git,
- rotation possible,
- contrôle strict des accès Render.

---

## 8) Cycle de déploiement (haut niveau)

1. Push du dépôt (docs + configuration serveur).
2. Render récupère et déploie le service web.
3. Configuration des variables d’environnement.
4. Provision PostgreSQL et liaison au service.
5. Connexion cloud au broker MQTT public (TLS).
6. Validation end-to-end :
   - télémétrie reçue,
   - décisions publiées,
   - paiements et notifications OK.

---

## 9) Modes de défaillance et résilience

### Coupure Internet
- le site doit conserver des flows basiques via cache,
- le cloud reprend la synchro à la reconnexion.

### Panne broker public
- le site continue localement,
- supervision cloud dégradée le temps du rétablissement.

### Panne cloud
- sûreté locale prioritaire,
- bascule sur procédures locales et overrides encadrés.

---

## 10) Liens dans la doc SysPark

- Architecture : `docs/fr/overview/architecture.md`
- Flows système : `docs/fr/overview/system-flows.md`
- Contrat MQTT : `docs/fr/cloud/mqtt-topics.md`

