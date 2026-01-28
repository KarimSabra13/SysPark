Language: Français | [English](../../en/edge/led-banner.md)

# Bandeau LED / Affichage usager

SysPark intègre un affichage usager (bandeau LED) pour fournir un retour immédiat et non ambigu à l’entrée et à la sortie. C’est un élément clé d’usage et de sûreté : le conducteur doit comprendre quoi faire sans dépendre d’un opérateur.

L’affichage est piloté via MQTT pour que toute source de décision validée (orchestration edge ou politique cloud) puisse mettre à jour le message de manière cohérente.

---

## 1) Objectif

### Objectifs principaux
- Réduire l’incertitude au niveau de la barrière (instruction claire).
- Rendre l’état du flow visible (identifier, attendre, passer, payer).
- Donner un retour immédiat en mode dégradé (panne, offline).
- Répondre à une contrainte B2B (messages prévisibles et standardisés).

### Contraintes
- Doit fonctionner en mode local (LAN).
- Ne doit pas conditionner la sûreté (informatif, pas un actionneur).

---

## 2) Modèle de contrôle

### Design par message
L’affichage est mis à jour en publiant un texte sur un topic MQTT.

Topic canonique :
- `parking/display/text`

Sens :
- Cloud → Local (via bridge), ou Edge → Local (direct LAN broker)

QoS :
- QoS 1 recommandé

Retain :
- Pas de retain par défaut (messages d’instruction transitoires)

---

## 3) Format message

Deux options pratiques :

### A) Texte brut (minimal)
- Payload string affiché tel quel.

Exemples :
- `BIENVENUE`
- `PRESENTEZ BADGE`
- `PAIEMENT REQUIS`
- `PASSEZ`
- `ATTENDEZ`
- `APPELEZ OPERATEUR`

### B) JSON (contrôle enrichi)
Si besoin :
- `text` : contenu
- `ttl_s` : durée avant effacement
- `lane` : identifiant entrée/sortie
- `prio` : priorité

Note :
- JSON optionnel ; texte brut est souvent le plus robuste.

---

## 4) Catalogue messages recommandé

Standardiser un petit ensemble de messages.

### Messages entrée
- Idle :
  - “BIENVENUE”
- Demande identification :
  - “PRESENTEZ BADGE”
  - “SAISISSEZ PIN”
- Accès autorisé :
  - “PASSEZ”
- Accès refusé :
  - “ACCES REFUSE”
- Parking complet :
  - “COMPLET”
- Traitement :
  - “ATTENDEZ”
- Panne :
  - “PANNE APPELEZ OPERATEUR”

### Messages sortie
- Idle :
  - “SORTIE”
- Paiement requis :
  - “PAIEMENT REQUIS”
- Paiement en cours :
  - “PAIEMENT…”
- Paiement validé :
  - “PAYE PASSEZ”
- Session inconnue / fallback :
  - “VOIR OPERATEUR”
- Panne :
  - “PANNE APPELEZ OPERATEUR”

---

## 5) Règles de mise à jour et priorités

### Priorité (recommandé)
1. Urgence / sûreté : “STOP”, “EVACUEZ”, “PANNE…”
2. Pannes : “APPELEZ OPERATEUR”
3. Prompts flow : “PAIEMENT REQUIS”, “PRESENTEZ BADGE”
4. Info : “BIENVENUE”, “SORTIE”

### TTL (optionnel)
- TTL court pour éviter messages obsolètes,
- TTL long pour pannes jusqu’à clear.

### Multi-voies
Si plusieurs voies :
- topics séparés (ex : `parking/entry/display/text`)
- ou champ `lane` dans payload.

---

## 6) Comportement en panne

### MQTT indisponible
- Afficher un message safe par défaut (“ATTENDEZ” / “VOIR OPERATEUR”).
- Éviter des retries agressifs qui saturent le broker.

### Cloud indisponible
- Edge pilote localement.
- Dégradation cohérente (paiement off → “VOIR OPERATEUR”).

### Conflit de publishers
Pour éviter une “guerre” de messages :
- un publisher autoritaire par voie (souvent Edge),
- cloud autorisé uniquement pour certains messages (paiement validé),
- allowlist bridge adaptée.

---

## 7) Guidelines exploitation (qualité texte)

- Mots courts, vocabulaire constant.
- Messages non ambigus.
- Majuscules si nécessaire.
- Langue cohérente par site.
- Éviter l’affichage de données personnelles (plaque complète).

---

## 8) Place dans le système

- L’affichage reflète l’état du système.
- Il ne commande pas les actionneurs.
- Testable indépendamment en publiant des messages sur le topic.

