#!/usr/bin/env python3
import base64
import sys
import os

# --- FORCE L'UTILISATION DE OPENCV HEADLESS DU VENV ---
sys.path.insert(0, "/opt/edgeai-gst-apps/venv/lib/python3.12/site-packages")

os.environ["YOLO_VERBOSE"] = "False"

import time
import threading
import logging
import re
import subprocess
import cv2
import numpy as np
import requests
from flask import Flask, Response

# Correction Logger
logging.getLogger("ultralytics").setLevel(logging.ERROR)

import contextlib
import io
import select

# IA LOCALE
import pytesseract
from ultralytics import YOLO

# ==========================================                                                          
#     corriger les ambiguïtés caractère-par-caractère                                                                          
# ========================================== 

# Positions SIV: 0-1 = Lettres, 2-4 = Chiffres, 5-6 = Lettres
_EXPECT = ["L", "L", "D", "D", "D", "L", "L"]

_TO_DIGIT = {  # quand on attend un chiffre
    "O": "0", "Q": "0", "D": "0",
    "I": "1", "L": "1",
    "Z": "2",
    "S": "5",
    "G": "6",
    "B": "8",
}

_TO_LETTER = {  # quand on attend une lettre
    "0": "O",
    "1": "I",
    "2": "Z",
    "4": "A",
    "5": "S",
    "6": "G",
    "8": "B",
}

def _is_letter(c: str) -> bool:
    return "A" <= c <= "Z"

def _is_digit(c: str) -> bool:
    return "0" <= c <= "9"

def correct_siv_by_position(raw: str):
    """
    Ne fait QUE:
    - Nettoyage alphanum
    - Vérifie longueur == 7
    - Corrige caractère par caractère selon la position (L/D)
    Retourne "AA-123-BB" ou None si impossible.
    """
    if not raw:
        return None

    raw = re.sub(r"[^A-Z0-9]", "", raw.upper().strip())
    if len(raw) != 7:
        return None

    out = []
    for i, ch in enumerate(raw):
        expect = _EXPECT[i]

        if expect == "L":
            if _is_letter(ch):
                out.append(ch)
                continue
            if _is_digit(ch) and ch in _TO_LETTER:
                out.append(_TO_LETTER[ch])
                continue
            return None

        if expect == "D":
            if _is_digit(ch):
                out.append(ch)
                continue
            if _is_letter(ch) and ch in _TO_DIGIT:
                out.append(_TO_DIGIT[ch])
                continue
            return None

        return None

    return f"{out[0]}{out[1]}-{out[2]}{out[3]}{out[4]}-{out[5]}{out[6]}"

# ==========================================
#     CLASSE "SILENCE TOTAL"
# ==========================================
class AgnosticSuppress:
    def __enter__(self):
        self.save_fds = [os.dup(1), os.dup(2)]
        self.null_fds = [os.open(os.devnull, os.O_RDWR) for _ in range(2)]
        os.dup2(self.null_fds[0], 1)
        os.dup2(self.null_fds[1], 2)

    def __exit__(self, *args):
        os.dup2(self.save_fds[0], 1)
        os.dup2(self.save_fds[1], 2)
        for fd in self.null_fds + self.save_fds:
            try: os.close(fd)
            except: pass

# ==========================================
#             CONFIG GLOBALE
# ==========================================

AI_W, AI_H = 640, 360
AI_NV12_SIZE = int(AI_W * AI_H * 1.5)
AI_CHECK_INTERVAL = 0.2 # On peut essayer un peu plus rapide maintenant que c'est sécurisé
CONFIDENCE_THRESHOLD = 0.20
STREAM_W, STREAM_H = 320, 180
STREAM_JPEG_QUALITY = 45
STREAM_MAX_FPS = 15.0 # Un peu plus fluide

PARKING_SERVER_BASE = os.getenv("PARKING_SERVER_BASE", "https://parking-server-r38v.onrender.com").rstrip("/")

_frame_cache = { "cam1": (0.0, b""), "cam2": (0.0, b"") }
_cache_lock = threading.Lock()

# 🔒 LE VERROU DE SÉCURITÉ (INDISPENSABLE)
# Empêche de lancer 50 IA en même temps
ai_lock = threading.Lock()

app = Flask(__name__)

# ==========================================
# CHARGEMENT DU MODÈLE
# ==========================================
print("[INIT] Chargement du modèle YOLO...", flush=True)
model_path = "best.pt"

if not os.path.exists(model_path):
    print(f"[ERREUR] {model_path} introuvable, fallback yolov8n.pt", flush=True)
    model = YOLO("yolov8n.pt") 
else:
    model = YOLO(model_path)

# ==========================================
#     LOGIQUE INTELLIGENTE
# ==========================================

