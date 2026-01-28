#!/bin/bash

# 1. On se place dans le dossier
cd /opt/edgeai-gst-apps

# 2. Variables d'environnement
export PARKING_SERVER_BASE="https://parking-server-r38v.onrender.com"
export PYTHONUNBUFFERED=1
export YOLO_VERBOSE=False

# 3. ON FORCE LE PYTHONPATH (Double sécurité pour Systemd)
export PYTHONPATH=/opt/edgeai-gst-apps/venv/lib/python3.12/site-packages:$PYTHONPATH

echo "🚀 Lancement du wrapper vision avec le Python du VENV..."

# 4. LIGNE CRUCIALE : On appelle DIRECTEMENT le binaire python du venv
# Au lieu de 'python', on met le chemin absolu.
exec /opt/edgeai-gst-apps/venv/bin/python -u beagle_vision_combined.py
