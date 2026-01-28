Language: Français | [English](../../en/edge/mqtt-bridge.md)

# Bridge MQTT (Local ↔ Relais Cloud)

SysPark utilise une architecture MQTT hybride : un **broker local** sur le LAN du parking pour la faible latence et le fonctionnement offline, et un **broker public** utilisé comme relais vers le backend Cloud. Le bridge MQTT est le lien contrôlé entre ces deux mondes.

Le bridge est critique en sécurité. Il doit se comporter comme un pare-feu applicatif :
- ne relayer que le nécessaire,
- empêcher les boucles,
- réduire l’exposition,
- garantir la sûreté locale même si le côté public devient bruité ou compromis.

---

## 1) Pourquoi un bridge

### Objectifs
- Garder le parking utilisable sans Internet (le broker local suffit).
- Activer supervision/paiement cloud quand la connectivité est disponible.
- Ne pas exposer le broker local à Internet.
- Contrôler précisément les topics qui traversent la frontière.

### Ce que le bridge n’est pas
- Ce n’est pas un outil “sync tout”.
- Il ne doit pas relayer des topics arbitraires.

---

## 2) Topologie et rôles

### Côté local
- Broker dans le LAN du parking.
- Producteurs : STM32, télémétrie FPGA, capteurs.
- Consommateurs : applis edge (affichage, vision), outils locaux.

### Côté public
- Broker accessible via Internet (TLS).
- Le backend cloud s’y abonne et publie.
- Multi-sites possible via un même broker (modèle multi-tenant).

### Bridge
- Service sur la passerelle Edge.
- Client des deux brokers.
- S’abonne à des topics whitelistés côté A et republie côté B.

---

## 3) Politique de sens (allowlists)

Le bridge définit deux allowlists explicites :

### A) Local → Cloud
Relayer uniquement les états/télémétries utiles :
- présence et événements sûreté,
- snapshots état actionneurs,
- état/liste ACL,
- demandes de resync,
- diagnostics sélectionnés (heartbeats).

Ne jamais relayer :
- debug interne bruyant,
- flux vidéo brut,
- topics haute fréquence non justifiés.

### B) Cloud → Local
Relayer uniquement le plan de contrôle minimal :
- messages d’affichage (optionnel),
- paiement demandé + paiement validé,
- updates configuration contrôlées (ACL),
- commandes actionneurs si la politique l’autorise.

Ne jamais relayer :
- commandes arbitraires via wildcards,
- topics pouvant écraser la logique d’état sûr locale.

---

## 4) Prévention de boucles

Obligatoire car :
- les deux côtés peuvent publier des noms identiques,
- le bridge peut créer des boucles infinies.

Stratégies recommandées :
- allowlists en correspondance exacte (pas de wildcards larges).
- tag `src` et drop des messages déjà republiés par le bridge.
- “ownership” par topic :
  - topics appartenant au local (uniquement vers le haut),
  - topics appartenant au cloud (uniquement vers le bas).

---

## 5) QoS et retain en environnement bridgé

### QoS
- Rester cohérent avec le contrat topic.
- Pour commandes/alertes : QoS 1 ou 2 possible, mais :
  - traitement idempotent des doublons,
  - présence d’un identifiant session/corrélation.

### Retain
- Éviter retain sur les commandes côté broker public.
- Préférer retain des derniers états côté local.
- Si retain côté public, vérifier qu’un état ne déclenche pas une action à lui seul.

---

## 6) Authentification et chiffrement

Minimum :
- TLS vers le broker public.
- Identifiants bridge uniques par site.
- Pas de connexions publiques entrantes vers le LAN.
- Secrets via variables d’environnement (pas dans Git).

Recommandé prod :
- user/pass distincts par site et par sens,
- ACL broker (droits publish/subscribe),
- limitation de débit côté broker.

---

## 7) Comportement en panne

### Broker public injoignable
- retry avec backoff.
- broker local OK → mode LAN continue.
- fonctions cloud dégradées (paiement/supervision).

### Broker local injoignable
- bridge inopérant ; système en mode restreint.
- recommandation : supervision broker local + auto-restart.

### Backend cloud injoignable
- broker public peut rester joignable mais pas de décisions.
- site continue en mode offline si supporté.

---

## 8) Checklist exploitation

Avant activation :
- broker local bind LAN uniquement (pas public).
- TLS broker public validé.
- allowlists minimales et revues.
- prévention boucles validée (pas de tempête).
- sûreté : si le bridge tombe, pas de comportement dangereux.

---

## 9) Liens doc

- Architecture : `docs/fr/overview/architecture.md`
- Contrat MQTT : `docs/fr/cloud/mqtt-topics.md`
- Edge overview : `docs/fr/edge/beagley-ai.md`