def notify_server_plate(plate: str, cam_id: str, image_bgr=None):
    """
    Envoie la plaque + la photo (encodée en Base64) au serveur.
    """
    if not PARKING_SERVER_BASE: return
    
    clean_id = "1" if "cam1" in cam_id.lower() else "2"
    url = f"{PARKING_SERVER_BASE}/api/plate_event"
    
    # Construction du payload de base
    payload = {
        "plate": plate, 
        "cam_id": clean_id,
        "image": "" # Vide par défaut
    }

    # Si on a une image, on la convertit en Base64
    if image_bgr is not None:
        try:
            # 1. On encode l'image numpy en JPEG en mémoire
            _, buffer = cv2.imencode('.jpg', image_bgr)
            # 2. On convertit les octets en chaîne Base64
            jpg_as_text = base64.b64encode(buffer).decode('utf-8')
            # 3. On ajoute au payload
            payload["image"] = jpg_as_text
        except Exception as e:
            print(f"[{cam_id}] Erreur encodage image: {e}")

    print(f"[{cam_id}][HTTP] 📤 Envoi : {plate} (avec photo 📸)", flush=True)
    
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"[{cam_id}][HTTP] ❌ Erreur : {e}", flush=True)

def process_ai_frame_safe(frame_bgr, cam_id):
    """
    Mode extraction puis correction:
    - YOLO bbox
    - OCR -> raw alphanum
    - Extraction d'un bloc de 7 caractères dans raw
    - Correction positionnelle SIV (lettre/chiffre) sur ces 7 caractères
    """
    with ai_lock:
        t0 = time.perf_counter()
        try:
            with AgnosticSuppress():
                results = model(frame_bgr, verbose=False, conf=CONFIDENCE_THRESHOLD, max_det=1)
            t1 = time.perf_counter()

            for r in results:
                if r.boxes is None or len(r.boxes) == 0:
                    print(f"[{cam_id}] YOLO: 0 box  (t={t1-t0:.3f}s)", flush=True)
                    return

                for box in r.boxes:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])

                    h_img, w_img, _ = frame_bgr.shape
                    pad = 10
                    x1 = max(0, x1 - pad)
                    y1 = max(0, y1 - pad)
                    x2 = min(w_img, x2 + pad)
                    y2 = min(h_img, y2 + pad)

                    plate_img = frame_bgr[y1:y2, x1:x2]

                    gray = cv2.cvtColor(plate_img, cv2.COLOR_BGR2GRAY)
                    gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
                    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

                    config_tess = r'--oem 3 --psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
                    with AgnosticSuppress():
                        text = pytesseract.image_to_string(thresh, config=config_tess)
                    t2 = time.perf_counter()

                    # 1) Nettoyage OCR -> alphanum
                    raw = re.sub(r'[^A-Z0-9]', '', text.upper().strip())
          
                    # Au lieu de regex complexe, on teste chaque bloc de 7 caractères
                    
                    found_plate = None
                    
                    # Si on a moins de 7 caractères, c'est mort
                    if len(raw) >= 7:
                        # On parcourt la chaîne : "JAA123AAB"
                        # i=0 -> "JAA123A" (Testé -> Invalide)
                        # i=1 -> "AA123AA" (Testé -> VALIDE !)
                        # i=2 -> "A123AAB" (Testé -> Invalide)
                        for i in range(len(raw) - 6):
                            candidate = raw[i : i+7]
                            corrected = correct_siv_by_position(candidate)
                            if corrected:
                                found_plate = corrected
                                break # On a trouvé, on arrête de chercher !

                    if found_plate:
                        print(
                            f"[{cam_id}] YOLO(t={t1-t0:.3f}s) OCR(t={t2-t1:.3f}s) => {found_plate} (raw='{raw}')",
                            flush=True
                        )
                        notify_server_plate(found_plate, cam_id, plate_img)
                        return
                    else:
                        print(
                            f"[{cam_id}] YOLO OK (t={t1-t0:.3f}s) OCR KO (t={t2-t1:.3f}s) raw='{raw}' (Aucun pattern SIV trouvé)",
                            flush=True
                        )
                        return

        except Exception as e:
            print(f"[{cam_id}] EXCEPTION IA: {type(e).__name__}: {e}", flush=True)

