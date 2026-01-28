Language: Français | [English](../../en/ai-vision/pipeline.md)

# Pipeline IA / Vision (lecture de plaque)

SysPark intègre un module IA/Vision optionnel pour la **lecture de plaque (LPR/ANPR)** et l’enrichissement des flows du parking avec un signal d’identification supplémentaire. Le module vision tourne en edge (sur site), publie les résultats sur MQTT, puis s’intègre au Cloud pour rattacher un véhicule à une session lorsque nécessaire.

Principes :
- La vision améliore l’automatisation, mais **ne doit jamais être un point de défaillance**.
- La voie doit fonctionner avec des fallback (RFID/PIN/opérateur).
- Un résultat vision est probabiliste et doit inclure une **confiance**.

---

## 1) Place du module vision

### Exécution sur site
Le pipeline tourne sur la passerelle edge (ou un nœud compute dédié) et interagit avec :
- capture caméra (entrée/sortie),
- broker MQTT local (publication résultats),
- orchestration (machine d’états),
- backend cloud (matching session, contexte facturation).

### Responsabilités
- capture image/frames,
- détection zone plaque,
- OCR caractères,
- normalisation + validation format,
- calcul confiance,
- publication événements sur le bus système.

---

## 2) Étapes du pipeline

### Étape A : Capture
Entrée :
- photo sur trigger (présence détectée), ou
- rafale courte de frames autour du trigger.

Recommandations :
- plusieurs frames augmentent la probabilité de succès,
- exposition stable (éviter flou),
- timestamp systématique.

### Étape B : Détection plaque (localisation)
But :
- trouver la région de plaque.

Sortie :
- bounding box(es),
- confiance détection.

Notes :
- gérer plusieurs détections (reflets, faux positifs),
- garder le meilleur candidat sans perdre les métadonnées si possible.

### Étape C : OCR (reconnaissance caractères)
But :
- lire les caractères dans le crop plaque.

Sortie :
- string OCR brut,
- confiance OCR (par candidat).

Notes :
- confusions fréquentes (O/0, I/1, B/8).
- plusieurs frames stabilisent souvent le résultat.

### Étape D : Normalisation et validation
But :
- produire une plaque propre exploitable.

Opérations typiques :
- passage en majuscules,
- suppression espaces/séparateurs,
- rejet caractères illégaux,
- règles de format par pays (optionnel),
- corrections heuristiques prudentes.

Sortie :
- `plate_normalized`,
- `format_valid` (bool),
- `final_confidence` (score combiné).

### Étape E : Publication MQTT
Publication événement avec :
- plaque normalisée,
- score confiance,
- timestamp,
- identifiant voie (entrée/sortie),
- optionnel : id frame, bbox (pas requis pour flow cœur).

---

## 3) Contrat MQTT (événements vision)

Deux approches possibles :

### Option A : topic vision dédié
- `parking/vision/plate`

### Option B : topics par voie
- `parking/entry/vision/plate`
- `parking/exit/vision/plate`

Payload (JSON recommandé) :
- `ts` : timestamp
- `src` : `vision`
- `lane` : `entry` ou `exit`
- `plate` : plaque normalisée
- `confidence` : score (0..1 ou 0..100, rester cohérent)
- `valid` : bool
- optionnel : `frame_id`, `bbox`, `candidates` (optionnel pour garder payload léger)

QoS :
- QoS 1 recommandé

Retain :
- Non (événement, pas un état)

---

## 4) Usage plaque dans les flows SysPark

### Flow entrée (amélioration optionnelle)
Usages possibles :
- rattacher la plaque à une nouvelle session,
- second facteur en plus du RFID,
- réduire interventions opérateur.

Règles :
- faible confiance ne doit pas bloquer l’entrée.
- si RFID présent, RFID reste l’identifiant primaire stable.

### Flow sortie (forte valeur)
Usage principal :
- retrouver la session correspondante et calculer le tarif.

Règles :
- la plaque sert au matching,
- l’autorisation paiement reste validée côté cloud,
- fallback obligatoire si lecture plaque échoue.

---

## 5) Seuils confiance et fallback

Définir au moins deux seuils :

### Seuil haute confiance
Si `confidence >= HIGH` et `valid == true` :
- matching auto session,
- flow automatisé normal.

### Seuil moyenne confiance
Si `LOW <= confidence < HIGH` :
- résultat “suggestion” :
  - affichage dashboard opérateur,
  - confirmation via RFID/PIN.

### Seuil basse confiance
Si `confidence < LOW` ou `valid == false` :
- ne pas utiliser pour décision automatique,
- fallback RFID/PIN/opérateur.

Important :
- seuils à ajuster selon caméra et éclairage.
- ne pas sur-confiance OCR.

---

## 6) Contraintes terrain (positionnement et lumière)

La qualité dépend fortement :
- taille plaque en pixels,
- angle et perspective,
- nuit, glare/reflets,
- flou de mouvement,
- plaques sales/occlusions.

Recommandations :
- caméra fixe et framing stable par voie,
- crop suffisamment proche,
- éclairage constant si nécessaire,
- lentille propre.

---

## 7) Notes vie privée et conformité

Les plaques sont des données personnelles dans beaucoup de contextes. Bonnes pratiques :
- éviter stockage frames brutes sauf debug nécessaire,
- si snapshots stockés : accès restreint + rétention limitée,
- préférer stocker plaque normalisée + confiance,
- masquage possible côté dashboard selon politique.

---

## 8) Checks d’acceptance

Intégration validée quand :
- publication événements plaque structurés sur MQTT,
- seuils confiance cohérents (pas de blocage en faible confiance),
- flow sortie peut matcher en haute confiance,
- système utilisable si vision désactivée ou en panne.

