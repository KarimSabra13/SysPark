Language: Français | [English](../../en/stm32/storage-sd.md)

# Stockage microSD et persistance (nœud STM32)

SysPark utilise une carte microSD sur le STM32 pour persister des données petites mais critiques après redémarrage. L’objectif n’est pas de construire une base lourde sur microcontrôleur, mais d’assurer autonomie locale et reprise prévisible lorsque la connectivité est instable.

Intentions :
- garder le parking utilisable en mode LAN,
- ne pas perdre les droits d’accès (PIN/ACL) après reset,
- maintenir une traçabilité minimale sans user la microSD.

---

## 1) Ce qui est stocké (périmètre)

### Données nécessaires
- **PIN entrée** (si mode PIN actif)
- **PIN sortie** (si mode PIN actif)
- **ACL whitelist** (UID RFID autorisés)
- **Marqueur dernière config appliquée** (optionnel, sync/debug)

### Données optionnelles
- **Log local événements** (petit, faible fréquence)
- **Derniers paramètres réseau** (si utile, IP statique préféré en démo)
- **Marqueurs calibration/homing** (si utile, mais sûreté prioritaire)

---

## 2) Pourquoi stocker localement (même avec un cloud)

Parce que :
- Internet peut tomber,
- le broker public peut être indisponible,
- le cloud peut être injoignable,
- le STM32 doit pouvoir exécuter des flows basiques selon une politique offline.

Le cloud reste la couche d’audit long terme, mais le STM32 doit posséder assez d’état pour se comporter correctement sans lui.

---

## 3) Layout fichiers (recommandé)

Layout simple. Exemple :
- `/SYS_PARK/`

Fichiers :
- `/SYS_PARK/pins.json`
- `/SYS_PARK/acl.json`
- `/SYS_PARK/state.json` (optionnel)
- `/SYS_PARK/log/events.log` (optionnel)

### pins.json (exemple)
- `entry_pin`
- `exit_pin`
- `updated_ts`

### acl.json (exemple)
- `version`
- `updated_ts`
- `uids` (tableau strings UID)

### state.json (optionnel)
- timestamp boot
- timestamp dernière sync MQTT
- rôle (entrée/sortie)
- dernier code faute

Règle :
- fichiers petits et simples à parser,
- un fichier “source de vérité” par catégorie.

---

## 4) Workflow de mise à jour (cloud → edge → persistance STM32)

Les mises à jour ACL et PIN peuvent venir du cloud via MQTT.

### Étapes
1. Le cloud publie une commande (add/del UID ou replace liste complète).
2. Le bridge edge relaie seulement les topics allowlistés.
3. Le STM32 reçoit et valide :
   - schéma message
   - champ secret applicatif si utilisé
4. Application en RAM.
5. Écriture sûre vers microSD.
6. Publication d’un événement d’ack :
   - success/fail
   - version courante

Objectif : update traçable et robuste.

---

## 5) Stratégie d’écriture sûre (éviter la corruption)

### Pattern quasi-atomique
1. Écrire vers fichier temporaire :
   - `acl.json.tmp`
2. Flush + close.
3. Rename :
   - remplacement `acl.json` par `.tmp`

### Validation avant commit
- valider JSON avant rename,
- valider contraintes UID (taille, caractères),
- valider contraintes PIN (digits, longueur).

### Récupération au boot
- si fichier principal absent ou invalide :
  - tenter de lire le `.tmp`,
  - sinon fallback safe (mode restreint).

---

## 6) Sérialisation accès SD (contrainte threads)

Comme plusieurs tâches peuvent demander la persistance :
- un seul thread stockage fait les I/O SD,
- les autres passent par une file stockage,
- un mutex protège la couche driver SD.

Ne jamais écrire SD depuis :
- ISR,
- threads timing moteur haute priorité,
- callbacks MQTT si blocants.

---

## 7) Politique d’usure (réduire la fréquence d’écriture)

La microSD a une endurance limitée. Éviter “write à chaque événement”.

Recommandations :
- écrire une fois par transaction d’update ACL,
- debounce des commandes répétées,
- logs essentiels seulement,
- rotation logs avec taille max,
- éviter les rewrites de grosses listes trop souvent si add/del suffit.

---

## 8) Intégrité et sécurité

### Intégrité
- publier un ack après update,
- compteur version ACL,
- timestamps pour traçabilité.

### Sécurité
- updates sensibles avec secret applicatif et/ou ACL broker,
- éviter de stocker des secrets inutilement,
- ne pas stocker de données perso complètes, seulement tokens nécessaires (UID).

---

## 9) Tests d’acceptance

Une persistance correcte doit valider :
- recovery après power cycle (PIN/ACL intacts),
- updates ACL répétées sans corruption,
- storm événements sans deadlock SD,
- fallback sûr si SD absente/illisible,
- croissance log bornée.

