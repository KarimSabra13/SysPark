Language: Français | [English](../../en/fpga/networking.md)

# Réseau sur le nœud Linux FPGA (LAN + MQTT)

Le nœud FPGA SysPark exécute Linux sur un SoC RISC-V LiteX. Le réseau sert à intégrer le nœud exécution dans le LAN du parking afin de :
- recevoir des commandes d’actionnement (MQTT),
- publier états capteurs/actionneurs,
- participer à la supervision.

Ce document décrit le modèle réseau, les attentes MQTT et les règles de robustesse côté nœud FPGA.

---

## 1) Rôle du réseau sur le nœud FPGA

Le réseau permet au nœud FPGA d’être un service d’exécution fiable :
- subscribe aux topics de contrôle approuvés,
- publish état barrières + diagnostics,
- monitoring opérateur dans le LAN.

Le nœud doit rester sûr même si le réseau est indisponible.

---

## 2) Modèle intégration LAN

### Approche préférée
- Connexion Ethernet au LAN parking.
- IP prédictible (statique ou DHCP réservé).
- Connexion au **broker MQTT local** (souvent sur passerelle edge).

Objectif :
- actionnement temps critique local (CSR),
- réseau = commande/télémétrie, pas boucle temps réel.

---

## 3) Adressage et isolation

### Adressage
Un sous-réseau unique documenté.
Recommandé :
- IP statique en démo,
- DHCP réservé en déploiement géré.

### Isolation
- LAN parking privé,
- pas d’exposition publique des services Linux FPGA,
- cloud uniquement via passerelle edge et bridge.

---

## 4) Responsabilités client MQTT

Le client/service MQTT FPGA doit :

### Subscribe
- topics commandes barrière (open/close),
- topics config si supportés (timeouts, politiques),
- optionnel : sync état global.

### Publish
- état actionneur :
  - open/closed/moving/fault,
- snapshots capteurs :
  - fins de course, présence, entrées faute,
- heartbeat :
  - alive, uptime, dernier code erreur.

### Règles contrat
- topics stricts (pas ad-hoc),
- schéma payload cohérent,
- gestion idempotente des commandes.

---

## 5) Supervision services (robustesse Linux)

Les services Linux doivent être supervisés :
- restart automatique en crash,
- logs bornés (ne pas saturer RAM),
- ordre startup :
  - réseau up → MQTT connect → service contrôle.

En initramfs :
- services lancés via script init clair ou superviseur.

---

## 6) Mode dégradé

### Broker injoignable
- retry avec backoff,
- pas de publish tant que non connecté,
- ne pas maintenir outputs actifs indéfiniment.

### Réseau down
- rester sûr :
  - arrêt mouvement / outputs état sûr,
  - hardware stable.

### Cloud down
- pas directement concerné :
  - dépend du broker local,
  - passerelle gère cloud/bridge.

---

## 7) Attentes sécurité

Minimum :
- le nœud FPGA parle au broker local (adresse LAN),
- secrets hors Git,
- ACL broker pour limiter publish commandes barrière,
- allowlist topics au niveau bridge.

En démo, sécurité simplifiée possible, mais architecture compatible prod.

---

## 8) Checks d’acceptance

Intégration OK si :
- connexion fiable au broker local,
- commandes reçues et actionnement correct,
- état + heartbeat publiés de façon stable,
- pannes (broker/réseau) ne créent pas de comportement dangereux,
- recovery correct après reconnexion.

