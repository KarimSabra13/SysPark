# SysPark : Guide d'Implémentation du Nœud BeagleY-AI

## 1. Le Cœur Matériel : Analyse de la BeagleY-AI

Le choix de la plateforme matérielle est déterminant pour la viabilité d'une solution Edge AI. La **BeagleY-AI** a été sélectionnée pour SysPark en raison de son architecture hétérogène unique, offrant un équilibre optimal entre puissance de calcul généraliste et accélération matérielle spécialisée.

### 1.1 Spécifications Techniques et Pertinence pour SysPark

La BeagleY-AI repose sur le System-on-Chip (SoC) **Texas Instruments AM67A** (J722S), une puce conçue spécifiquement pour la vision industrielle et l'IA embarquée.<sup>12</sup>

| **Composant**                  | **Spécification**                           | **Rôle dans SysPark**                                                                                                                                                                                                   |
|--------------------------------|---------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **CPU Application**            | Quad-core Cortex-A53 @ 1.4 GHz (64-bit)     | Exécution de l'OS Linux (Debian/TI Edge AI), du runtime Python, du broker MQTT et du serveur Web Flask. C'est le chef d'orchestre généraliste.                                                                          |
| **Accélérateur IA (DSP)**      | C7x DSP + MMA (Matrix Multiply Accelerator) | Capable de délivrer jusqu'à 4 TOPS (Trillions d'Opérations par Seconde). Il est dédié à l'inférence des réseaux de neurones profonds (YOLO) pour la détection de véhicules et de plaques, déchargeant le CPU principal. |
| **Processeur de Vision (ISP)** | VPAC (Vision Processing Accelerator)        | Unité critique pour le pipeline vidéo. Elle traite le flux brut (RAW Bayer) des caméras, gère la balance des blancs, l'exposition automatique (AE) et la conversion de format (Demosaicing), sans latence CPU.          |
| **Microcontrôleurs TR**        | Cortex-R5F (x2)                             | Coeurs temps réel dédiés. Bien que SysPark utilise un STM32 externe, ces cœurs gèrent en interne la gestion de l'énergie et certains périphériques bas niveau du SoC.                                                   |
| **Mémoire**                    | 4 Go LPDDR4                                 | Suffisant pour stocker les modèles d'IA, les buffers vidéo GStreamer et l'OS complet.                                                                                                                                   |
| **Connectivité**               | Wi-Fi 6, Bluetooth 5.4, Gigabit Ethernet    | Assure la liaison vers le Cloud (via Wi-Fi/Ethernet) et potentiellement vers des capteurs BLE futurs.                                                                                                                   |

Contrairement à une Raspberry Pi 4 ou 5 qui dépend fortement de son GPU VideoCore et de son CPU pour le traitement d'image, l'AM67A dispose de pipelines matériels dédiés (VPAC + DMPAC) qui permettent un traitement d'image déterministe et une consommation énergétique maîtrisée, crucial pour un boîtier de parking pouvant être exposé à la chaleur.

### 1.2 Topologie des Entrées/Sorties (Pinout) et Câblage

L'intégration physique de la BeagleY-AI dans le boîtier SysPark nécessite une compréhension précise du connecteur d'extension 40 broches. Bien que compatible physiquement avec le standard HAT Raspberry Pi, le multiplexage des broches (PinMux) sur le SoC TI AM67A est spécifique et nécessite une configuration logicielle précise via les "Device Tree Overlays".<sup>34</sup>

