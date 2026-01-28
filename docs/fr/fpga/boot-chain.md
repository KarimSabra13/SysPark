Language: Français | [English](../../en/fpga/boot-chain.md)

# Chaîne de boot du nœud FPGA (LiteX BIOS → OpenSBI → Linux)

Le nœud exécution FPGA SysPark lance Linux sur un SoC RISC-V soft généré avec LiteX. Pour rendre le système fiable et explicable, la chaîne de boot est explicitée : chaque étape a un rôle clair et charge la suivante.

Idée globale :
- le bitstream FPGA crée le SoC,
- un boot minimal initialise la plateforme,
- le kernel Linux boote avec DTB et rootfs.

---

## 1) Composants de la chaîne (rôles)

### 1.1 Bitstream FPGA (étape matériel)
- Programme le FPGA avec le design SoC LiteX.
- Définit :
  - cœur CPU,
  - map mémoire,
  - périphériques CSR,
  - DDR + clocking,
  - UART, Ethernet (si activé), etc.

Sans bitstream, rien n’existe côté logiciel.

### 1.2 LiteX BIOS (monitor de boot)
Premier logiciel exécuté. Il :
- initialise clocks et interfaces mémoire,
- fournit une console série,
- charge des binaires depuis un stockage (souvent SD),
- transfère l’exécution à l’étape suivante.

### 1.3 OpenSBI (runtime supervisor RISC-V)
OpenSBI fournit les services “Supervisor Binary Interface” nécessaires à Linux en mode supervisor. Il :
- gère des services bas niveau,
- fournit un environnement standard pour Linux sur RISC-V.

Dans cette chaîne :
- LiteX BIOS charge OpenSBI,
- OpenSBI lance le kernel Linux.

### 1.4 Kernel Linux (+ Device Tree)
Linux a besoin :
- de l’image kernel,
- d’un DTB décrivant le hardware (map mémoire, périphériques),
- d’arguments boot (console, rootfs, etc.).

Le DTB doit correspondre au bitstream FPGA. Sinon, les périphériques et l’adressage cassent.

### 1.5 Root filesystem (initramfs)
SysPark boote souvent avec initramfs :
- rootfs compressé embarqué ou chargé avec le kernel,
- userspace minimal (MQTT, daemon contrôle),
- déploiement simple sans partition persistante complexe.

---

## 2) Séquence “qui charge quoi”

Séquence pratique SysPark :

1. Charger le bitstream FPGA (le SoC apparaît).
2. Reset / démarrage CPU vers LiteX BIOS.
3. LiteX BIOS charge :
   - OpenSBI,
   - kernel,
   - DTB,
   - initramfs (si séparé).
4. LiteX BIOS jump vers OpenSBI.
5. OpenSBI boote Linux.
6. Linux lance l’userspace (initramfs) et les services SysPark.

---

## 3) Rôle de la carte SD (stockage boot)

En boot SD, la SD contient :
- image OpenSBI,
- kernel,
- DTB,
- initramfs (si séparé).

Guideline :
- layout et noms stables,
- doc claire pour recovery rapide.

---

## 4) Dépendance critique : DTB ↔ bitstream

Le DTB décrit :
- adresses UART,
- bases CSR,
- présence MAC Ethernet,
- interrupts,
- taille mémoire.

Si on modifie le design FPGA et rebuild le bitstream :
- il faut généralement régénérer le DTB.

Symptômes mismatch :
- Linux boote mais périphériques KO,
- initramfs ne démarre pas correctement,
- adresses CSR utilisées par les services sont fausses.

Toujours lier un build bitstream à son DTB.

---

## 5) Pourquoi initramfs (raison SysPark)

Initramfs car :
- déploiement le plus simple en démo,
- pas de root partition persistante,
- boot rapide et reproductible,
- inclure seulement les outils nécessaires.

Trade-off :
- update rootfs = rebuild/remplacer initramfs.

---

## 6) Checks opérationnels (sanity)

Chaîne saine si :
- prompt BIOS visible sur UART,
- banner OpenSBI,
- logs kernel Linux,
- initramfs lance les services attendus,
- CSR control OK (barrière).

---

## 7) Patterns de panne

### Pas de sortie BIOS
- bitstream absent,
- mauvais UART/baud,
- problème alim/clock.

### BIOS OK mais Linux plante tôt
- kernel/DTB/initramfs manquants sur SD,
- mauvais noms fichiers,
- SD corrompue.

### Linux boote mais périphériques absents
- mismatch DTB/bitstream,
- map CSR incorrecte.

### Linux OK mais contrôle SysPark KO
- services non démarrés,
- MQTT absent,
- adresses CSR mauvaises.

