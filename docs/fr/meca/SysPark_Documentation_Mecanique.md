# SysPark - Documentation Mécanique (Impression 3D)

Ce répertoire contient l'ensemble des fichiers de conception mécanique nécessaires à l'assemblage physique du système de parking **SysPark**.  
Toutes les pièces ont été conçues pour être fabriquées via **impression 3D (FDM)**.

## 📂 Contenu du dossier

Le projet est divisé en quatre sous-ensembles principaux.

### 1. Support principal (STM32 + RFID + LCD)

**Dossier**  
`Support stm+rfid+lcd`

**Description**  
Châssis central du nœud de contrôle. Il permet de fixer solidement la carte **STM32F746G-DISCO**, le lecteur de badges **RFID RC522** et l'écran LCD intégré.

**Usage**  
Unité d'interface utilisateur à l'entrée et à la sortie du parking.

### 2. Support Écran OLED (Ascenseur)

**Dossier**  
`Ecran OLED ascenseur`

**Description**  
Boîtier compact conçu pour accueillir l'écran OLED déporté **SSD1306**.

**Usage**  
Fixation sur la structure de l'ascenseur afin d'indiquer l'étage ou le statut du véhicule.

### 3. Supports Caméras

Le système utilise deux types de supports selon la technologie de vision employée.

**Caméra CSI**  
Support optimisé pour les caméras à nappe de type **Raspberry Pi** ou **BeagleY-AI**, idéal pour la reconnaissance de plaques en pose fixe.

**Caméra Logitech**  
Support universel adapté aux webcams USB **Logitech** (C170, C920) pour une surveillance grand angle.

## 🛠 Paramètres d'Impression Recommandés

Afin de garantir la solidité mécanique et la précision des emboîtements, notamment pour les connecteurs USB de la STM32, les paramètres suivants sont recommandés.

**Matériau**  
PLA ou PETG. Le PETG est conseillé si le système est exposé à la chaleur.

**Hauteur de couche**  
0.2 mm.

**Remplissage (Infill)**  
15 % à 20 %, motif Gyroid ou Grille.

**Supports**  
Généralement non requis pour le support STM32. Ils peuvent être nécessaires pour certains supports caméras selon l'orientation d'impression.

**Brim / Bordure**  
Recommandé pour les pièces larges afin d'éviter le warping et le décollement des coins.

## 🔧 Instructions d'Assemblage

**Préparation**  
Nettoyer les restes de supports et vérifier l'ébavurage des trous de fixation.

**Montage électronique**  
La carte STM32 se fixe sur ses plots à l'aide de vis M3 de 6 mm à 10 mm.  
Le lecteur RFID se glisse ou se visse dans son logement dédié en vérifiant l'alignement de l'antenne.

**Fixation caméra**  
Les supports caméras sont conçus pour être orientables. Les vis de pivot doivent être serrées une fois l'angle de vue optimal obtenu.

**Intégration OLED**  
L'écran OLED doit être inséré délicatement afin d'éviter toute casse de la dalle en verre. Une fixation par clips ou un point de colle chaude est prévue selon la version du fichier.

## 📝 Format des fichiers

**STL**  
Fichiers directement importables dans les slicers tels que Cura, PrusaSlicer ou Bambu Studio.

**Note**  
Les fichiers sources CAD peuvent être ajoutés sur demande pour permettre la modification des tolérances ou des dimensions.