**Avertissement Critique** : Les niveaux logiques des GPIOs de la BeagleY-AI sont strictement en **3.3V**. Toute connexion directe avec des périphériques 5V (fréquents dans l'industrie ou sur Arduino/STM32 anciens modèles) sans adaptation de niveau (Level Shifter) entraînera la destruction immédiate du port GPIO, voire du SoC complet.<sup>5</sup>

#### 1.2.1 Le Bus SPI (Affichage LED Matriciel)

L'affichage des messages ("LIBRE", "COMPLET", Météo) est assuré par une chaîne de matrices LED pilotées par le contrôleur MAX7219. Ce composant utilise une interface série synchrone SPI (Serial Peripheral Interface). Sur la BeagleY-AI, nous exploitons le bus **SPI0** mappé pour correspondre au standard Raspberry Pi.<sup>6</sup>

-   **MOSI (Master Out Slave In) - Pin 19 (GPIO 10)** : C'est la ligne de données principale. La BeagleY-AI (Maître) envoie les commandes d'allumage des pixels aux modules LED (Esclaves). Le script bandeau_led.py écrit des trames binaires sur cette ligne.<sup>1</sup>

-   **SCLK (Serial Clock) - Pin 23 (GPIO 11)** : L'horloge de synchronisation. Générée par la BeagleY-AI, elle cadence la lecture des bits par le MAX7219. La fréquence est configurée à 1 MHz dans le script.

-   **CE0 (Chip Select 0) - Pin 24 (GPIO 8)** : Ligne de sélection de l'esclave. Lorsqu'elle est passée à l'état bas (Low), le MAX7219 écoute le bus. C'est essentiel pour initier une transaction SPI valide.

-   **MISO (Master In Slave Out) - Pin 21 (GPIO 9)** : Bien que présente physiquement, cette ligne n'est pas câblée aux matrices LED MAX7219 car la communication est unidirectionnelle (la BeagleY-AI envoie des données, mais les matrices ne répondent pas).

Pour que ces broches fonctionnent en mode SPI et non en GPIO simple, l'overlay k3-am67a-beagley-ai-spidev0.dtbo doit être chargé au démarrage.<sup>7</sup> Cela expose le périphérique /dev/spidev0.0 au niveau du noyau Linux.

#### 1.2.2 Interface GPIO (Capteur de Présence & Barrière)

La détection de véhicule à la barrière (simulation de boucle d'induction ou cellule photoélectrique) est gérée par une entrée numérique simple.

-   **Signal - Pin 11 (GPIO 17)** : Cette broche est configurée en entrée (Input). Le script sensor_gate.py <sup>1</sup> surveille l'état de cette ligne.

    -   *État Haut (3.3V)* : Véhicule présent (ou absence de faisceau, selon la logique du capteur - NC/NO).

    -   *État Bas (0V)* : Voie libre.

-   **Masse (GND) - Pin 9, 25, 39, etc.** : Référence commune obligatoire entre le capteur et la BeagleY-AI.

La documentation <sup>8</sup> confirme que la Pin 11 correspond bien au GPIO 17 du SoC (Net name : GPIO1_8 ou SoC Pin A26 selon le multiplexage, mais mappée logiciellement comme GPIO 17 pour compatibilité RPi).

#### 1.2.3 Interface Caméra (MIPI CSI-2)

La capture vidéo haute performance ne passe pas par l'USB (trop de latence et charge CPU), mais par l'interface **CSI (Camera Serial Interface)**.

-   **Connecteur** : La BeagleY-AI dispose de connecteurs 22-pin FPC (Flexible Printed Circuit).

-   **Modèle** : Caméra IMX219 (Sony Exmor R), standard de facto pour les projets embarqués.

-   **Topologie** : La caméra est connectée en point-à-point différentiel haut débit. Cela nécessite l'activation de l'overlay k3-am67a-beagley-ai-csi0-imx219.dtbo.<sup>2</sup> Cet overlay configure le PHY D-PHY du SoC pour recevoir les signaux LVDS de la caméra et router le flux vers le VPAC.

## 2. Stratégie Système : OS, Installation et Drivers

Le socle logiciel est le fondement de la stabilité de SysPark. Pour la BeagleY-AI, deux philosophies s'affrontent : l'image Debian générique maintenue par la fondation BeagleBoard, et l'image SDK (Software Development Kit) optimisée par Texas Instruments pour l'Edge AI.

### 2.1 Analyse Comparative des Images Système

Les recherches <sup>91011</sup> mettent en évidence une dichotomie critique :

1.  **Image BeagleBoard Debian (XFCE/Minimal)** :

    -   *Avantages* : Très proche d'une expérience Debian standard, mises à jour via apt, large support communautaire.

    -   *Inconvénients majeurs pour SysPark* : Le support de l'accélération matérielle (C7x DSP, VPAC ISP) et des plugins GStreamer associés (tiovxisp) est souvent expérimental, absent, ou nécessite une recompilation complexe du noyau et des modules.<sup>2</sup>

    -   *Risque* : Sans accélération, le traitement vidéo 1080p se ferait entièrement sur le CPU, saturant les cœurs A53 et rendant le système instable.

2.  **Image TI Edge AI (Basée sur Yocto/Arago)** :

    -   *Avantages* : Contient "out-of-the-box" tous les drivers propriétaires TI, les firmwares pour le DSP et le R5F, et surtout les plugins GStreamer tiovx optimisés. C'est l'image recommandée pour toute application de vision.<sup>12</sup>

    -   *Inconvénients* : Système de fichiers parfois en lecture seule (overlayFS), gestionnaire de paquets moins flexible (parfois opkg au lieu de apt, bien que les versions récentes intègrent apt), environnement plus "figé".

**Décision Architecturale** : Pour les déploiements SysPark, nous distribuons une **image disque SysPark prête à l'emploi** (basée sur TI Edge AI et déjà préconfigurée pour le projet). Cela garantit la disponibilité immédiate des drivers et accélérateurs (VPAC/tiovxisp, etc.) nécessaires au pipeline de vision, tout en figeant un socle stable pour l'intégration terrain.

### 2.2 Procédure d'installation et de mise en route (image SysPark prête à l'emploi)

Le nœud BeagleY-AI destiné à SysPark ne se déploie **pas** en réinstallant manuellement une distribution TI/Debian ni en reconstruisant l'environnement Python. Le système (serveur local, affichage LED, caméras, services, configuration de base) est livré sous forme **d'image disque** déjà préparée.

#### Phase 1 : Pré-requis

1. Une carte BeagleY-AI.
2. Une carte microSD de 16 Go minimum (32 Go recommandé).
3. Un ordinateur (Windows, macOS ou Linux) avec un lecteur microSD.
4. Un outil de flashage (balenaEtcher recommandé).

#### Phase 2 : Flashage de l'image SysPark sur microSD

1. Télécharger et installer balenaEtcher : [https://etcher.balena.io/](https://etcher.balena.io/)
2. Récupérer l'image disque SysPark (fichier `.img`) fournie pour le projet. [https://drive.google.com/file/d/1gn_GpR_V2WfZ9HwwYjGpSotGyj_53xE5/view?usp=sharing](https://drive.google.com/file/d/1gn_GpR_V2WfZ9HwwYjGpSotGyj_53xE5/view?usp=sharing)
3. Flasher la carte microSD avec balenaEtcher (sélection de l'image, sélection de la carte cible, écriture).
4. À la fin du flashage, certains systèmes (notamment Windows) peuvent proposer de formater la carte : il faut **refuser**. La carte contient des partitions Linux valides, simplement non reconnues par Windows.

#### Phase 3 : Premier démarrage

1. Éjecter proprement la microSD puis l'insérer dans la BeagleY-AI.
2. Brancher l'alimentation USB-C.
3. Connecter l'Ethernet (recommandé au premier démarrage).

Au premier boot, l'image peut effectuer une adaptation automatique à la taille de la microSD (extension de partition) et redémarrer. Laisser le nœud démarrer complètement (en pratique 1 à 2 minutes) afin que l'ensemble des services (serveur, affichage, vision, MQTT) se lance.

#### Phase 4 : Accès SSH (Ethernet préconfiguré)

Dans l'image SysPark, l'interface Ethernet est déjà configurée avec l'adresse statique suivante :

```bash
ssh root@192.160.10.1
```

Après connexion, sécuriser immédiatement le nœud (au minimum via la commande `passwd`). L'ajout d'un utilisateur non-root et l'authentification par clé SSH sont recommandés en exploitation, tout en gardant une procédure root disponible pour la maintenance.

#### Phase 5 : Accès au tableau de bord Web

Depuis un poste sur le même réseau, accéder au service Web local :

```text
http://192.160.10.1:5000
```

Selon l'environnement réseau (mDNS/Avahi), l'accès par nom peut aussi fonctionner :

```text
http://beagley-ai.local:5000
```

#### Phase 6 : Personnalisation obligatoire avant mise en service

L'image SysPark contient des réglages de démonstration et/ou de sauvegarde. Avant toute mise en service sur un nouveau site, il faut impérativement :

1. Changer la configuration Wi-Fi pour utiliser le réseau du site.
2. Remplacer toutes les clés / abonnements des services externes (HiveMQ Cloud, Tailscale, API météo, etc.) par les valeurs du client ou de l'exploitant.

Ces opérations sont détaillées en section 3.3.


#### Phase 7 : Comprendre le contenu de l’image SysPark (ce qui est déjà préinstallé)

L’image SysPark n’est pas seulement un système qui “démarre”, c’est un nœud BeagleY‑AI déjà câblé logiciellement pour exécuter la passerelle Edge du projet. Le dossier opérationnel est livré dans `/opt/edgeai-gst-apps` et les services correspondants sont déjà déclarés dans `/etc/systemd/system`.

##### 7.1 Matériel attendu et interfaces

Le fonctionnement nominal de l’image suppose la présence des éléments matériels suivants, car les scripts et services correspondants sont déjà prévus dans l’intégration.

Composant | Interface | Rôle
---|---|---
BeagleY‑AI | Carte SBC | Passerelle Edge, broker MQTT local, pont MQTT cloud, serveurs et logique locale
Caméra 1 IMX219 | CSI | Caméra principale pour la vision IA et la lecture de plaque
Caméra 2 USB | USB | Caméra secondaire, suivant l’intégration
Bandeau LED MAX7219 x4 | SPI (`/dev/spidev0.0`) | Affichage local des états et messages
Driver PCA9685 | I2C (`0x40`) | Génération PWM pour servos (Pan/Tilt)
Servomoteurs x4 | PWM | Orientation des deux caméras motorisées (Pan/Tilt)

##### 7.2 Arborescence livrée dans /opt/edgeai-gst-apps

Le projet est déployé directement dans `/opt/edgeai-gst-apps` et cette arborescence contient à la fois les scripts SysPark et des éléments “EdgeAI” issus de l’écosystème TI.

Référence de contenu observé dans l’image (extrait `ls`), utile pour se repérer lors d’un audit ou d’un dépannage.

```text
/opt/edgeai-gst-apps
Arducam-pivariety-v4l2-driver  (nom exact selon l’image)
CONTRIBUTING
LICENSE
README.md
[Unit]  (entrée anormale, peut être supprimée si inutile)
apps_cpp
apps_python
bandeau_led.py
beagle-ai.tail2fb2e4.ts.net.crt
beagle-ai.tail2fb2e4.ts.net.key
beagle_vision_combined.py
best.pt
cleaner.py
configs
docker
download_models.sh
download_test_data.sh
find_pins.py
force_all_neutra.sh
gate_zone_sensor.py
gnuradio
init_script.sh
optiflow
queue
scripts
sensor_gate.py
serveur
servo_calibration.py
servo_camera.py
setup_script.sh
simple_broker.py
start_vision.sh
test_simple_servo.py
tests
v4l2src
venv
```


Les éléments les plus importants, car directement liés au fonctionnement SysPark, sont les suivants.

Élément | Type | Rôle dans SysPark | Remarques d’exploitation
---|---|---|---
`beagle_vision_combined.py` | Script Python | Vision IA, détection, OCR, streaming MJPEG | Généralement lancé via `start_vision.sh`
`start_vision.sh` | Script shell | Point d’entrée vision | Active le venv et prépare `LD_LIBRARY_PATH` (plugins GStreamer)
`best.pt` | Modèle YOLO | Modèle de détection (plaques/véhicules) | À conserver avec le script vision
`simple_broker.py` | Script Python | Broker MQTT local (résilience) | Écoute typiquement en 1883
`mqtt_bridge.py` | Script Python | Pont MQTT local <-> cloud en TLS | Contient hôte, identifiants, CA, règles de filtrage
`bandeau_led.py` | Script Python | Pilotage bandeau LED (SPI) | Abonné à `parking/display/text`
`meteo_client.py` | Script Python | Client API météo et publication MQTT | Clé API et localisation à personnaliser
`sensor_gate.py` | Script Python | Lecture capteur présence barrière | Publie l’état sur MQTT
`servo_camera.py` | Script Python | Pilotage servos via PCA9685 (I2C) | Abonné à `parking/camera/cmd`
`venv/` | Dossier | Environnement Python isolé | Contient les dépendances déjà installées
`serveur/` | Dossier | Composants serveur local | Heberge le script mqtt_bridge.py et meteo_client.py
`beagle-ai.tail2fb2e4.ts.net.crt` et `.key` | Certificats | Artefacts liés à Tailscale | À régénérer après rattachement au compte Tailscale du client

L’arborescence contient aussi des outils et répertoires non spécifiques à SysPark, mais présents car l’image s’appuie sur l’écosystème TI EdgeAI, par exemple `apps_cpp`, `apps_python`, `optiflow`, `docker`, `tests`, ou des scripts utilitaires (`download_models.sh`, `download_test_data.sh`, etc.). Ils sont utiles pour diagnostiquer ou étendre, mais ne sont pas requis pour l’exploitation minimale.

##### 7.3 Services systemd déjà installés

Les scripts SysPark sont exécutés au démarrage via des unités systemd déjà présentes, notamment `simple_broker.service`, `mqtt_bridge.service`, `beagle_vision.service`, `bandeau_led.service`, ainsi que `meteo_client.service`, `sensor_gate.service` et `servo_camera.service`.

Référence de contenu observé dans l’image (extrait `ls`). Les unités `.service` ci-dessous portent le fonctionnement SysPark, le reste correspond au socle système et aux dépendances de démarrage.

```text
/etc/systemd/system
bandeau_led.service
beagle_vision.service
bluetooth.target.wants
ctrl-alt-del.target
dbus-org.bluez.service
dbus-org.freedesktop.Avahi.service
dbus-org.freedesktop.network1.service
dbus-org.freedesktop.resolve1.service
dbus-org.freedesktop.timesync1.service
dbus.service
default.target
display-manager.service
edgeai-init.service
getty.target.wants
local-fs.target.wants
meteo_client.service
mqtt_bridge.service
multi-user.target.wants
network-online.target.wants
sensor_gate.service
servo_camera.service
simple_broker.service
sockets.target.wants
sysinit.target.wants
systemd-hostnamed.service
systemd-journald.service.wants
systemd-random-seed.service.wants
systemd-udevd.service
timers.target.wants
```

Les sous-répertoires `*.target.wants` correspondent à des liens gérés par systemd pour l’activation automatique au boot.


Le point important est que les services sont le “contrat” d’exécution en production. Après modification d’identifiants (HiveMQ, Tailscale, météo) ou de paramètres matériels (caméra, SPI, I2C), il faut redémarrer le service concerné et vérifier ses logs via `journalctl`.

##### 7.4 Cartographie services <-> exécutables

Service systemd | Exécutable typique | Fonction
---|---|---
`simple_broker.service` | `simple_broker.py` | Broker MQTT local
`mqtt_bridge.service` | `mqtt_bridge.py` | Pont MQTT vers HiveMQ Cloud en TLS
`beagle_vision.service` | `start_vision.sh` puis `beagle_vision_combined.py` | Vision IA + streaming MJPEG
`bandeau_led.service` | `bandeau_led.py` | Bandeau LED SPI
`meteo_client.service` | `meteo_client.py` | Client météo, publication MQTT
`sensor_gate.service` | `sensor_gate.py` | Capteur présence, publication MQTT
`servo_camera.service` | `servo_camera.py` | Servos Pan/Tilt via I2C

##### 7.5 Accès au flux vidéo et maintenance à distance (Tailscale)

Le flux MJPEG issu du module vision est exposé classiquement sur le port 8000, avec une route de type `/mjpeg/cam1`. En local, cela permet de vérifier le cadrage et la mise au point sans outil spécifique.

```text
http://<IP_BEAGLE>:8000/mjpeg/cam1
```

Pour la télémaintenance, l’image peut s’appuyer sur Tailscale. Après rattachement au compte Tailscale du client, deux approches sont usuelles.

La première consiste à utiliser directement l’IP Tailscale (réseau 100.x) ou le nom MagicDNS de la machine pour atteindre le port 8000 à l’intérieur du réseau privé Tailscale.

La seconde consiste à activer un accès HTTPS public via Funnel sur ce port, ce qui renvoie une URL https unique.

```bash
sudo tailscale funnel 8000
```

Dans l’architecture SysPark, cette URL est ensuite reportée côté serveur cloud dans la variable historiquement nommée `NGROK_BASE` (même si le transport n’est pas ngrok) afin que les opérateurs puissent ouvrir le flux vidéo sans être sur le LAN du parking.

Après modification de l’accès distant, vérifier que les fichiers de certificat présents dans `/opt/edgeai-gst-apps` correspondent bien au domaine/compte Tailscale utilisé, puis régénérer si nécessaire.



### 2.3 Paramétrage initial après connexion (réseau, sécurité, abonnements)

Cette phase se fait directement en SSH (connexion root) après le premier démarrage.

#### 2.3.1 Sécurisation minimale

1. Changer le mot de passe root.

```bash
passwd
```

2. Configurer l'accès SSH par clés et, en production, limiter l'accès root (clé uniquement ou désactivation du login root), en s'appuyant sur un utilisateur d'exploitation dédié.

#### 2.3.2 Configuration Wi-Fi (remplacer le réseau par défaut)

La méthode exacte dépend du gestionnaire réseau présent dans l'image (NetworkManager, wpa_supplicant, systemd-networkd). La procédure ci-dessous est robuste : elle privilégie NetworkManager si disponible, sinon bascule sur une configuration wpa_supplicant.

Vérifier d'abord la présence de NetworkManager :

```bash
nmcli --version
```

Si `nmcli` est disponible, configurer le Wi-Fi via :

```bash
nmcli dev wifi list
nmcli dev wifi connect "<SSID>" password "<MOT_DE_PASSE>"
```

Si `nmcli` n'est pas présent, configurer via wpa_supplicant (cas fréquent sur images légères) :

1. Éditer `/etc/wpa_supplicant/wpa_supplicant.conf` et ajouter un bloc `network` pour le SSID du site.
2. Redémarrer le service réseau (ou redémarrer le nœud).

Après configuration, vérifier l'obtention d'une adresse IP et la connectivité :

```bash
ip a
ping -c 3 1.1.1.1
ping -c 3 google.com
```

#### 2.3.3 Remplacement des abonnements et clés API (HiveMQ, Tailscale, météo, etc.)

L'image SysPark inclut des identifiants de démonstration et/ou des valeurs liées à l'environnement de sauvegarde. Ils doivent être remplacés avant toute utilisation.

Recommandation : ne pas modifier en dur les scripts, mais centraliser les secrets dans un fichier de configuration (type `/opt/edgeai-gst-apps/.env` ou `/etc/syspark/secrets.env`) et/ou dans des overrides systemd (`Environment=`). Si l'image a été figée avec des valeurs en dur, l'approche ci-dessous permet de localiser rapidement les points à modifier.

1. Identifier où les paramètres sont stockés (configuration ou code) :

```bash
cd /opt/edgeai-gst-apps
grep -RIn "hivemq\|mqtt\|broker\|openweather\|weather\|tailscale\|authkey\|apikey" .
```

2. Paramétrer HiveMQ Cloud (MQTT distant) :

Mettre à jour l'hôte/port MQTT TLS, l'identifiant, le mot de passe, et le CA si nécessaire. Puis redémarrer le service de pont MQTT (script `mqtt_bridge.py` ou équivalent).

3. Paramétrer Tailscale :

Se déconnecter de l'ancienne identité, puis rattacher le nœud au compte du client avec une clé d'authentification générée dans l'admin console Tailscale :

```bash
tailscale logout
tailscale up --authkey "<TS_AUTHKEY>" --hostname "syspark-beagley-ai"
```

4. Paramétrer l'API météo :

Mettre à jour la clé OpenWeatherMap (ou service équivalent), ainsi que la localisation si elle est utilisée. Puis redémarrer le service météo (script `meteo_client.py` ou équivalent).

#### 3.3.4 Redémarrage des services et vérifications

Lister les services SysPark installés :

```bash
systemctl list-units --type=service | grep -i syspark
```

Vérifier l'état, puis redémarrer les services affectés :

```bash
systemctl status <service>
systemctl restart <service>
```

Contrôler les logs :

```bash
journalctl -u <service> -f
```

### 2.4 Environnement Python et Dépendances

Dans l'image SysPark prête à l'emploi, l'environnement d'exécution nécessaire est déjà installé et les services sont déjà configurés. Cette section reste utile pour comprendre la pile logicielle, dépanner, ou reconstruire une image propre à partir d'une base TI/Debian.

L'écosystème Python moderne (PEP 668) impose l'utilisation d'environnements virtuels pour éviter de corrompre le gestionnaire de paquets système (apt).

1.  **Installation des pré-requis système** :  
```bash
sudo apt update
sudo apt install -y python3-pip python3-venv \
libgpiod-dev gpiod \
tesseract-ocr tesseract-ocr-fra \
libopencv-dev python3-opencv \
gstreamer1.0-tools gstreamer1.0-plugins-base gstreamer1.0-plugins-good gstreamer1.0-plugins-bad \
libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev
```

*Note* : libgpiod-dev est crucial pour le pilotage moderne des GPIOs. tesseract-ocr installe le moteur de reconnaissance optique de caractères.

2.  **Création de l'environnement virtuel (venv)** :  
```bash
# Création du dossier projet
sudo mkdir -p /opt/edgeai-gst-apps
sudo chown $USER:$USER /opt/edgeai-gst-apps
cd /opt/edgeai-gst-apps

# Création du venv
python3 -m venv venv

# Activation
source venv/bin/activate
```

3.  **Installation des librairies Python** : Les scripts fournis nécessitent un ensemble précis de bibliothèques <sup>11111</sup> :  
```bash
pip install paho-mqtt # Client MQTT (Broker & Bridge)
pip install requests # Appels HTTP (Meteo & Vision backend)
pip install flask # Serveur Web (Streaming MJPEG)
pip install numpy # Manipulation matrices image
pip install ultralytics # Framework YOLO (Vision)
pip install pytesseract # Wrapper OCR
pip install smbus2 # Bus I2C (si utilisé futur)
pip install amqtt # Broker MQTT asynchrone (pour simple_broker.py)
```

*Point d'attention* : Le script beagle_vision_combined.py <sup>1</sup> tente d'ajouter manuellement un chemin site-packages au sys.path (/opt/edgeai-gst-apps/venv/...). Cela indique qu'il a été conçu pour tourner dans l'environnement par défaut de l'image TI. Dans notre installation "propre", il faudra peut-être commenter ces lignes ou adapter le chemin vers notre /opt/edgeai-gst-apps/venv.

## 3. Infrastructure de Communication : Le Backbone MQTT

L'architecture SysPark repose sur le paradigme **Publish/Subscribe** via le protocole MQTT (Message Queuing Telemetry Transport). Ce choix est dicté par la nature distribuée du système, la nécessité de découpler les producteurs de données (capteurs) des consommateurs (dashboard, actionneurs), et la résilience requise face aux réseaux instables.

### 3.1 Le Broker Local : Résilience et Autonomie (simple_broker.py)

Le script simple_broker.py <sup>1</sup> instancie un serveur MQTT directement sur la BeagleY-AI.

**Pourquoi un broker local?**

Si la connexion internet coupe, le parking doit continuer à fonctionner : la barrière doit s'ouvrir si le ticket est valide, et les panneaux doivent afficher "LIBRE" ou "COMPLET". En hébergeant le broker sur la passerelle, on garantit que le trafic interne (STM32 \<-\> BeagleY-AI) reste fonctionnel en mode "îlotage".

**Analyse du Code :**

-   Le script utilise la bibliothèque amqtt (anciennement hbmqtt), qui repose sur asyncio pour une gestion non-bloquante des connexions.

-   **Configuration** :  
```python
config = {
'listeners': {
'default': {
'type': 'tcp',
'bind': '0.0.0.0:1883' # Écoute universelle
}
},
'auth': {
'allow_anonymous': True # Sécurité faible (Développement)
}
}
```

-   **Fonctionnement** : Il démarre une boucle d'événements asynchrone. La fonction broker.start() lance le service. Une boucle infinie while True: await asyncio.sleep(10) empêche le script de se terminer, maintenant le broker actif.

-   **Recommandation Sécurité** : En production, allow_anonymous doit impérativement passer à False. Un fichier de mots de passe doit être configuré pour que seuls le STM32 et les services internes (Bridge, Vision) puissent publier.

### 3.2 Le Pont vers le Cloud : Filtrage et Sécurité (mqtt_bridge.py)

Ce composant est la porte de sortie sécurisée vers internet. Il connecte le broker local (127.0.0.1) au broker cloud HiveMQ.<sup>1</sup> Les identifiants et paramètres de connexion du broker distant doivent être remplacés lors du paramétrage initial (voir section 3.3).

**Fonctionnalités Clés :**

1.  **Bridging Bidirectionnel** : Il maintient deux connexions client MQTT simultanées. Lorsqu'un message arrive sur l'une, il est republié sur l'autre, *sous condition*.

2.  **Sécurité TLS** : La connexion vers le cloud (broker.hivemq.com) se fait sur le port **8883** (MQTT over TLS). L'appel cloud.tls_set() active le chiffrement SSL/TLS, protégeant les données de stationnement et les commandes d'ouverture contre l'écoute ou l'injection sur le réseau public.

3.  **Filtrage par Whitelist (ACLs Logiques)** : C'est une fonctionnalité de sécurité applicative majeure.

    -   *Cloud vers Local (ALLOW_CLOUD_TO_LOCAL)* : Seules les commandes critiques sont autorisées (parking/barriere/cmd, parking/display/text). Cela empêche une compromission du cloud de devenir un vecteur d'attaque pour inonder le réseau local de messages parasites.

    -   *Local vers Cloud (ALLOW_LOCAL_TO_CLOUD)* : Seuls les états pertinents (parking/sensor_gate/present, parking/ascenseur/state) remontent. Les logs de debug ou le trafic haute fréquence inutile restent confinés localement, économisant la bande passante 4G/IoT.

### 3.3 Taxonomie des Topics (Namespace)

Une structure de topics rigoureuse est essentielle pour l'évolutivité. SysPark utilise une hiérarchie racine parking/.

| **Topic**                   | **Payload Exemple** | **QoS** | **Retain** | **Description**                                                                                                                                      |
|-----------------------------|---------------------|---------|------------|------------------------------------------------------------------------------------------------------------------------------------------------------|
| parking/sensor_gate/present | 0 ou 1              | 1       | True       | État du capteur de présence. Retain=True est crucial : un nouveau client (ex: dashboard) recevra immédiatement le dernier état connu à la connexion. |
| parking/display/text        | "LIBRE: 12"         | 0       | False      | Message texte brut à afficher sur la matrice LED.                                                                                                    |
| parking/barriere/cmd        | "110"            | 1       | False      | Commande d'actionnement de la barrière. QoS 1 garantit la délivrance "au moins une fois".                                                            |
| parking/meteo               | { "temp": 22,... }  | 0       | True       | Données météorologiques agrégées pour affichage.                                                                                                     |
| parking/system/heartbeat    | Timestamp           | 0       | False      | Battement de cœur pour le monitoring de santé du système.                                                                                            |

## 4. Vision par Ordinateur : L'Intelligence Artificielle en Action

Le module beagle_vision_combined.py <sup>1</sup> transforme la BeagleY-AI d'une simple passerelle en un nœud de calcul intelligent. Il a pour mission de détecter les véhicules et de lire leurs plaques d'immatriculation (LAPI / ALPR - Automatic License Plate Recognition).

### 4.1 Pipeline d'Acquisition Vidéo (GStreamer & Hardware Acceleration)

Le traitement vidéo en 1080p est extrêmement gourmand. Une approche naïve utilisant OpenCV (cv2.VideoCapture) décoderait le flux via le CPU, saturant les 4 cœurs A53 et provoquant une surchauffe et une latence inacceptable (plusieurs secondes).

La solution adoptée exploite **GStreamer** et les éléments matériels dédiés de l'AM67A.<sup>12</sup>

```python
pipeline = (
"gst-launch-1.0 -q v4l2src device=/dev/video-imx219-cam0 io-mode=2 do-timestamp=true! "
"video/x-bayer,width=1920,height=1080,format=rggb,framerate=10/1! "
"tiovxisp sensor-name=SENSOR_SONY_IMX219_RPI...! "
"video/x-raw,format=NV12,width=1920,height=1080! "
"tiovxmultiscaler! "
"video/x-raw,format=NV12,width=640,height=360! "
"fdsink fd=1"
)
```

**Analyse du Pipeline :**

1.  **v4l2src** : Capture les données brutes (Raw Bayer) depuis le capteur via l'interface V4L2 (Video4Linux2).

2.  **tiovxisp (Texas Instruments OpenVX Image Signal Processor)** : C'est le cœur de l'optimisation. Cet élément décharge le CPU en confiant au **VPAC** les tâches lourdes :

    -   *Demosaicing* : Reconstruction des couleurs RGB à partir de la matrice de Bayer.

    -   *Auto White Balance (AWB) & Auto Exposure (AE)* : Ajustement dynamique de l'image (essentiel dans un parking où la luminosité varie).

    -   *Sortie NV12* : Format YUV semi-planaire, efficace pour la mémoire.

3.  **tiovxmultiscaler** : Redimensionnement matériel. L'image 1080p est réduite en 640x360, résolution d'entrée typique pour les réseaux de neurones (YOLO), sans coût CPU.

4.  **fdsink** : Redirige le flux binaire vers la sortie standard (Pipe), permettant à Python de lire les frames comme un fichier.

### 4.2 Architecture de Détection Hybride (YOLO + Tesseract)

Le script implémente une approche en deux temps pour la lecture de plaque :

1.  **Détection d'Objet (Localization) avec YOLOv8** :

    -   Le modèle best.pt (fine-tuné pour les plaques) est chargé via la librairie ultralytics.

    -   Il analyse l'image 640x360 et retourne une **Bounding Box** (coordonnées x, y, w, h) de la plaque.

    -   *Optimisation* : L'utilisation d'un modèle "Nano" (yolov8n) est recommandée sur ce type de hardware pour maintenir un framerate correct si l'accélération TIDL (TI Deep Learning) n'est pas pleinement configurée (le script semble utiliser l'inférence CPU par défaut d'Ultralytics, ce qui est un goulot d'étranglement potentiel).

2.  **Reconnaissance de Caractères (OCR) avec Tesseract** :

    -   La zone de la plaque (Region of Interest - ROI) est découpée dans l'image originale.

    -   **Prétraitement** : Conversion en niveaux de gris -\> Agrandissement (x2) -\> Binarisation (Otsu). Ces étapes sont cruciales pour "nettoyer" l'image avant l'OCR.

    -   **Inférence** : pytesseract extrait le texte.

    -   **Post-traitement (Heuristique SIV)** : Le script applique des règles métiers (Regex) pour valider le format AA-123-AA. Il corrige les erreurs OCR fréquentes (ex: un '0' détecté au début est remplacé par 'O' car le SIV commence par une lettre).

### 4.3 Streaming MJPEG (Feedback Visuel)

En parallèle de l'analyse, le script lance un serveur Flask léger sur le port **8000**. Il expose une route /mjpeg/cam1 qui diffuse les frames traitées.

-   **Utilisation** : Permet à l'opérateur de vérifier le cadrage de la caméra à distance via un navigateur Web, sans avoir besoin d'un flux vidéo complexe (RTSP/WebRTC).

-   **Mécanisme** : "Multipart/x-mixed-replace". Le navigateur reçoit une série d'images JPEG successives.

## 5. Interface Physique : Contrôle et Affichage

La BeagleY-AI n'est pas qu'un cerveau numérique, c'est aussi un contrôleur physique interagissant avec le monde réel via ses GPIOs et Bus série.

### 5.1 Affichage Matrix LED (Bus SPI Bas Niveau)

Le script bandeau_led.py <sup>1</sup> est une démonstration technique fascinante de programmation système en Python. Plutôt que d'utiliser une librairie abstraite (et lente) comme luma.core, il implémente une communication directe avec le driver noyau.

**Technique : ioctl et ctypes**

Le protocole SPI sous Linux est géré par le driver spidev. Pour envoyer des données efficacement (ex: animer une balle qui rebondit), il faut minimiser les changements de contexte (User space \<-\> Kernel space).

Le script définit la structure C spi_ioc_transfer via le module ctypes.

```python
class spi_ioc_transfer(ctypes.Structure):
_fields_ = [("tx_buf", ctypes.c_ulonglong),... ("speed_hz", ctypes.c_uint),...]
```

Il utilise ensuite fcntl.ioctl pour passer cette structure directement au noyau. Cela permet d'envoyer un buffer complet de pixels à 1 MHz en une seule opération atomique, garantissant une fluidité parfaite des animations de défilement de texte ("SCROLL LEFT").

**Logique Métier :**

-   L'affichage est piloté par MQTT. Sur réception de parking/display/text, le script met à jour son buffer interne.

-   Il gère des priorités : un message "COMPLET" (Parking plein) clignote pour attirer l'attention, tandis qu'un message "LIBRE" affiche le nombre de places avec une animation ludique.

### 5.2 Capteurs et Barrière (GPIO et Debouncing)

Le script sensor_gate.py <sup>1</sup> gère l'entrée binaire du capteur de présence.

**Problématique du Rebond (Bouncing) :**

Dans le monde réel, un signal électrique n'est jamais parfaitement propre. Lors d'une transition 0-\>1, le signal peut osciller plusieurs fois en quelques millisecondes. Une lecture naïve déclencherait de multiples événements "Véhicule entré / Véhicule sorti".

**Solution Logicielle** : Le script implémente un "Debounce" (anti-rebond) temporel. Un changement d'état n'est validé que s'il reste stable pendant STABLE_MS (300ms).

**Performance vs Facilité (subprocess vs libgpiod) :**

Le script actuel utilise :

```python
subprocess.check_output(["gpioget",...])
```

*Critique* : Cette méthode lance un nouveau processus shell Linux à chaque lecture (toutes les 50ms). C'est très lourd pour le CPU.

*Optimisation recommandée* : Utiliser les bindings Python de libgpiod (import gpiod) pour garder le périphérique GPIO ouvert et lire son état par simple appel de fonction C, divisant la charge CPU par 100.

**Sécurité (Fail-Safe)** :

Si la lecture échoue (erreur matérielle, surcharge CPU), le script force l'état "PRÉSENT". C'est une sécurité par défaut : le système préfère croire qu'il y a une voiture (et donc laisser la barrière ouverte ou interdire la fermeture) plutôt que de risquer un écrasement.

## 6. Services Tiers et Connectivité Étendue

SysPark ne vit pas en vase clos. Il s'appuie sur des services externes pour enrichir ses fonctionnalités et faciliter son administration.

### 6.1 Météo et Qualité de l'Air (OpenWeatherMap)

Le script meteo_client.py <sup>1</sup> interroge cycliquement (toutes les 60s) l'API OpenWeatherMap. La clé API doit être remplacée lors du paramétrage initial (voir section 3.3).

-   **Données** : Température, Pluie (pour avertir les motards par exemple), Vent, et Indice AQI (Qualité de l'Air).

-   **Flux** : Les données JSON reçues sont parsées ("flattened") et republiées sur MQTT (parking/meteo). Cela permet à l'affichage LED d'afficher "22°C - PLUIE" sans que la BeagleY-AI ait besoin de capteurs physiques coûteux. De plus, les données sont envoyées au serveur Cloud pour corréler la météo avec l'occupation du parking (Data Science).

### 6.2 Accès Distant Sécurisé (Tailscale)

Pour la télémaintenance (SSH, mise à jour des scripts, debug GStreamer), il est impensable d'exposer les ports de la BeagleY-AI directement sur Internet (Port Forwarding), surtout si le parking est connecté via un routeur 4G (CGNAT).

**Solution : Tailscale (VPN Mesh basé sur WireGuard)**.<sup>15</sup> Le nœud doit être rattaché au compte Tailscale de l'exploitant via une auth key (voir section 3.3).

-   **Principe** : La BeagleY-AI installe le démon tailscaled. Elle s'authentifie auprès du coordinateur Tailscale et crée une interface réseau virtuelle (ex: tailscale0 avec IP 100.x.y.z).

-   **Avantage** : Ce réseau est un "Overlay". L'ingénieur peut se connecter en SSH à l'IP 100.x.y.z depuis son PC (aussi sur Tailscale) comme s'il était sur le même réseau local, quel que soit l'endroit où se trouve le parking, traversant les pare-feux et NATs de manière transparente et chiffrée.

## 7. Déploiement Opérationnel et Maintenance

Pour transformer ce prototype en produit industriel fiable, l'installation doit être rigoureuse.

### 7.1 Gestion des processus (systemd)

Dans l’image SysPark, les services nécessaires sont déjà présents dans `/etc/systemd/system` et activés de manière à démarrer automatiquement. En exploitation, on évite de lancer les scripts à la main, et on passe systématiquement par systemd afin d’obtenir un redémarrage automatique, des logs centralisés (journald) et un comportement reproductible au reboot.

Les unités directement liées au projet SysPark sur BeagleY‑AI sont typiquement `simple_broker.service`, `mqtt_bridge.service`, `beagle_vision.service`, `bandeau_led.service`, `meteo_client.service`, `sensor_gate.service` et `servo_camera.service`.

Pour vérifier l’état d’un service et voir ses logs en direct, les commandes de référence sont :

```bash
systemctl status beagle_vision
journalctl -u beagle_vision -f
```

Même logique pour les autres services.

```bash
systemctl status simple_broker mqtt_bridge bandeau_led meteo_client sensor_gate servo_camera
```

Après modification d’un paramètre, redémarrer uniquement le service concerné, puis relire les logs pour valider.

```bash
systemctl restart mqtt_bridge
journalctl -u mqtt_bridge -n 100 --no-pager
```

#### Overrides et injection de secrets sans modifier le code

Pour éviter de réécrire des identifiants “en dur” dans les scripts, le mode recommandé consiste à créer un fichier de secrets et à le déclarer côté systemd.

Un exemple courant est de créer un fichier `/etc/syspark/secrets.env` contenant vos valeurs (HiveMQ, API météo, Tailscale), puis de créer un override systemd.

```bash
mkdir -p /etc/systemd/system/mqtt_bridge.service.d
nano /etc/systemd/system/mqtt_bridge.service.d/override.conf
```

Contenu type.

```ini
[Service]
EnvironmentFile=/etc/syspark/secrets.env
```

Après modification, recharger systemd et redémarrer le service.

```bash
systemctl daemon-reload
systemctl restart mqtt_bridge
```

Cette approche permet de livrer une image “générique”, puis de personnaliser site par site sans toucher aux scripts, tout en gardant la traçabilité et la maintenance.

#### Exemple d’unité représentative (vision)

Dans cette image, `beagle_vision.service` passe par `start_vision.sh`. Dans les ce cas-ci, l’idée est d’ancrer le répertoire de travail sur `/opt/edgeai-gst-apps` et d’utiliser le venv fourni.

```ini
[Unit]
Description=SysPark Beagle Vision (AI + MJPEG)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/opt/edgeai-gst-apps
ExecStart=/opt/edgeai-gst-apps/start_vision.sh
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```


### 7.2 Logs et Monitoring

Avec Systemd, tous les print() des scripts Python sont capturés par journald.

-   **Visualisation temps réel** : journalctl -u syspark-vision -f permet de voir les logs de la vision en direct.

-   **Rotation** : Les logs sont gérés automatiquement pour ne pas saturer la carte SD.

### 7.3 Check-list de Validation (Mise en service)

Avant de quitter le site, l'intégrateur doit valider :

1.  **Matériel** :

    -   La BeagleY-AI est-elle bien alimentée (LED Power stable)?

    -   Le dissipateur thermique est-il chaud (signe que le CPU/DSP travaille)?

2.  **Système** :

    -   htop : La charge CPU est-elle acceptable (\<70% sur les 4 cœurs)?

    -   free -h : Reste-t-il de la RAM libre?

3.  **Fonctionnel** :

    -   Passer la main devant le capteur : La barrière virtuelle change-t-elle d'état dans les logs MQTT (mosquitto_sub -t parking/#)?

    -   Montrer une photo de plaque à la caméra : Le texte est-il reconnu et envoyé?

    -   L'afficheur LED réagit-il aux commandes envoyées depuis le Cloud?


