Language: Français | [English](../../en/hw/power-bms.md)

# Architecture puissance et BMS

SysPark intègre des moteurs et plusieurs nœuds de calcul. La puissance doit couvrir :
- les pics moteurs
- une alimentation 5 V stable pour le compute
- la sûreté en cas de défaut câblage
- une démo reproductible

Ce document décrit l’architecture puissance et le rôle du BMS au niveau système.

---

## 1) Objectifs puissance

- Fournir un 5 V stable pour compute et périphériques
- Fournir un rail 12 V classe démo pour moteurs et charges fortes
- Prévenir les situations dangereuses
  - sur-courant
  - sur-tension
  - sous-tension
  - court-circuit
- Simplifier le câblage pour bring-up rapide

---

## 2) Rails SysPark

### Rail principal
- rail batterie (classe 12 V en démo)

### Rails distribution
- 12 V vers drivers moteurs et modules puissance
- 5 V pour passerelle, FPGA, STM32, capteurs et displays

### Rails locaux
- 3.3 V généré localement sur les cartes ou via petits régulateurs
- utilisé pour RFID, capteurs, logique I/O

---

## 3) Batterie et bloc BMS

### Pack batterie
- pack classe LiFePO4 en source principale démo
- dimensionné pour
  - consommation compute
  - pics moteurs
  - durée démo

### Rôle BMS
Le BMS protège le pack et le système :
- protection sur-courant
- protection court-circuit
- coupure sous-tension pour protéger les cellules
- équilibrage des cellules
- télémétrie optionnelle
  - tension pack et courant
  - tensions cellules
  - température

SysPark retient une solution BMS adaptée à :
- le nombre de cellules en série
- le courant peak attendu
- la simplicité câblage pour la maquette

Référence
- references/pdf/BMS.pdf

---

## 4) Conversion DC-DC

### Module 12 V vers 5 V fort courant
- DC-DC fort courant pour générer le bus 5 V depuis la batterie
- règles de dimensionnement
  - somme des charges 5 V
  - marge pour pics de boot et bruit moteur
  - marge thermique

Règles intégration
- DC-DC proche du point distribution
- conducteurs épais sur segments forts courants
- retours masse faible impédance

---

## 5) Protection et sûreté câblage

Chaîne protection recommandée
- plus batterie
- fusible principal proche pack
- BMS
- nœud distribution
- fusibles par branche si possible

Ajouter selon besoin
- protection inversion polarité
- TVS transitoires sur câbles longs
- strain relief sur parties mobiles

---

## 6) Masse et bruit

Les moteurs injectent du bruit. Règles simples :
- masse en étoile au nœud distribution
- séparer retours moteurs des retours compute si possible
- torsader les câbles moteurs
- éloigner Ethernet des drivers pas-à-pas
- découplage proche drivers et cartes sensibles

---

## 7) Règles mise sous tension

Power-up
- démarrer DC-DC
- valider 5 V stable sous charge
- booter les nœuds compute
- activer actionnement seulement après

Power-down
- désactiver actionnement
- arrêter les nœuds si besoin
- couper l’alimentation

---

## 8) Mesures à conserver

Mesurer sur banc :
- tension batterie au repos et sous charge moteur
- tension 5 V au bout du faisceau
- courant peak pendant mouvement barrière
- température DC-DC en longue durée
- seuils coupure BMS en faible batterie

Ces mesures évitent les resets cachés.