# ==========================================
#  PIPELINE VIDÉO
# ==========================================
def _camera_session(cmd: str, cam_key: str, cam_label: str):
    print(f"[{cam_label}] Démarrage Pipeline...", flush=True)
    proc = None
    try:
        # On redirige stderr vers DEVNULL pour éviter de polluer
        proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=AI_NV12_SIZE * 2)
        
        # ⚠️ CORRECTION : ON NE TOUCHE PAS AU MODE BLOQUANT ICI
        # On laisse le comportement par défaut (Bloquant) pour que .read() récupère tout le buffer.

        last_ai = 0.0
        last_jpg = 0.0

        while True:
            # --- WATCHDOG (Sécurité Anti-Gel) ---
            # select fonctionne aussi sur des fichiers bloquants !
            # Il nous dit si des données sont PRÊTES à être lues.
            rlist, _, _ = select.select([proc.stdout], [], [], 5.0)
            
            if not rlist:
                print(f"[{cam_label}] ⚠️ TIMEOUT CAMÉRA (Pas de données depuis 5s) -> Redémarrage...", flush=True)
                break 

            # --- LECTURE (Bloquante mais sécurisée par select) ---
            # Comme select a dit "ok", le read ne bloquera pas indéfiniment au début.
            # Et comme on est en mode bloquant, il va attendre d'avoir EXACTEMENT AI_NV12_SIZE bytes.
            raw = proc.stdout.read(AI_NV12_SIZE)
            
            if not raw or len(raw) != AI_NV12_SIZE:
                print(f"[{cam_label}] Flux terminé (EOF) ou taille incorrecte", flush=True)
                break

            now = time.time()
            
            # --- Traitement Image ---
            nv12 = np.frombuffer(raw, np.uint8).reshape((int(AI_H * 1.5), AI_W))
            bgr = cv2.cvtColor(nv12, cv2.COLOR_YUV2BGR_NV12)

            # --- IA (YOLO) ---
            if (now - last_ai > AI_CHECK_INTERVAL) and not ai_lock.locked():
                last_ai = now
                threading.Thread(target=process_ai_frame_safe, args=(bgr.copy(), cam_label), daemon=True).start()

            # --- Streaming MJPEG ---
            if now - last_jpg >= 1.0 / STREAM_MAX_FPS:
                last_jpg = now
                s_frame = cv2.resize(bgr, (STREAM_W, STREAM_H), interpolation=cv2.INTER_NEAREST)
                ok, buf = cv2.imencode(".jpg", s_frame, [int(cv2.IMWRITE_JPEG_QUALITY), STREAM_JPEG_QUALITY])
                if ok:
                    with _cache_lock: _frame_cache[cam_key] = (now, buf.tobytes())

    except Exception as e:
        print(f"[{cam_label}] Erreur Pipeline Critique: {e}", flush=True)
    finally:
        # Nettoyage
        if proc:
            try:
                proc.terminate()
            except:
                pass
            try:
                proc.wait(timeout=1)
            except:
                try:
                    proc.kill()
                except:
                    pass

def capture_thread(cmd, key, label):
    while True:
        _camera_session(cmd, key, label)
        time.sleep(1.0)

# ==========================================
#  FLASK
# ==========================================
@app.route("/mjpeg/<cid>")
def mjpeg(cid):
    k = "cam1" if "cam1" in cid else "cam2"
    def gen():
        lt = 0
        while True:
            with _cache_lock: t, d = _frame_cache.get(k, (0, b""))
            if d and t > lt:
                lt = t
                yield (b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: " + str(len(d)).encode() + b"\r\n\r\n" + d + b"\r\n")
            else: time.sleep(0.02)
    return Response(gen(), mimetype="multipart/x-mixed-replace; boundary=frame")

@app.route("/")
def index(): return "BeagleVision Pro (Stable Lock) Running."

if __name__ == "__main__":
    c1 = ("gst-launch-1.0 -q v4l2src device=/dev/video-imx219-cam0 io-mode=2 do-timestamp=true ! "
          "video/x-bayer,width=1920,height=1080,format=rggb,framerate=10/1 ! "
          "tiovxisp sensor-name=SENSOR_SONY_IMX219_RPI sink_0::device=/dev/v4l-imx219-subdev0 "
          "sink_0::dcc-2a-file=/opt/imaging/imx219/linear/dcc_2a_1920x1080.bin "
          "dcc-isp-file=/opt/imaging/imx219/linear/dcc_viss_1920x1080.bin ! "
          "video/x-raw,format=NV12,width=1920,height=1080 ! tiovxmultiscaler ! "
          "video/x-raw,format=NV12,width=640,height=360 ! fdsink fd=1")
    
    c2 = ("gst-launch-1.0 -q v4l2src device=/dev/video-usb-cam0 ! videoconvert ! videoscale ! "
          "video/x-raw,format=NV12,width=640,height=360,framerate=15/1 ! fdsink fd=1")

    threading.Thread(target=capture_thread, args=(c1, "cam1", "CAM1"), daemon=True).start()
    threading.Thread(target=capture_thread, args=(c2, "cam2", "CAM2"), daemon=True).start()
    
    print("🚀 Serveur Vision Démarré sur port 8000 (Mode STABLE)", flush=True)
    app.run(host="0.0.0.0", port=8000, debug=False)
