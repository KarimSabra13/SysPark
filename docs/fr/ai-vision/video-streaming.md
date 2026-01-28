Language: Français | [English](../../en/ai-vision/video-streaming.md)

# Streaming vidéo (maintenance et debug)

SysPark peut exposer un flux vidéo live pour la maintenance, l’alignement caméra et le debug du pipeline vision. Le streaming n’est pas requis pour le fonctionnement normal. C’est un outil d’exploitation qui doit respecter des règles strictes de sécurité et de vie privée.

Règle centrale :
- **Aucun endpoint public.**
- Le flux est accessible uniquement via un canal maintenance sécurisé (VPN overlay) et uniquement quand nécessaire.

---

## 1) Objectif

### Pourquoi un flux vidéo
- Valider cadrage et focus pendant l’installation.
- Debug des échecs vision (reflets, flou, angle plaque).
- Maintenance à distance quand l’accès physique caméra est difficile.

### Ce que le streaming n’est pas
- Pas une feature client.
- Pas un monitoring permanent.
- Pas une dépendance sûreté.

---

## 2) Modèle d’accès (VPN uniquement)

Le flux ne doit être accessible que dans le réseau maintenance sécurisé :
- VPN overlay (ex : Tailscale),
- membership devices restreinte,
- pas de port forwarding sur la box site.

Approche recommandée :
- serveur de stream sur la passerelle Edge,
- accès limité aux identités VPN autorisées.

---

## 3) Procédure exploitation (workflow sûr)

1. Activer le streaming uniquement sur une fenêtre maintenance.
2. Vérifier que la voie est en état sûr (pas de mouvement dangereux).
3. Se connecter via VPN et ouvrir l’endpoint stream.
4. Faire l’alignement ou observation debug.
5. Désactiver le streaming après intervention.

Si accès distant indisponible :
- basculer sur procédure sur site.

---

## 4) Vie privée et conformité

Les images peuvent contenir :
- plaques,
- visages,
- identifiants véhicule.

Principes :
- pas d’enregistrement par défaut,
- accès strictement limité aux mainteneurs autorisés,
- si snapshots stockés :
  - politique de rétention,
  - accès restreint,
  - résolution minimale et fenêtre temporelle minimale.

Les interfaces opérateur doivent éviter d’afficher des données personnelles complètes si ce n’est pas requis.

---

## 5) Contraintes réseau et performance

Le streaming consomme bande passante et ressources edge.
Guidelines :
- résolution et fps modérés pour debug,
- ne pas affamer MQTT/vision,
- service optionnel, désactivable facilement.

---

## 6) Modes défaillance

### Stream indisponible
- le parking doit continuer normalement.
- le pipeline vision doit tourner sans le streaming.

### Réseau instable
- qualité flux dégradée, mais sûreté inchangée.
- éviter storms reconnexion qui chargent la machine.

### Mauvaise config sécurité
- si impossibilité VPN-only, ne pas activer.
- défaut “fermé”.

---

## 7) Critères d’acceptance

Intégration OK si :
- accès flux uniquement via VPN,
- activation/désactivation rapide,
- respect vie privée (pas d’enregistrement non contrôlé),
- flows parking non impactés.

