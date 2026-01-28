Language: Français | [English](../../en/hw/wiring-topology.md)

# Topologie de câblage et faisceaux

Le câblage SysPark se sépare en deux catégories :
- puissance pour batterie, DC-DC et moteurs
- signaux pour Ethernet et I/O basse tension

Ce document donne une stratégie câblage propre pour une démo fiable.

---

## 1) Principe de layout

Séparer physiquement les blocs :
- bloc puissance
  - batterie, BMS, DC-DC, fusible
- bloc compute
  - passerelle, FPGA, STM32, switch
- bloc actionnement
  - drivers moteurs, moteurs, fins de course, mécanismes
- bloc vision
  - caméra et support

Cela réduit le couplage bruit et simplifie le debug.

---

## 2) Câblage Ethernet

Topologie préférée
- un petit switch Ethernet sur la maquette
- connexions en étoile
  - passerelle
  - FPGA
  - STM32 entrée
  - STM32 sortie
  - PC opérateur optionnel

Règles
- câbles courts et fixés
- éviter Ethernet proche des drivers pas-à-pas
- étiqueter chaque câble par rôle

---

## 3) PMOD FPGA (actionnement et capteurs)

Le PMOD est sensible à l’ordre des pins.

Bonnes pratiques
- un PMOD dédié sorties vers drivers
- un PMOD dédié entrées capteurs
- convention couleurs cohérente
  - power
  - ground
  - signaux 0..7

Checks intégration
- test continuité de chaque ligne
- valider sens IN ou OUT
- éviter entrées flottantes

---

## 4) Drivers et moteurs

Exemple chaîne pas-à-pas
- sorties FPGA vers entrées driver
- sorties driver vers phases moteur

Règles
- torsader les câbles moteurs
- éloigner des câbles Ethernet et caméra
- strain relief près des parties mobiles
- protection mécanique contre frottement câble

---

## 5) Câblage STM32

Câblage typique par nœud
- Ethernet
- interface lecteur RFID
- écrans UI
- interface driver moteur lift
- fin de course et entrées sûreté

Règles
- séparer faisceaux puissance et signaux
- éviter longues lignes non blindées pour fins de course
- pull-up ou pull-down pour éviter entrées flottantes

---

## 6) Caméra et vision

Règles
- montage stable, limiter vibrations
- câble caméra séparé des câbles moteurs
- éviter angles de pliage trop serrés
- protéger la lentille et la nettoyer

---

## 7) Distribution puissance

Structure faisceau recommandée
- tronc fort courant court batterie vers distribution
- branches vers
  - DC-DC
  - drivers moteurs
  - distribution 5 V compute

Règles
- fusible proche batterie
- câbles épais sur segments forts courants
- connecteurs fiables et bien dimensionnés
- polarité clairement marquée

---

## 8) Étiquetage et maintenance

Tout étiqueter
- branches puissance
- câbles Ethernet
- moteurs et drivers
- capteurs

Kit service
- fusibles
- câble Ethernet
- jumpers
- multimètre

---

## 9) Checklist acceptance

- aucun fil libre proche des mécanismes mobiles
- actionnement OK sans perturber Ethernet
- Ethernet stable pendant mouvement moteur
- aucun reset au démarrage moteur
- BMS ne déclenche pas en pics normaux
- tous les nœuds bootent et publient heartbeats

