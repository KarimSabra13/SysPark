Language: Français | [English](../../en/stm32/rtos-threads.md)

# Modèle de threads Zephyr RTOS (nœud STM32)

Ce document décrit comment l’application SysPark STM32 est structurée en threads Zephyr et objets de synchronisation. Objectif : garder les tâches sensibles au timing déterministes, tout en gérant Ethernet/MQTT, rafraîchissement UI et persistance microSD de manière fiable.

Cibles de conception :
- le timing moteur ne doit pas être bloqué par le réseau ou le stockage,
- la lecture RFID doit rester réactive,
- l’UI doit refléter clairement la machine d’états,
- les messages MQTT doivent être routés sans deadlocks,
- les écritures SD doivent être sérialisées pour éviter la corruption.

---

## 1) Carte des threads (conceptuelle)

Un nœud STM32 SysPark est typiquement découpé ainsi :

### A) Communication et routage
- **Thread client MQTT**
  - maintient la connexion broker,
  - gère subscribe/publish,
  - parse les commandes entrantes.

- **Thread routeur / machine d’états**
  - consomme les “événements d’entrée” (UID RFID, paiement validé, signaux capteurs),
  - met à jour la machine d’états de voie,
  - publie les états et messages UI.

### B) Acquisition
- **Thread acquisition RFID**
  - lit l’interface RFID,
  - extrait l’UID et le formate,
  - pousse l’UID dans une file.

- **Thread sampling capteurs (optionnel)**
  - lit fin de course, entrées présence, capteurs analogiques,
  - publie snapshots ou déclenche alarmes.

### C) Interfaces utilisateur
- **Thread mise à jour LCD**
  - affiche prompts (identifier, attendre, passer, payer),
  - montre état réseau et fautes,
  - ne doit jamais bloquer le contrôle.

- **Thread OLED (optionnel)**
  - vue ascenseur ou debug détaillé.

### D) Contrôle mouvement (rôle entrée)
- **Thread contrôle ascenseur**
  - homing au démarrage,
  - séquences déterministes,
  - surveillance fin de course et timeouts,
  - publication état périodique.

### E) Persistance
- **Thread stockage**
  - sérialise les lectures/écritures microSD,
  - persiste PIN et ACL,
  - logs optionnels avec politique d’usure.

Tous les builds n’activent pas tous les threads. En rôle sortie, le contrôle mouvement peut être absent.

---

## 2) Priorités et guidelines timing

Ordre de priorité sûr :

1. **Contrôle mouvement / monitoring sûreté**
   - priorité la plus haute
   - contraintes timing strictes

2. **Acquisition RFID**
   - priorité haute
   - réactivité requise

3. **Routeur / machine d’états**
   - priorité moyenne-haute
   - cohérence UI + MQTT

4. **Communication MQTT**
   - priorité moyenne
   - maintien connexion, publish/sub

5. **Rendu UI**
   - faible/moyenne
   - ne doit pas impacter le critique

6. **Stockage**
   - faible
   - exécution arrière-plan

Note :
- MQTT ne doit pas affamer les threads de contrôle.
- microSD ne doit jamais tourner en contexte haute priorité.

---

## 3) Objets de synchronisation (quoi et pourquoi)

SysPark utilise un petit ensemble de primitives :

### Files de messages
Découplent producteurs et consommateurs :
- RFID → file UID
- MQTT inbound → file commandes
- machine d’états → file UI
- machine d’états → file stockage

Bénéfices :
- pas de blocage en acquisition,
- backpressure et mémoire bornée.

### Sémaphores / flags
Pour autorisations one-shot :
- paiement validé “débloque” la sortie,
- mode enroll badge activable.

### Mutex (verrou stockage)
Protège l’accès microSD :
- empêche écritures concurrentes,
- réduit la corruption.

### Timers
Utilisés pour :
- publish périodiques (heartbeat, état ascenseur),
- timeouts (mouvement, reconnexion),
- scheduling rafraîchissement UI.

---

## 4) Machine d’états événementielle (logique centrale)

La maintenance est plus simple si la logique est centralisée en machine d’états.
Elle consomme des événements et produit :
- commandes actionneurs (dans les limites autorisées),
- publications MQTT,
- mises à jour UI,
- requêtes de persistance.

### Exemples d’événements
- `UID_DETECTED(uid)`
- `PIN_OK` / `PIN_FAIL`
- `PAYMENT_SUCCESS(session_id)`
- `LIMIT_SWITCH_HIT`
- `MOTION_TIMEOUT`
- `MQTT_DISCONNECTED`

### Exemples d’actions
- publier événement identification,
- mettre à jour LCD/OLED,
- lancer séquence mouvement (rôle entrée),
- bloquer/débloquer séquence sortie (rôle sortie),
- persister ACL sur microSD.

---

## 5) Détails rôle entrée (intégration thread ascenseur)

En mode entrée, le thread ascenseur exécute typiquement :
1. homing au démarrage :
   - mouvement jusqu’au fin de course,
   - référence position fixée (étage 0),
   - publication statut “homed”.

2. mouvement commandé :
   - réception d’une consigne d’étage,
   - conversion en pas,
   - exécution contrôlée,
   - surveillance timeout + fin de course.

3. publication :
   - état périodique (position, étage, direction, faute).

Règles sûreté :
- timeout ou fin de course inattendue → arrêt + état sûr.
- notification machine d’états pour affichage faute.

---

## 6) Détails rôle sortie (paiement validé via sémaphore)

En mode sortie, logique “unlock” :
- à la réception de `payment/success` :
  - signaler un flag/sémaphore,
  - UI “PAYE PASSEZ”,
  - autoriser l’étape suivante.

Idempotence :
- un paiement validé répété ne doit pas relancer un comportement risqué.
- la machine d’états doit vérifier si la sortie est déjà autorisée.

---

## 7) Thread stockage : stratégie de persistance sûre

### À persister
- PIN (entrée/sortie si activés),
- liste ACL (UIDs autorisés),
- version config appliquée (optionnel),
- logs minimaux (optionnel).

### Politique usure
- éviter d’écrire à chaque événement,
- batch + flush périodique,
- format simple (JSON unique ou lignes).

### Robustesse
- jamais en ISR ou contexte moteur,
- valider opérations fichier et publier un événement “ACL sync OK/FAIL”.

---

## 8) Observabilité (debug des problèmes de threads)

Signaux recommandés :
- heartbeat périodique avec :
  - mémoire libre estimée,
  - état connexion MQTT,
  - dernier code erreur.
- ring buffer de fautes.
- piles configurées explicitement et testées sous charge.

Patterns fréquents :
- SD bloque UI et affame MQTT,
- parsing MQTT bloque la machine d’états,
- files non bornées causent pression mémoire.

---

## 9) Tests d’acceptance minimaux

Le modèle est correct quand :
- timing moteur stable malgré trafic MQTT,
- RFID réactif pendant update UI,
- SD robuste sous storms de reconnexion,
- paiement validé débloque la sortie sans effet de doublon,
- recovery propre après reconnexion broker.

