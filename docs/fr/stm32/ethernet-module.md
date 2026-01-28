Language: Français | [English](../../en/stm32/ethernet-module.md)

# Réseau Ethernet (nœud STM32)

SysPark utilise Ethernet pour connecter les nœuds STM32 au LAN du parking. Ethernet est choisi pour la robustesse, une latence plus prévisible que le Wi-Fi, et une intégration multi-équipements plus simple en démo (passerelle + FPGA + plusieurs STM32).

Ce document décrit le modèle réseau Ethernet côté STM32 : adressage, topologie, attentes MQTT, et une méthode de test pratique.

---

## 1) Pourquoi Ethernet dans SysPark

- Lien stable en environnement bruité (moteurs, convertisseurs).
- Intégration prédictible : IP fixes, pas de problèmes de roaming Wi-Fi.
- Segmentation facile du LAN démo vs réseau externe.
- MQTT fiable avec signaux clairs (link up/down).

---

## 2) Topologie LAN (démo SysPark typique)

Un LAN SysPark contient souvent :
- passerelle Edge (BeagleY-AI)
- nœud FPGA d’exécution
- STM32 entrée
- STM32 sortie
- optionnel : PC opérateur

Connexion via :
- petit switch Ethernet, ou
- routeur utilisé comme switch/bridge.

Préférence :
- LAN privé et indépendant d’Internet.
- Internet uniquement via passerelle/bridge si nécessaire.

---

## 3) Stratégie d’adressage (IPv4 statique recommandé)

IPv4 statique pour démos reproductibles :
- simple à documenter,
- évite les surprises DHCP,
- troubleshooting plus rapide.

Approche :
- un sous-réseau privé (ex : `192.168.X.0/24`),
- adresses fixes par rôle :
  - passerelle : `.10`
  - FPGA : `.20`
  - STM32 entrée : `.30`
  - STM32 sortie : `.31`

Règle importante :
- ne pas mélanger DHCP labo avec LAN parking en test.
- isoler pour éviter conflits.

---

## 4) Modèle MQTT sur Ethernet

Le STM32 est client MQTT sur TCP/IP.

### Comportement
- connexion vers broker via IP/hostname connu,
- subscribe aux topics du rôle (commandes/autorisations),
- publish télémétrie et événements (UID RFID, état ascenseur, heartbeats).

### Propriétés attendues
- reconnexion avec backoff si broker down,
- heartbeat ou “last will” pour liveness,
- files bornées pour éviter pression mémoire sous storms reconnexion.

---

## 5) Checklist bring-up (terrain)

Quand “Ethernet ne marche pas” :

1. **Physique**
   - câble OK, switch alimenté,
   - LEDs lien sur carte et switch.

2. **Adressage**
   - IP/mask/gateway corrects,
   - pas de conflit IP.

3. **Broker**
   - broker up sur passerelle et bind LAN,
   - topics visibles depuis un client MQTT sur PC du LAN.

4. **Côté STM32**
   - heartbeat publié après boot,
   - subscriptions actives (commandes reçues en test).

5. **Sanité trafic**
   - pas de boucle publish,
   - pas de flood dû à reconnect mal réglé.

---

## 6) Méthode de test (pratique SysPark)

### A) Test connectivité
- PC sur le LAN.
- Broker joignable.
- Subscribe aux topics STM32 et vérifier heartbeats.

### B) Validation réception TCP
- Vérifier réception/parsing fiable.
- S’assurer que la réception ne bloque pas les threads critiques.

### C) Test MQTT bout-en-bout
- Publier une commande test sur un topic subscribed.
- Vérifier :
  - réception STM32,
  - réaction machine d’états,
  - publication ack.

### D) Test stabilité longue durée
- Laisser tourner plusieurs heures.
- Vérifier pas de croissance mémoire, pas de deadlocks, heartbeats stables.

---

## 7) Pannes fréquentes

### Lien OK mais pas de trafic
- mauvais IP/mask,
- broker pas joignable (mauvaise adresse),
- VLAN/isolation port (rare sur switch simple).

### Marche puis plante
- pression mémoire (queues non bornées),
- SD bloque thread réseau,
- storms reconnexion affament d’autres threads.

### Déconnexions aléatoires
- bruit alim sur équipements,
- câble mal tenu,
- câbles non blindés près des drivers moteurs.

---

## 8) Intégration avec le reste SysPark

Ethernet STM32 doit coexister avec :
- contrôle moteur,
- UI,
- contraintes sûreté.

Comportement correct :
- perte réseau ne déclenche pas d’actionnement dangereux,
- mode dégradé clair,
- UI indique la perte de connectivité.

