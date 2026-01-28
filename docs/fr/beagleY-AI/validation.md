Language: Français | [English](../../en/ai-vision/validation.md)

# Plan de validation vision (orienté terrain)

Ce document définit un plan de validation pratique pour le module lecture plaque SysPark. L’objectif n’est pas d’avoir un OCR parfait partout, mais de garantir un comportement correct :
- **les sorties haute confiance sont suffisamment fiables pour automatiser le matching session**,
- **les sorties faible confiance ne bloquent jamais la voie**,
- **les fallbacks restent fluides**,
- performance stable sur longue durée.

---

## 1) Objectifs validation

### Objectifs principaux
- Vérifier la publication end-to-end des événements plaque sur MQTT.
- Vérifier le bon comportement des seuils de confiance.
- Vérifier le gain opérationnel à la sortie (moins d’interventions opérateur).
- Vérifier que le système reste utilisable et sûr si la vision échoue.

### Objectifs secondaires
- Caractériser le comportement selon lumière/météo.
- Identifier contraintes placement caméra et qualité minimale.
- Définir tests régression pour éviter les dégradations.

---

## 2) Environnements de test (set recommandé)

Pour éviter un biais “lab only” :

### A) Lab / indoor contrôlé
- lumière stable,
- distances répétables,
- utile pour debug initial.

### B) Voie réaliste outdoor
- jour + nuit,
- variations, glare/reflets,
- angles approche réalistes.

### C) Stress
- véhicules plus rapides,
- conditions météo dégradées si possible,
- faible luminosité.

---

## 3) Scénarios de test

### Scénario 1 : véhicule statique, conditions idéales
- arrêt au point de capture.
But : baseline détection + OCR.

Attendu :
- confiance haute,
- stabilité multi-frames.

### Scénario 2 : approche lente, journée
- léger flou.
But : valider agrégation multi-frames.

Attendu :
- plaque finale cohérente,
- confiance qui augmente avec consensus.

### Scénario 3 : nuit + éclairage artificiel
- faible lumière, glare phares.
But : observer modes d’échec et protection par seuils.

Attendu :
- plus de moyenne/faible confiance,
- aucun blocage voie.

### Scénario 4 : occlusion / plaque sale
- plaque partiellement masquée.
But : éviter hallucinations sur-confiantes.

Attendu :
- faible confiance ou invalid,
- fallback.

### Scénario 5 : reflets / faux positifs
- patterns réfléchissants.
But : valider robustesse du détecteur.

Attendu :
- sélection meilleur candidat stable,
- faux positifs en faible confiance.

### Scénario 6 : matching session sortie
- sessions réelles créées à l’entrée, match à la sortie.
But : mesurer gain opérationnel.

Attendu :
- haute confiance réduit sélection manuelle.

---

## 4) Collecte de données (pratique)

Pour chaque run :
- timestamp,
- voie (entrée/sortie),
- plaque finale + confiance,
- flag validité,
- top candidates (optionnel),
- temps de réponse,
- ground truth noté par opérateur.

Important :
- éviter stockage vidéo complet.
- si frames stockées pour debug : accès et rétention contrôlés.

---

## 5) Métriques

### Métriques précision
- **taux succès détection** : % triggers avec plaque détectée
- **taux OCR exact** : % plaque finale = ground truth
- **précision haute confiance** : quand confiance >= HIGH, % correct
- **utilité moyenne confiance** : % où la bonne plaque apparaît dans les candidats

### Calibration
- **fiabilité confiance** : haute confiance rarement fausse
- **taux faux positifs** : plaques “valides” mais mauvaises

### Performance
- **time-to-result** : trigger → publish
- **CPU** (qualitatif acceptable)
- **stabilité mémoire** sur longue durée

---

## 6) Seuils d’acceptance (orienté déploiement)

Les conditions varient par site. Baseline réaliste :
- précision haute confiance très élevée (rarement faux),
- faible confiance ne bloque jamais le flow,
- temps de réponse compatible usage conducteur,
- stabilité sur plusieurs heures (pas de leaks, pas de crash loop).

Si non atteint :
- ajuster placement caméra et éclairage d’abord,
- puis calibrer seuils.

---

## 7) Checklist régression

À chaque changement (modèles, caméra, paramètres), rerun :
- scénario 1 (baseline),
- scénario 3 (nuit/glare),
- scénario 4 (occlusion),
- matching sortie (end-to-end).

Vérifier aussi :
- contrat payload MQTT inchangé,
- seuils inchangés ou documentés,
- fallback toujours OK.

---

## 8) Règles d’exploitation (interpréter résultats)

- Si précision haute confiance insuffisante → augmenter HIGH.
- Si système trop conservateur → baisser HIGH légèrement, uniquement si précision reste bonne.
- Si faux positifs → renforcer validation format et filtrage.
- Si latence trop élevée → réduire rafale frames ou optimiser pipeline.

---

## 9) Critères “pass” finaux

Vision considérée utilisable quand :
- événements structurés fiables,
- haute confiance suffisamment fiable pour automatiser matching,
- flows fluides en faible confiance,
- le système reste sûr sans dépendre de la vision.

