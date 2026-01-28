Language: Français | [English](../../en/overview/system-flows.md)

# Flows système SysPark

Ce document décrit les flows opérationnels de SysPark, depuis la mise sous tension jusqu’aux cycles entrée/sortie, en incluant l’aide par vision, le paiement, les overrides opérateur, les modes dégradés et la gestion d’urgence. Objectif : rendre les rôles explicites et garder des frontières stables : **la passerelle décide**, **le FPGA exécute en sûreté**, **la STM32 gère les interactions terrain**.

---

## 0) Mise en route et état “READY” (power-on → système opérationnel)

### Déclencheur
- Alimentation secteur appliquée ou démarrage via la batterie de secours.

### Étapes
1. **Énergie et sûreté**
   - Stabilisation du bus 12 V, activation des conversions DC/DC.
   - Validation BMS (tensions cellules, limites courant, températures).
   - En cas d’anomalie BMS : système en état restreint (pas d’actionneurs).

2. **Initialisation réseau**
   - La passerelle, le FPGA et la STM32 montent les liens Ethernet.
   - Adressage statique ou DHCP selon configuration site.

3. **Plan de contrôle local**
   - Le **broker MQTT local** est disponible sur le LAN du parking.
   - Le système peut fonctionner en mode local même sans Internet.

4. **Connexion cloud (optionnelle mais recommandée)**
   - Le pont MQTT relaye une liste *whitelistée* de topics vers le broker public.
   - Le serveur cloud se connecte et réactive supervision et paiements.

5. **Santé sous-systèmes**
   - Chaque bloc publie un heartbeat/statut (passerelle, FPGA, STM32, capteurs).
   - La passerelle consolide l’état global et initialise les messages d’affichage.

### Sorties
- Passage en **READY** quand :
  - BMS OK,
  - communication LAN OK,
  - nœuds d’exécution en état sain.

---

## 1) Flow Entrée (arrivée véhicule → authentification → ouverture barrière → traçabilité)

### Déclencheur
- Présence véhicule détectée à l’entrée (capteur boucle/IR/etc.).

### Entrées
- Événement capteur de présence
- Optionnel : snapshot caméra / lecture plaque
- Authentification : badge RFID et/ou PIN (selon site)

### Étapes
1. **Détection arrivée**
   - Publication de l’événement de présence.
   - Mise à jour affichage : “Veuillez vous identifier” / “Bienvenue”.

2. **Authentification**
   - **Chemin badge RFID** (typique) :
     - STM32 lit l’UID et publie un événement d’identification.
     - La passerelle évalue l’accès via :
       - une whitelist locale mise en cache (mode offline), et/ou
       - une politique gérée côté cloud (mode online).
   - **Chemin PIN** (optionnel) :
     - Saisie PIN sur l’interface locale.
     - STM32 publie le résultat pour validation.

3. **Décision**
   - La passerelle autorise ou refuse l’entrée selon :
     - droits utilisateur, plages horaires, capacité,
     - anti-passback si activé (éviter une double entrée sans sortie),
     - optionnel : utilisation de la confiance vision comme facteur complémentaire.

4. **Commande d’exécution**
   - La passerelle envoie la demande d’ouverture vers la couche d’exécution.
   - Le FPGA (ou l’exécuteur dédié) applique :
     - séquence déterministe,
     - checks sûreté (timeouts, limites),
     - état sûr si anomalie.

5. **Confirmation**
   - Retour d’état : ouvert / en cours / erreur.
   - Affichage : “Passez” / “Patientez” / “Erreur, contactez l’opérateur”.

6. **Mise à jour et traçabilité**
   - Journalisation locale et/ou cloud :
     - timestamp, méthode (RFID/PIN/vision),
     - identifiant (masqué si besoin),
     - état barrière et alarmes.
   - Mise à jour occupation.

### Sorties
- Ouverture barrière si autorisé.
- Occupation + session d’entrée créée (cloud si online).

---

## 2) Flow Sortie avec paiement (arrivée → calcul tarif → paiement → ouverture)

### Déclencheur
- Présence véhicule détectée à la sortie.

### Entrées
- Événement présence
- Optionnel : résultat lecture plaque (LPR)
- Statut paiement depuis le cloud (Stripe ou équivalent)
- PIN sortie (fallback), override opérateur (fallback)

### Étapes
1. **Détection arrivée**
   - Publication de présence.
   - Affichage : “Sortie en cours…” / “Veuillez patienter”.

2. **Identification véhicule**
   - Prioritaire : LPR fournit plaque (+ confiance + timestamp).
   - Fallbacks :
     - badge RFID sortie,
     - PIN sortie,
     - assistance opérateur (override).

3. **Calcul tarif**
   - Serveur cloud calcule selon durée, tarifs, règles.
   - Cloud publie une demande de paiement (montant, référence session).

4. **Paiement**
   - Paiement via interface cloud.
   - Confirmation validée côté cloud (webhook).
   - Publication d’un événement **paiement validé** lié à la session.

5. **Autorisation sortie**
   - STM32 sortie reçoit “paiement validé” et déverrouille l’étape sortie.
   - Passerelle demande ouverture barrière à l’exécuteur.

6. **Exécution + confirmation**
   - Exécuteur ouvre avec sûreté.
   - Journalisation :
     - preuve paiement,
     - timestamp sortie,
     - état barrière + warnings.

