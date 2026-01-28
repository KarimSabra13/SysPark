Language: Français | [English](../../en/ai-vision/models.md)

# Modèles vision et stratégie d’inférence (SysPark)

Le module vision SysPark est organisé en pipeline. Plutôt qu’un modèle “end-to-end” unique, SysPark sépare :
1) localisation plaque,
2) OCR caractères,
3) post-traitement (normalisation/validation).

Cette approche modulaire simplifie le debug terrain et permet un fallback propre lorsque la confiance est faible.

---

## 1) Blocs modèles (conceptuels)

### 1.1 Modèle détection plaque (localisation)
But :
- trouver la zone plaque dans l’image.

Sorties :
- bounding box (x, y, w, h),
- confiance détection.

Attendus terrain :
- robustesse angle, occlusion partielle, glare,
- détection stable en plan “voie” (plaque assez grande).

### 1.2 Modèle OCR (caractères)
But :
- lire les caractères dans le crop plaque.

Sorties :
- une ou plusieurs strings candidates,
- confiance par candidat.

Attendus :
- gérer variabilité police et espacement,
- fonctionner sous compression et flou modéré,
- éviter hallucinations sur-confiantes.

### 1.3 Post-traitement (règles)
But :
- transformer l’OCR brut en plaque propre.

Opérations :
- majuscules,
- suppression espaces/séparateurs,
- rejet caractères invalides,
- heuristiques de format prudentes.

Sorties :
- plaque normalisée,
- flag validité,
- score confiance final.

---

## 2) Stratégie confiance (décider quand “faire confiance”)

SysPark traite la vision comme probabiliste.

### 2.1 Composition confiance
La confiance finale peut combiner :
- confiance détection,
- confiance OCR (meilleur candidat),
- accord entre frames (stabilité temporelle),
- validité format.

Logique conceptuelle :
- même plaque sur N frames → boost confiance,
- format invalide → cap confiance.

### 2.2 Seuils
Définir :
- `LOW` : en dessous, ne pas utiliser automatiquement.
- `HIGH` : au-dessus, utilisation auto pour matching session.
- entre LOW et HIGH : résultat “suggestion” à confirmer.

Les seuils sont à calibrer par site (caméra/éclairage dominent).

---

## 3) Inférence multi-frames (stabilité)

Recommandation :
- capturer une rafale courte autour du trigger,
- détection + OCR par frame,
- agrégation :
  - vote majoritaire sur la string,
  - boost si consensus fort,
  - rejet outliers.

Bénéfices :
- réduit glitches single-frame,
- atténue flou/reflets transitoires.

Contraintes :
- budget CPU compatible usage voie,
- ne pas bloquer en attendant trop de frames.

---

## 4) Contraintes déploiement (réalité edge)

### 4.1 Budget latence
Résultat assez rapide pour :
- matching session sortie,
- prompts UI.

Si trop lent :
- renvoyer “unknown” et fallback RFID/PIN,
- ne pas bloquer.

### 4.2 Ressources
Sur edge :
- concurrence avec MQTT, streaming (si activé), services.
- mémoire stable sur longues durées.

### 4.3 Conditions environnement
Facteurs :
- variation nuit/jour,
- glare/reflets,
- plaques sales,
- pluie/brouillard,
- vibrations.

La stratégie doit les anticiper.

---

## 5) Contrat de sortie (ce qu’un résultat doit inclure)

Champs minimum à publier :
- voie (entrée/sortie),
- plaque normalisée,
- score confiance,
- validité,
- timestamp.

Optionnel :
- top-K candidates,
- frame id,
- bbox (debug).

Règles :
- payload MQTT léger,
- pas d’images brutes sur MQTT.

---

## 6) Validation (sans code)

Validation via scénarios proches terrain.

### 6.1 Acquisition samples
Collecter :
- jour/nuit,
- véhicules variés,
- vitesses différentes,
- scénarios glare.

### 6.2 Métriques
Suivre :
- taux succès détection,
- taux match OCR exact,
- calibration confiance (haute confiance rarement fausse),
- temps de réponse.

### 6.3 Acceptance sur site
Pipeline accepté quand :
- les résultats haute confiance sont rarement faux,
- faible confiance ne bloque pas le flow,
- fallback reste utilisable,
- taux intervention opérateur diminue.

---

## 7) Politique gestion d’échec

Si vision échoue ou incertaine :
- publier événement avec `valid=false` ou faible confiance,
- éviter retries agressifs qui chargent la machine,
- fallback RFID/PIN/opérateur.

La vision ne doit jamais provoquer un actionnement non sûr.

