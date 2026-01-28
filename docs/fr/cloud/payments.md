Language: Français | [English](../../en/cloud/payments.md)

# Paiements et facturation

SysPark intègre le paiement en ligne pour permettre une sortie contrôlée, une traçabilité complète de la facturation et un workflow opérateur clair. Le paiement est validé côté Cloud puis utilisé comme signal d’autorisation pour débloquer la sortie, tandis que la sûreté et l’exécution déterministe restent gérées sur site.

Ce document définit :
- comment le tarif est calculé,
- comment la demande de paiement est générée,
- comment la validation est confirmée,
- comment la sortie est débloquée,
- comment tout est journalisé,
- quoi faire en modes dégradés.

---

## 1) Acteurs et responsabilités

### Backend Cloud (Render)
- Calcule le montant (tarifs, durée, règles).
- Génère le contexte de paiement côté utilisateur.
- Valide le paiement côté serveur via la confirmation du prestataire.
- Publie un événement d’autorisation pour débloquer la sortie.
- Persiste l’audit (session, preuve paiement, timestamps, overrides).

### Prestataire de paiement (Stripe)
- Gère l’interface de paiement et le traitement carte.
- Notifie le Cloud du résultat via une confirmation serveur-à-serveur.
- Fournit une référence transaction et une preuve stockée pour audit.

### Passerelle site (BeagleY-AI)
- Relaye les événements paiement entre site et cloud via MQTT (bridge sélectif).
- Maintient la cohérence des flows (messages affichage, transitions).

### Contrôleur sortie (STM32 rôle sortie)
- Attend une autorisation “paiement validé” pour autoriser la sortie.
- Exécute la séquence locale (guidage, confirmation, déclenchement ouverture via couche d’exécution).

### Couche d’exécution (FPGA / exécuteur actionneur)
- Ouvre la barrière après autorisation.
- Applique les limites sûreté (timeouts, obstruction, état sûr en fault).

---

## 2) Objets de données (conceptuels)

### Session
Une session représente un cycle complet de stationnement.
Champs typiques :
- `session_id` (unique, généré cloud)
- `entry_ts`, `exit_ts`
- référence d’identité (plaque si dispo, UID badge si applicable, ou token fallback)
- `status` : active, pending_payment, paid, closed, flagged

### Paiement
Un paiement est lié à une session unique.
Champs typiques :
- `payment_id` (interne cloud)
- `provider` : stripe
- `provider_ref` : référence transaction / intent
- `amount`, `currency`
- `validated_ts`
- `state` : requested, pending, paid, failed, canceled

---

## 3) Règles de calcul tarif

Le calcul est côté Cloud car il dépend des règles globales.
Entrées possibles :
- durée (entry_ts → maintenant),
- grille tarifaire (horaire, forfait, période de grâce),
- pénalités (ticket perdu), réductions (abonnements),
- plafonds éventuels.

Sorties :
- montant dû,
- détail (optionnel),
- session passée à `pending_payment`.

---

## 4) Flow paiement bout-en-bout (voie sortie)

### Déclencheur
- Présence véhicule détectée à la sortie (capteur et/ou capture vision).

### Étapes
1. **Identifier la session**
   - Prioritaire : lecture plaque pour retrouver la session active.
   - Fallbacks : badge RFID, PIN sortie, sélection opérateur via dashboard.

2. **Calculer le montant**
   - Calcul cloud.
   - Session mise à `pending_payment`.

3. **Publier la demande de paiement**
   - Publication d’un message contenant :
     - référence session,
     - montant et devise,
     - message affichage éventuel.

   Topic MQTT :
   - `parking/payment/req`

4. **Paiement utilisateur**
   - Paiement via interface cloud liée à la session.
   - Traitement par le prestataire.

5. **Validation Cloud (côté serveur)**
   - Le Cloud reçoit la confirmation et la valide.
   - Mise à jour :
     - paiement → `paid`
     - session → `paid`

6. **Publier l’autorisation paiement**
   - Publication d’un message “paiement validé” lié à la session.

   Topic MQTT :
   - `parking/payment/success`

7. **Débloquer la sortie**
   - STM32 sortie reçoit `payment/success` et passe en état “sortie autorisée”.
   - La passerelle demande l’ouverture barrière à l’exécuteur.

8. **Ouverture barrière et clôture**
   - L’exécuteur ouvre en sûreté et confirme.
   - Le Cloud clôture la session (exit_ts, statut final) et archive la preuve.

---

## 5) Messages MQTT (résumé contrat)

### `parking/payment/req`
Sens :
- Cloud → Local

But :
- Indiquer qu’un paiement est requis et donner le contexte.

Champs (JSON recommandé) :
- `ts`, `src`
- `session_id`
- `amount`, `currency`
- optionnel : `label`, `reason`, `plate`, `duration`

QoS :
- 1 recommandé

Retain :
- Non

### `parking/payment/success`
Sens :
- Cloud → Local

But :
- Autoriser la sortie après validation paiement.

Champs :
- `ts`, `src`
- `session_id`
- `provider_ref` (ou référence preuve)
- optionnel : `amount`, `currency`

QoS :
- 1 recommandé

Retain :
- Non

---

## 6) Exigences sécurité

### Validation serveur uniquement
La sortie ne doit être débloquée qu’après validation côté Cloud via preuve prestataire. Les confirmations côté client ne sont pas fiables.

### Rejeu et doublons
MQTT peut livrer des doublons (QoS 1). Tous les nœuds doivent traiter un `payment/success` répété comme idempotent pour une même session.

### Durcissement bridge/broker
- Seuls les topics paiement et commandes nécessaires doivent traverser le bridge.
- Désactiver la publication anonyme en production.
- Secrets et clés via variables d’environnement, jamais dans Git.

---

## 7) Cas d’échec et récupération

### Paiement refusé / annulé
- Session reste `pending_payment`.
- Sortie bloquée.
- Message clair et option de retry ou assistance opérateur.

### Cloud injoignable (coupure internet)
Options selon politique site :
- Désactiver paiement carte et basculer :
  - sortie RFID utilisateurs de confiance,
  - PIN sortie,
  - override opérateur avec audit.
- Ou mode restreint avec procédure opérateur.

### Prestataire injoignable
- Le Cloud ne peut pas valider.
- Sortie reste bloquée tant que confirmation indisponible.
- Override possible si politique l’autorise.

### Panne broker public
- Le site reste sûr localement mais la validation paiement distante est indisponible.
- Mode offline avec procédures explicites.

---

## 8) Audit (ce qui doit être journalisé)

Pour conformité et debug :
- cycle session : entry_ts, payment_req_ts, payment_validated_ts, exit_ts
- montant et devise
- référence prestataire et résultat validation
- identité utilisée (plaque/badge/fallback)
- overrides opérateur (qui/pourquoi/quand)
- résultat exécution barrière (ouvert, timeout, fault)

Objectif :
- chaque sortie doit être expliquable a posteriori.