7. **Mise à jour occupation**
   - Occupation décrémentée.
   - Session clôturée (cloud si online).

### Sorties
- Ouverture uniquement après autorisation (paiement validé ou override explicite).
- Revenu et session enregistrés.

---

## 3) Flow Vision (caméra → détection plaque → OCR → validation → support décision)

### Déclencheur
- Présence véhicule ou politique de capture périodique.

### Entrées
- Frames caméra
- Sorties modèle vision (zone plaque, confiance)
- OCR
- Règles de validation (format, caractères autorisés)

### Étapes
1. **Capture + prétraitement**
   - Acquisition image, préparation pour inference.
   - Optionnel : crop/stabilisation.

2. **Détection plaque**
   - Détection des régions candidates.
   - Sélection meilleure hypothèse (confiance + géométrie).

3. **OCR + normalisation**
   - Extraction caractères.
   - Nettoyage (espaces, casse, caractères parasites).
   - Validation format.

4. **Publication**
   - Publication plaque reconnue, confiance, optionnel snapshot.

5. **Intégration décision**
   - Entrée : second facteur ou pré-identification.
   - Sortie : rattachement à la session active pour calcul tarif.

### Gestion échecs
- Si confiance faible ou validation KO :
  - ne pas bloquer la voie,
  - basculer RFID/PIN/opérateur,
  - stocker un marqueur “non vérifié” pour analyse.

---

## 4) Supervision et override opérateur (dashboard → action → audit)

### Déclencheur
- Opérateur consulte le dashboard ou reçoit une alerte.

### Entrées
- Télémétries (statuts, heartbeats, alarmes)
- Flux debug (maintenance)
- Commandes opérateur (ouvrir barrière, reset, config)

### Étapes
1. **Observation**
   - Occupation, événements récents, alarmes, état système.
   - Optionnel : flux vidéo debug via accès sécurisé.

2. **Commande manuelle**
   - Action demandée (ouvrir barrière, stop mouvement, clear fault).
   - Autorisation + journalisation (qui/quand/pourquoi).

3. **Exécution**
   - Passerelle relaie vers l’exécuteur.
   - Exécuteur applique limites sûreté.

4. **Audit**
   - Cloud conserve l’événement :
     - identité opérateur/admin,
     - motif,
     - résultat et timing.

### Sorties
- Récupération sûre sans contourner la couche de sûreté.

---

## 5) Configuration et gestion des accès (politique cloud → passerelle → persistance STM32)

### Déclencheur
- Admin met à jour whitelist, PIN, tarifs, paramètres.

### Entrées
- Action admin via interface web
- Payload de configuration (ACL, PIN, options)

### Étapes
1. **Publication cloud**
   - Diffusion événement configuration.

2. **Contrôle passerelle**
   - Filtrage des familles autorisées vers le LAN.
   - Possibilité de renforcer l’auth sur changements sensibles.

3. **Application + persistance STM32**
   - STM32 met à jour config locale (whitelist/PIN) sur stockage SD.
   - STM32 publie “sync OK” vers le cloud.

### Sorties
- Mode offline possible (accès via cache).
- Traçabilité claire des changements.

---

## 6) Modes dégradés (perte Internet, panne nœud, vision KO)

SysPark vise une continuité d’usage sous pannes partielles.

### A) Internet indisponible
- Broker local continue.
- Passerelle maintient les flows basiques via cache.
- Paiements possibles à désactiver ou remplacer par :
  - sortie RFID pour utilisateurs de confiance,
  - PIN sortie,
  - override opérateur,
  selon politique site.

### B) Panne exécuteur local
- Si exécuteur en fault :
  - blocage automatique commandes,
  - affichage clair,
  - notification opérateur,
  - récupération manuelle encadrée si sûre.

### C) Vision dégradée
- Ne doit pas bloquer :
  - retour RFID/PIN,
  - collecte de diagnostics.

### D) Broker local indisponible
- Fallback possible si défini :
  - lien direct passerelle → exécuteurs,
  - ou état restreint jusqu’au retour broker.
- Recommandé : supervision service + auto-restart.

---

## 7) Flow sûreté et urgence (obstacle, timeout, alerte incendie)

### Déclencheurs typiques
- Obstacle pendant fermeture.
- Timeout mouvement ou état incohérent.
- Signal incendie via canal indépendant.

### Règles sûreté
1. **Stop + état sûr**
   - arrêt mouvement et état sûr si :
     - obstacle,
     - dépassement fenêtre temporelle,
     - incohérence d’état.

2. **Message utilisateur clair**
   - affichage : “Obstacle détecté, veuillez dégager” / “Contactez opérateur”.

3. **Propagation alarme**
   - publication locale puis cloud si possible.
   - notification opérateur.

4. **Politique urgence**
   - incendie : appliquer la politique définie site, typiquement :
     - arrêt mouvements non essentiels,
     - sortie libre ou ouverture barrière si requis et sûr,
     - journalisation pour post-mortem.

### Sorties
- La sûreté prime toujours.
- L’urgence reste gérable même si le réseau IP principal est compromis.

---

## 8) Ce qui est journalisé (base traçabilité)

Pour chaque session et événement critique :

- timestamps (entrée, sortie, paiement),
- méthode d’auth (RFID, PIN, vision, override),
- états système et résultats exécuteur,
- alarmes et actions de récupération,
- actions opérateur avec audit (si applicable).

Objectif : système démontrable, analysable, et maintenable.
