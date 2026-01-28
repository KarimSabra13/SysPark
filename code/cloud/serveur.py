# serveur.py - VERSION RESTAURÉE (Flux MJPEG Direct + Proxy Backend)

# ⚡⚡⚡ INDISPENSABLE POUR LE TEMPS RÉEL (DOIT ÊTRE LA PREMIÈRE LIGNE) ⚡⚡⚡
from gevent import monkey
monkey.patch_all()

import os
import json
import time
import threading
import math
import requests
from requests.adapters import HTTPAdapter
from typing import List, Dict, Any, Optional
from datetime import datetime
import pytz

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, jsonify, Response
)

from b2b import b2b_bp
from extensions import db, socketio
from flask_socketio import emit
from sqlalchemy import desc, or_
from werkzeug.security import generate_password_hash, check_password_hash
import paho.mqtt.client as mqtt
import stripe

# ============================================================================
# Configuration Flask, Database & IO
# ============================================================================
app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET", "change_me")

database_url = os.getenv("DATABASE_URL", "sqlite:///parking.db")
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
socketio.init_app(app)

app.register_blueprint(b2b_bp)



PARKING_CAPACITY = 10 

# ============================================================================
# MODÈLE DE DONNÉES
# ============================================================================
class ParkingSession(db.Model):
    __tablename__ = 'sessions'
    id = db.Column(db.Integer, primary_key=True)
    identity = db.Column(db.String(50), nullable=False)
    source = db.Column(db.String(50))
    meta_data = db.Column(db.JSON, default={})
    opened_at = db.Column(db.Float, nullable=False)
    closed_at = db.Column(db.Float, nullable=True)
    last_event = db.Column(db.Float, nullable=False)
    payment_time = db.Column(db.Float, default=0.0)
    paid = db.Column(db.Boolean, default=False)
    duration_s = db.Column(db.Float, default=0.0)
    price_eur = db.Column(db.Float, default=0.0)
    is_open = db.Column(db.Boolean, default=True)

# --- NOUVELLE TABLE POUR SAUVEGARDER LES PLAQUES ---
class Badge(db.Model):
    __tablename__ = 'badges'
    uid = db.Column(db.String(20), primary_key=True)
    plate = db.Column(db.String(20), nullable=True)

class SystemConfig(db.Model):
    __tablename__ = 'system_config'
    key = db.Column(db.String(50), primary_key=True)
    value = db.Column(db.String(255), nullable=False)

with app.app_context():
    db.create_all()


# --- GESTION UTILISATEURS SÉCURISÉE ---
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
# Si aucun mot de passe n'est défini, on met une valeur par défaut mais on avertit
ADMIN_PASS = os.getenv("ADMIN_PASSWORD", "admin") 

if "ADMIN_PASSWORD" not in os.environ:
    print("⚠️ [SECURITE] Attention : Mot de passe admin par défaut utilisé !", flush=True)

USERS = { 
    ADMIN_USER: { 
        "password_hash": generate_password_hash(ADMIN_PASS) 
    } 
}

# ============================================================================
# Config & Globals
# ============================================================================

parking_lock = threading.Lock()

# Fichier de sauvegarde des associations UID <-> Plaque
current_badges_from_stm32: List[str] = []

# --- Variable pour le mode enrôlement ---
enrollment_mode = False 
# ----------------------------------------------------

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
STRIPE_API_KEY = os.getenv("STRIPE_API_KEY")
stripe.api_key = STRIPE_API_KEY

MQTT_HOST = os.getenv("MQTT_HOST", "broker.hivemq.com")
MQTT_PORT = 8883
MQTT_SECRET = os.getenv("MQTT_SECRET", "CHANGE_ME")

mqtt_client = mqtt.Client(client_id="parking-server-secure", clean_session=False)

# Activation du TLS
print("🔒 [SÉCURITÉ] MQTT chiffré (TLS) activé", flush=True)
mqtt_client.tls_set()

_mqtt_ready = False
mqtt_lock = threading.Lock()

current_badges: List[str] = []
_last_acl_ack: Dict[str, Optional[str]] = {"status": None, "at": None}
_badge_cooldowns: Dict[str, float] = {}

meteo_data: Optional[Dict[str, Any]] = None
ascenseur_state: Dict[str, Any] = {"current": None, "at": None}

# ============================================================================
# GESTION CAMÉRAS (TON CODE RESTAURÉ)
# ============================================================================
NGROK_BASE = os.getenv("NGROK_BASE")  # Obligatoire pour les caméras

if not NGROK_BASE:
    print("⚠️  ERREUR : NGROK_BASE n'est pas défini dans les variables Render !", flush=True)

# Session HTTP persistante
_cam_http_session = requests.Session()
_adapter = HTTPAdapter(pool_connections=20, pool_maxsize=20, max_retries=0)
_cam_http_session.mount("http://", _adapter)
_cam_http_session.mount("https://", _adapter)

# Micro-cache en RAM
_frame_cache: Dict[str, tuple[float, bytes]] = {
    "cam1": (0.0, b""),
    "cam2": (0.0, b""),
}

_BLACK_JPEG = (b"\xff\xd8\xff\xdb\x00C\x00" + b"\x00" * 64 + b"\xff\xd9")
_MAX_FRAME_AGE = 0.08  # secondes

def _make_no_cache_response(payload: bytes) -> Response:
    resp = Response(payload, mimetype="image/jpeg")
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp

def _proxy_snapshot(path: str, cam_key: str):
    """
    Proxy vidéo → appelle NGROK_BASE + path et renvoie le JPEG.
    """
    if not NGROK_BASE:
        return _make_no_cache_response(_BLACK_JPEG)

    now = time.time()
    ts, buf = _frame_cache.get(cam_key, (0.0, b""))

    # Micro-cache côté Render
    if buf and (now - ts) <= _MAX_FRAME_AGE:
        return _make_no_cache_response(buf)

    url = f"{NGROK_BASE}{path}"

    try:
        r = _cam_http_session.get(url, timeout=0.7)
        r.raise_for_status()
        data = r.content
        _frame_cache[cam_key] = (now, data)
        return _make_no_cache_response(data)
    except Exception as e:
        print(f"[CAM PROXY] erreur pour {cam_key}: {e}", flush=True)
        if buf:
            return _make_no_cache_response(buf)
        return _make_no_cache_response(_BLACK_JPEG)

# ROUTES CAMERA (Render)
def login_required(fn):
    from functools import wraps
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("username"): return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

# ============================================================================
# GESTION CAMÉRAS (MODE STREAMING / VIDÉO FLUIDE)
# ============================================================================
@app.route("/proxy/cam1")
@login_required
def proxy_cam1():
    if not NGROK_BASE: return _make_no_cache_response(_BLACK_JPEG)
    try:
        # On se connecte au flux MJPEG continu de la BeagleBone
        # stream=True est CRUCIAL ici pour ne pas attendre la fin du téléchargement
        url = f"{NGROK_BASE}/mjpeg/cam1"
        req = _cam_http_session.get(url, stream=True, timeout=5)
        
        # On renvoie les paquets de données au navigateur au fur et à mesure (Piping)
        return Response(req.iter_content(chunk_size=1024), 
                        content_type=req.headers.get('Content-Type', 'multipart/x-mixed-replace; boundary=frame'))
    except Exception as e:
        print(f"[PROXY] Erreur Stream Cam 1: {e}")
        return _make_no_cache_response(_BLACK_JPEG)

@app.route("/proxy/cam2")
@login_required
def proxy_cam2():
    if not NGROK_BASE: return _make_no_cache_response(_BLACK_JPEG)
    try:
        url = f"{NGROK_BASE}/mjpeg/cam2"
        req = _cam_http_session.get(url, stream=True, timeout=5)
        return Response(req.iter_content(chunk_size=1024), 
                        content_type=req.headers.get('Content-Type', 'multipart/x-mixed-replace; boundary=frame'))
    except Exception as e:
        print(f"[PROXY] Erreur Stream Cam 2: {e}")
        return _make_no_cache_response(_BLACK_JPEG)

@app.route("/camera1/fullscreen")
@login_required
def camera1_fullscreen():
    return render_template("camera_full.html", titre="Caméra 1", cam_id="cam1", ts_funnel=NGROK_BASE or "")

@app.route("/camera2/fullscreen")
@login_required
def camera2_fullscreen():
    return render_template("camera_full.html", titre="Caméra 2", cam_id="cam2", ts_funnel=NGROK_BASE or "")

# ============================================================================
# Helpers & Logic
# ============================================================================
def _now_ts() -> float: return time.time()

def _fmt_dt(ts: float) -> str:
    if not ts: return "-"
    try:
        paris_tz = pytz.timezone('Europe/Paris')
        dt_paris = datetime.fromtimestamp(ts, paris_tz)
        return dt_paris.strftime("%Y-%m-%d %H:%M")
    except: return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))

def get_pricing_config():
    """ Récupère la configuration tarifaire depuis la DB (SystemConfig) """
    return {
        "free_minutes": int(get_db_config("tariff_free_min", 30)),
        "chunk_minutes": int(get_db_config("tariff_chunk_min", 15)),
        "price_per_chunk": float(get_db_config("tariff_price_chunk", 0.50)),
        "daily_max": float(get_db_config("tariff_daily_max", 20.0))
    }

def _compute_price(duration_s: float, source: str = "", identity: str = "") -> float:
    minutes = duration_s / 60.0
    
    # Gratuit pour PINCODE ou BADGE
    if identity.startswith("PINCODE"): return 0.0
    if source and "badge" in source.lower(): return 0.0
    
    # Récupération de la config dynamique
    p = get_pricing_config()
    
    # Période de grâce
    if minutes <= p["free_minutes"]: return 0.0
    
    # Calcul par tranches
    billable_minutes = minutes - p["free_minutes"]
    
    # On évite la division par zéro si l'utilisateur met 0
    chunk_size = p["chunk_minutes"] if p["chunk_minutes"] > 0 else 15 
    
    chunks = math.ceil(billable_minutes / chunk_size)
    price = chunks * p["price_per_chunk"]
    
    # Gestion du plafond journalier
    days_started = math.ceil(minutes / (24 * 60)) 
    max_price = days_started * p["daily_max"]
    
    return min(price, max_price)

def _send_telegram(text: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID: return
    try: requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", data={"chat_id": TELEGRAM_CHAT_ID, "text": text}, timeout=4)
    except: pass

def _notify_parking_telegram(session_obj):
    dur_min = int(round(session_obj.duration_s / 60.0))
    text_lines = ["🚗 Session parking terminée", f"ID : {session_obj.identity}"]
    plate = session_obj.meta_data.get("plate")
    if plate: text_lines.append(f"Plaque : {plate}")
    text_lines.extend([f"Entrée : {_fmt_dt(session_obj.opened_at)}", f"Sortie : {_fmt_dt(session_obj.closed_at)}", f"Durée : {dur_min} min", f"Montant : {session_obj.price_eur:.2f} €"])
    _send_telegram("\n".join(text_lines))

def _normalize_uid8(uid_raw: str) -> str:
    cleaned = []
    for c in uid_raw.strip():
        if c.isspace(): continue
        if "a" <= c <= "f": c = c.upper()
        if ("0" <= c <= "9") or ("A" <= c <= "F"): cleaned.append(c)
        if len(cleaned) >= 8: break
    return "".join(cleaned)

def get_db_config(key, default_val):
    """ Récupère une config en DB, ou renvoie la valeur par défaut """
    with app.app_context():
        item = SystemConfig.query.get(key)
        return item.value if item else default_val

def set_db_config(key, val):
    """ Sauvegarde une config en DB """
    with app.app_context():
        item = SystemConfig.query.get(key)
        if not item:
            item = SystemConfig(key=key, value=str(val))
            db.session.add(item)
        else:
            item.value = str(val)
        db.session.commit()

def sync_stm32_state(delay=0.0):
    """ Envoie l'état complet à la STM32 depuis la DB """
    _ensure_mqtt()
    
    # 1. Envoi des PINs (Priorité 1)
    with app.app_context():
        # Lecture DB
        pin_in = get_db_config("pin_entry", "1234")
        pin_out = get_db_config("pin_exit", "0000")
        
        # Envoi PIN Entrée
        mqtt_client.publish("parking/config/pin", pin_in, retain=True)
        if delay > 0: time.sleep(delay) # ⏳ Pause anti-saturation
        
        # Envoi PIN Sortie
        mqtt_client.publish("parking/config/exit_pin", pin_out, retain=True)
        if delay > 0: time.sleep(delay) # ⏳ Pause
        
        # 2. Envoi des Places (Priorité 2)
        count = ParkingSession.query.filter_by(is_open=True).count()
        remaining = PARKING_CAPACITY - count
        msg = "COMPLET" if remaining <= 0 else f"LIBRE:{remaining}"
        
        mqtt_client.publish("parking/display/text", msg, retain=True)
        
        print(f"🔄 [SYNC] Envoyé à la STM32 (In={pin_in}, Out={pin_out}, {msg})", flush=True)


# ============================================================================
# MQTT Logic
# ============================================================================
def _ensure_mqtt():
    global _mqtt_ready
    if _mqtt_ready: return
    try:
        mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)
        mqtt_client.loop_start()
        mqtt_client.subscribe("parking/#")
        mqtt_client.publish("parking/ascenseur/get", "req")
        _mqtt_ready = True
        print(f"[MQTT] Connecté à {MQTT_HOST}")
    except: pass

def send_cmd(cible, commande):
    _ensure_mqtt()
    topic = ""
    if cible == "barriere_sortie" or cible == "barriere": topic = "parking/barriere/cmd"
    elif cible == "barriere_entree": topic = "parking/barriere_entree/cmd"
    elif cible == "ascenseur": topic = "parking/ascenseur/cmd"
    else: return
    mqtt_client.publish(topic, commande)

def send_acl_add(uid): _ensure_mqtt(); mqtt_client.publish("parking/acl/add", json.dumps({"op": "ADD", "uid": uid, "secret": MQTT_SECRET}))
def send_acl_del(uid): _ensure_mqtt(); mqtt_client.publish("parking/acl/del", json.dumps({"op": "DEL", "uid": uid, "secret": MQTT_SECRET}))
def send_acl_full(uids): _ensure_mqtt(); mqtt_client.publish("parking/acl/full", json.dumps({"op": "FULL", "entries": [{"uid": u} for u in uids], "secret": MQTT_SECRET}))
def send_acl_list_request(): _ensure_mqtt(); mqtt_client.publish("parking/acl/get", json.dumps({"op": "LIST_REQ", "secret": MQTT_SECRET}))

# ============================================================================
# LOGIQUE PARKING (AVEC CORRECTION D'ERREURS OCR)
# ============================================================================
def levenshtein_distance(s1, s2):
    """Calcule le nombre de caractères différents entre deux plaques"""
    if len(s1) < len(s2): return levenshtein_distance(s2, s1)
    if len(s2) == 0: return len(s1)
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions, deletions = previous_row[j + 1] + 1, current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]

def _handle_parking_event(identity: str, source: str, meta: Optional[Dict[str, Any]] = None):
    now = _now_ts()
    meta = meta or {}
    COOLDOWN_NEW = 60        
    EXIT_DELAY_MINUTES = 10
    FUZZY_TOLERANCE = 1  # Tolérance d'erreur (1 caractère)
    DUPLICATE_WINDOW = 300 # 5 minutes pour détecter un doublon à l'entrée

    is_entry_cam = ("cam1" in source.lower()) or ("cam_1" in source.lower()) or ("entree" in source.lower())
    is_exit_cam = ("cam2" in source.lower()) or ("cam_2" in source.lower()) or ("sortie" in source.lower()) or ("paiement" in source) or ("demo" in source)
    
    # On extrait la plaque brute (sans "PLATE:") pour comparer
    plate_raw = meta.get("plate", identity.replace("PLATE:", ""))

    with app.app_context():
        with parking_lock:
            # Recherche exacte d'abord
            session_entry = ParkingSession.query.filter_by(identity=identity, is_open=True).first()
            
            # --- INTELLIGENCE FLOU (SORTIE) ---
            # Si on est à la sortie et qu'on ne trouve personne, on cherche "quelqu'un qui ressemble"
            if is_exit_cam and not session_entry:
                all_open = ParkingSession.query.filter_by(is_open=True).all()
                best_match = None
                min_dist = 100
                
                for s in all_open:
                    # On compare la plaque actuelle avec celle en base
                    s_plate = s.meta_data.get("plate", s.identity.replace("PLATE:", ""))
                    dist = levenshtein_distance(plate_raw, s_plate)
                    
                    # Si c'est proche (<= 2 erreurs pour la sortie, on est plus cool)
                    if dist <= 2 and dist < min_dist:
                        min_dist = dist
                        best_match = s
                
                if best_match:
                    print(f"[OCR] 🔮 Correction auto : '{plate_raw}' interprété comme '{best_match.identity}'")
                    session_entry = best_match

            # --- FUSION BADGE (Logique existante) ---
            if session_entry and "badge" in source.lower() and "cam" in session_entry.source.lower():
                session_entry.source = "badge" 
                session_entry.last_event = now
                db.session.commit()
                try: send_cmd("barriere_entree", "100") 
                except: pass
                return
            
            # --- CAS 1 : GESTION DE L'ENTRÉE (Cas 1 + FUSION INVERSE)
            if is_entry_cam:
                # A. Si une session existe déjà pour cette plaque exacte
                if session_entry:
                     if "badge" in session_entry.source.lower(): return 
                     return
                # 👇👇👇 B. FUSION INVERSE : Badge OU PIN passé AVANT la caméra ? 🔗 👇👇👇
                # On cherche une session ouverte par "badge" OU "code" il y a moins de 60s
                orphan_auth_session = ParkingSession.query\
                    .filter(ParkingSession.is_open == True)\
                    .filter(or_(ParkingSession.source.like('%badge%'), ParkingSession.identity.startswith('PINCODE')))\
                    .filter(ParkingSession.opened_at > (now - 60))\
                    .order_by(desc(ParkingSession.opened_at))\
                    .first()

                # Si on trouve une session autorisée récente (Badge ou PIN)
                if orphan_auth_session:
                    print(f"🔗 [FUSION INVERSE] Caméra suit une Auth (Badge/PIN) ! Fusion dans session {orphan_auth_session.id}")
                    
                    # ATTENTION : Si c'est un PIN, on NE change PAS l'identité en "PLATE:..."
                    # Sinon la session deviendrait payante !
                    # On garde l'identité "PINCODE_..." ou "BADGE:..." pour conserver la gratuité/abonnement.
                    
                    is_pin = orphan_auth_session.identity.startswith("PINCODE")
                    
                    # On enrichit les métadonnées avec la plaque lue par la caméra
                    current_meta = dict(orphan_auth_session.meta_data)
                    current_meta.update(meta) # Ajoute l'image, la plaque, etc.
                    current_meta["plate_confirmed_by_cam"] = True
                    orphan_auth_session.meta_data = current_meta
                    
                    # On note la double source
                    if is_pin:
                        orphan_auth_session.source = "pin_et_cam"
                    else:
                        orphan_auth_session.source = "badge_et_cam"
                        # Pour les badges, on aime bien remplacer l'identité par la plaque car le badge est lié à la plaque
                        # Mais pour le PIN, on garde PINCODE.
                        if "plate" in current_meta:
                             orphan_auth_session.identity = f"PLATE:{current_meta['plate']}"

                    db.session.commit()
                    
                    # On envoie l'info au dashboard
                    socketio.emit('parking_event', {"meta": {"plate": plate_raw, "cam_id": "Fusion"}})
                    return # STOP ! On ne crée pas de doublon.
                
                # 🛑 ANTI-DOUBLON INTELLIGENT 🛑
                # On vérifie si une voiture similaire est entrée il y a moins de 5 min
                if not identity.startswith("PINCODE"): 
                    recent_sessions = ParkingSession.query.filter_by(is_open=True).all()
                    for s in recent_sessions:
                        s_plate = s.meta_data.get("plate", s.identity.replace("PLATE:", ""))
                        dist = levenshtein_distance(plate_raw, s_plate)
                        time_diff = now - s.opened_at
                        
                        if dist <= FUZZY_TOLERANCE and time_diff < DUPLICATE_WINDOW:
                            print(f"[OCR] 🛡️ Doublon évité : '{plate_raw}' trop proche de '{s_plate}' entré il y a {int(time_diff)}s.")
                            # On ouvre quand même la barrière au cas où le mec a calé
                            try: send_cmd("barriere_entree", "100")
                            except: pass
                            return

                # Logique standard d'entrée...
                current_count = ParkingSession.query.filter_by(is_open=True).count()
                if current_count >= PARKING_CAPACITY:
                    print(f"⛔ REFUS ENTRÉE : Parking complet pour {identity}")
                    
                    try: 
                        # 1. On met à jour le statut global (au cas où)
                        _ensure_mqtt()
                        mqtt_client.publish("parking/display/text", "COMPLET")
                        
                        # 2. On affiche la POPUP D'ERREUR au conducteur
                        clean_plate = meta.get("plate", "Inconnu")
                        
                        # On utilise le même canal que le paiement, mais avec un "Prix" spécial
                        mqtt_client.publish("parking/payment/req", json.dumps({
                            "plate": clean_plate,
                            "price": "STOP",  # Sera affiché en rouge
                            "cause": "PARKING COMPLET\nACCES REFUSE" # Le message explicatif
                        }))
                        print(f"📟 [DISPLAY] Message 'COMPLET' envoyé pour {clean_plate}")
                        
                    except Exception as e: 
                        print(f"Erreur MQTT Full: {e}")
                        
                    return

                last_closed = ParkingSession.query.filter_by(identity=identity, is_open=False).order_by(desc(ParkingSession.closed_at)).first()
                if last_closed and last_closed.closed_at and (now - last_closed.closed_at < COOLDOWN_NEW): 
                    print(f"⛔ Rejet entrée immédiate (Sortie détectée il y a {int(now - last_closed.closed_at)}s)")
                    return

                new_session = ParkingSession(identity=identity, source=source, meta_data=meta, opened_at=now, last_event=now, is_open=True)
                db.session.add(new_session)
                db.session.commit()
                print(f"[PARKING] ✅ Entrée {identity}")
                
                try: 
                    send_cmd("barriere_entree", "100")
                    remaining = PARKING_CAPACITY - (current_count + 1)
                    mqtt_client.publish("parking/display/text", f"LIBRE:{remaining}")
                    socketio.emit('parking_update', {'count': current_count + 1, 'capacity': PARKING_CAPACITY, 'action': 'entry', 'last_update': _fmt_dt(now)})
                except: pass
                return

            # --- CAS 2 : SORTIE ---
            elif is_exit_cam:

                # ============================================================
                # 1. TOLÉRANCE POST-SORTIE (Le temps pour sortir)
                # ============================================================
                # On cherche si cette plaque est sortie récemment
                recent_closed = ParkingSession.query\
                    .filter(ParkingSession.identity == identity)\
                    .filter(ParkingSession.is_open == False)\
                    .order_by(desc(ParkingSession.closed_at))\
                    .first()
                
                # 👇 CORRECTION 1 : On passe de 120s à 600s (10 minutes)
                if recent_closed and recent_closed.closed_at and (now - recent_closed.closed_at) < 300:
                    print(f"🔓 [TOLERANCE] Réouverture immédiate pour {identity} (Sortie < 5 min)")
                    send_cmd("barriere_sortie", "100")
                    return
                    
                # ============================================================
                # 2. GESTION DES CAS SANS ENTRÉE CONNUE (Fantômes)
                # ============================================================
                if not session_entry: 
                    
                    # A. Vérifier si c'est le BADGE qui vient de fermer la session
                    recently_closed = ParkingSession.query\
                        .filter(ParkingSession.identity == identity)\
                        .filter(ParkingSession.is_open == False)\
                        .order_by(desc(ParkingSession.closed_at))\
                        .first()
                    
                    if recently_closed and (now - recently_closed.closed_at) < 60:
                        print(f"👋 [SORTIE] Ignoré : Session fermée par Badge récemment.")
                        send_cmd("barriere_sortie", "100") 
                        return

                    # 👇 CORRECTION 2 : PROTECTION ANTI-DOUBLON FANTÔME 👇
                    # On vérifie si un fantôme a DÉJÀ été créé pour cette plaque il y a moins de 60s
                    existing_ghost = ParkingSession.query\
                        .filter(ParkingSession.identity == identity)\
                        .filter(ParkingSession.source == "ghost_exit")\
                        .filter(ParkingSession.opened_at > (now - 60))\
                        .first()

                    if existing_ghost:
                        print(f"👻 [GHOST] Doublon détecté pour {identity}. On utilise la session existante.")
                        session_entry = existing_ghost
                    
                    else:
                        # B. CRÉATION DU FANTÔME (Seulement si pas de doublon récent)
                        print(f"👻 [EXIT] Véhicule fantôme détecté : {plate_raw}")

                        pricing = get_pricing_config()
                        lost_ticket_price = pricing["daily_max"]

                        ghost_session = ParkingSession(
                            identity=identity,
                            source="ghost_exit", 
                            meta_data=meta,
                            opened_at=now - 86400, # Entrée simulée hier
                            last_event=now,
                            is_open=True, 
                            price_eur=lost_ticket_price
                        )
                        db.session.add(ghost_session)
                        db.session.commit()
                        
                        print(f"⚠️ Session 'Ticket Perdu' créée (ID: {ghost_session.id})")
                        session_entry = ghost_session

                # ============================================================
                # 3. LOGIQUE STANDARD (Calcul Prix & Paiement)
                # ============================================================
                if session_entry:
                    duration = max(0.0, now - session_entry.opened_at)
                    
                    session_plate = session_entry.meta_data.get("plate", "").replace(" ", "").replace("-", "")
                    is_vip = False
                    
                    all_badges = Badge.query.all()
                    for b in all_badges:
                        if b.plate and b.plate.replace(" ", "").replace("-", "") == session_plate:
                            is_vip = True
                            break
                    
                    # Logique de prix
                    if session_entry.source == "ghost_exit":
                         price = session_entry.price_eur # Prix déjà fixé pour les fantômes
                    elif is_vip:
                         price = 0.0
                         print(f"[PARKING] 🌟 Sortie VIP (Abonné) pour {session_plate}")
                    else:
                         price = _compute_price(duration, session_entry.source, session_entry.identity)
                    
                    payment_ts = session_entry.payment_time
                    time_since_payment = now - payment_ts
                    is_payment_valid = (payment_ts > 0) and (time_since_payment < (EXIT_DELAY_MINUTES * 60))
                    
                    # Si impayé -> Demande Paiement
                    if price > 0 and not is_payment_valid and not session_entry.paid:
                        print(f"[PARKING] ⛔ Sortie refusée (Impayé : {price}€)")
                        try:
                            clean_plate = session_entry.meta_data.get("plate", "Inconnue")
                            
                            # 👇 ENVOI DE LA CAUSE DU PRIX FORT 👇
                            cause_msg = ""
                            if session_entry.source == "ghost_exit":
                                cause_msg = "ENTREE NON DETECTEE\nFORFAIT JOURNALIER"
                            
                            _ensure_mqtt()
                            mqtt_client.publish("parking/payment/req", json.dumps({
                                "plate": clean_plate,
                                "price": f"{price:.2f}",
                                "cause": cause_msg
                            }))
                            print(f"📟 [DISPLAY] Demande affichage paiement pour {clean_plate}")
                        except Exception as e:
                            print(f"⚠️ Erreur MQTT: {e}")
                        
                        session_entry.last_event = now
                        db.session.commit()
                        return # On arrête ici, barrière fermée

                    # Si payé ou gratuit -> Ouverture
                    session_entry.is_open = False
                    session_entry.closed_at = now
                    session_entry.last_event = now
                    session_entry.duration_s = duration
                    session_entry.price_eur = price
                    
                    if meta:
                        current_meta = dict(session_entry.meta_data)
                        current_meta.update(meta)
                        session_entry.meta_data = current_meta
                    
                    db.session.commit()
                    print(f"[PARKING] 👋 Sortie {identity}")
                    
                    try: 
                        send_cmd("barriere_sortie", "100")
                        count_after = ParkingSession.query.filter_by(is_open=True).count()
                        mqtt_client.publish("parking/display/text", f"LIBRE:{PARKING_CAPACITY - count_after}")
                        _notify_parking_telegram(session_entry)
                        socketio.emit('parking_update', {'count': count_after, 'capacity': PARKING_CAPACITY, 'action': 'exit', 'last_update': _fmt_dt(now)})
                    except: pass

# ============================================================================
# Routes
# ============================================================================
def _build_tables():
    active_q = ParkingSession.query.filter_by(is_open=True).order_by(ParkingSession.opened_at).all()
    active_sessions = []
    for s in active_q:
        dur_min = int(round((_now_ts() - s.opened_at) / 60.0))
        active_sessions.append({"id": s.id, "plate": s.meta_data.get("plate", ""), "source": s.source, "opened": _fmt_dt(s.opened_at), "duration": f"{dur_min} min"})
    hist_q = ParkingSession.query.filter_by(is_open=False).order_by(desc(ParkingSession.closed_at)).limit(20).all()
    finished_sessions = []
    for s in hist_q:
        dur_min = int(round(s.duration_s / 60.0))
        finished_sessions.append({"plate": s.meta_data.get("plate", ""), "source": s.source, "opened": _fmt_dt(s.opened_at), "closed": _fmt_dt(s.closed_at), "duration": f"{dur_min} min", "price": f"{s.price_eur:.2f} €"})
    return active_sessions, finished_sessions

@app.route("/dashboard")
@login_required
def dashboard():
    active, finished = _build_tables()
    return render_template("index.html", meteo=meteo_data, sessions=finished, sessions_active=active, sessions_finished=finished, parking_count=len(active))

@app.route("/parking")
@login_required
def parking_sessions():
    active, finished = _build_tables()
    return render_template("parking.html", sessions_active=active, sessions_finished=finished, parking_count=len(active))

@app.route("/api/parking/count")
@login_required
def api_parking_count():
    count = ParkingSession.query.filter_by(is_open=True).count()
    return jsonify({"count": count, "at": _fmt_dt(_now_ts()).split(" ")[1], "capacity": PARKING_CAPACITY})

@app.route('/api/delete_session', methods=['POST'])
@login_required
def delete_session():
    data = request.json or {}
    s = ParkingSession.query.get(data.get('id'))
    if s:
        db.session.delete(s)
        db.session.commit()
        new_count = ParkingSession.query.filter_by(is_open=True).count()

        # --- AJOUT : MISE À JOUR DU BANDEAU LED (MQTT) ---
        remaining = PARKING_CAPACITY - new_count
        msg = "COMPLET" if remaining <= 0 else f"LIBRE:{remaining}"
        
        try:
            _ensure_mqtt()
            mqtt_client.publish("parking/display/text", msg, retain=True)
            print(f"🗑️ [DELETE] Session supprimée. MQTT mis à jour : {msg}", flush=True)
        except Exception as e:
            print(f"⚠️ Erreur MQTT Delete: {e}")
            
        socketio.emit('parking_update', {'count': new_count, 'capacity': PARKING_CAPACITY, 'action': 'delete'})
        return jsonify({"status": "ok"})
    return jsonify({"status": "error"}), 404

@app.route('/api/force_finish', methods=['POST'])
@login_required
def force_finish():
    data = request.json or {}
    s = ParkingSession.query.get(data.get('id'))
    
    if not s: 
        return jsonify({"status": "error", "message": "Introuvable"}), 404
        
    # 1. On valide le paiement
    s.paid = True
    s.payment_time = _now_ts()
    db.session.commit()

    try:
        _ensure_mqtt()
        mqtt_client.publish("parking/payment/success", "1")
        print("✅ [MQTT] Ordre fermeture QR Code envoyé (Force Finish)", flush=True)
    except Exception as e:
        print(f"⚠️ Erreur MQTT Success: {e}")
    # 2. INTELLIGENCE DE SORTIE :
    # Si la voiture a été vue (bloquée) il y a moins de 5 minutes, 
    # on considère qu'elle est toujours devant la barrière -> ON OUVRE !
    if (_now_ts() - s.last_event) < 300: # 300s = 5 minutes
        print(f"🔓 [AUTO-EXIT] Paiement confirmé pour {s.identity}, ouverture immédiate.", flush=True)
        # On simule un événement caméra sortie pour déclencher toute la logique (Barrière, Display, Ticket...)
        # On utilise 'cam2' pour être sûr que c'est traité comme une sortie
        _handle_parking_event(s.identity, source="cam2", meta=s.meta_data)
        return jsonify({"status": "ok", "message": "Paiement validé & Barrière ouverte automatiquement."})
    
    return jsonify({"status": "ok", "message": "Paiement validé. Le client peut se présenter à la sortie."})

@app.route("/")
def root_redirect(): return redirect(url_for("dashboard"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("username"): return redirect(url_for("dashboard"))
    if request.method == "POST":
        u, p = (request.form.get("username") or "").strip(), (request.form.get("password") or "").strip()
        user = USERS.get(u)
        if user and check_password_hash(user["password_hash"], p): session["username"] = u; return redirect(url_for("dashboard"))
        flash("Erreur", "error")
    return render_template("login.html")

@app.route("/logout")
def logout(): session.clear(); return redirect(url_for("login"))

@app.route("/api/meteo", methods=["POST"])
def api_meteo_post():
    global meteo_data
    try: meteo_data = request.get_json(force=True) or {}; meteo_data["timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S"); return jsonify({"status": "ok"})
    except: return jsonify({"status": "error"}), 400

@app.route("/meteo", methods=["GET"])
def get_meteo(): return jsonify(meteo_data or {"status": "vide"})

@app.route("/control", methods=["POST"])
@login_required
def control(): d = request.get_json(silent=True) or {}; send_cmd(d.get("cible"), d.get("commande")); return jsonify({"status": "ok"})

@app.route("/etat/ascenseur")
@login_required
def etat_ascenseur(): return jsonify(ascenseur_state)

@app.route('/api/camera/move', methods=['POST'])
@login_required
def move_camera():
    d = request.get_json(silent=True) or {}; 
    try: _ensure_mqtt(); mqtt_client.publish("parking/camera/cmd", f"{d.get('cam_id')}:{d.get('direction')}"); return jsonify({"status": "ok"})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/enroll/start', methods=['POST'])
@login_required
def start_enrollment():
    global enrollment_mode
    enrollment_mode = True
    print("📡 [ENROLL] Mode enrôlement activé pour 30s", flush=True)
    
    # Timeout de sécurité 30s
    def auto_disable():
        global enrollment_mode
        time.sleep(30)
        if enrollment_mode:
            enrollment_mode = False
            print("⏳ [ENROLL] Timeout - Mode désactivé", flush=True)
    
    threading.Thread(target=auto_disable).start()
    return jsonify({"status": "ok"})

@app.route("/badges", methods=["GET", "POST"])
@login_required
def manage_badges():
    if request.method == "POST":
        a = request.form.get("action")
        u = (request.form.get("uid") or "").strip().upper()
        p = (request.form.get("plate") or "").strip().upper()

        if a == "add" and u:
            send_acl_add(u)
            # SAUVEGARDE EN BASE DE DONNÉES (Persistant)
            existing = Badge.query.get(u)
            if not existing:
                db.session.add(Badge(uid=u, plate=p))
            else:
                existing.plate = p
            db.session.commit()
        
        elif a == "del" and u:
            send_acl_del(u)
            # SUPPRESSION EN BASE
            existing = Badge.query.get(u)
            if existing:
                db.session.delete(existing)
                db.session.commit()

        elif a == "full":
            b = request.form.get("bulk") or ""
            uids = [l.strip().split(":")[-1].strip() for l in b.splitlines() if l.strip()]
            send_acl_full(uids)

        send_acl_list_request()
        return redirect(url_for("manage_badges"))

    return render_template("badges.html")

@app.route("/api/config/pin", methods=["POST"])
@login_required
def api_set_pin():
    data = request.json or {}
    new_pin = str(data.get("pin", "")).strip()
    pin_type = data.get("type", "entry") 
    
    if not new_pin.isdigit() or len(new_pin) < 4 or len(new_pin) > 8:
        return jsonify({"status": "error", "message": "Le PIN doit contenir 4 à 8 chiffres."}), 400

    try:
        _ensure_mqtt()
        
        topic = "parking/config/pin"
        label = "ENTRÉE"
        db_key = "pin_entry"
        
        if pin_type == "exit":
            topic = "parking/config/exit_pin"
            label = "SORTIE"
            db_key = "pin_exit"

        # 1. Sauvegarde en Base de Données
        set_db_config(db_key, new_pin)

        # 2. Envoi MQTT Retained (Mémoire pour la STM32)
        mqtt_client.publish(topic, new_pin, retain=True)
        
        # 3. On force une resynchro pour être sûr que l'affichage suit
        sync_stm32_state()
        
        return jsonify({"status": "ok", "message": f"PIN {label} changé en {new_pin}"})
    except Exception as e:
        print(f"Erreur API PIN: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

    
@app.route('/stats')
@login_required
def stats_page(): return render_template('stats.html')

@app.route('/api/stats_data')
@login_required
def api_stats_data():
    active_count = ParkingSession.query.filter_by(is_open=True).count()
    free_spots = max(0, PARKING_CAPACITY - active_count)
    days_map = {}
    for i in range(6, -1, -1):
        d = time.time() - (i * 86400)
        days_map[datetime.fromtimestamp(d).strftime("%d/%m")] = 0.0
    closed_sessions = ParkingSession.query.filter_by(is_open=False).all()
    for s in closed_sessions:
        if s.closed_at:
            s_date = datetime.fromtimestamp(s.closed_at).strftime("%d/%m")
            if s_date in days_map: days_map[s_date] += s.price_eur
    return jsonify({"occupancy": {"active": active_count, "free": free_spots}, "revenue": {"labels": list(days_map.keys()), "data": list(days_map.values())}})

# Routes Stripe
@app.route('/portal')
def portal(): return render_template('portal.html')

@app.route('/api/get_payment_link', methods=['POST'])
def get_payment_link():
    data = request.json or {}; plate_search = (data.get('plate') or "").strip().upper().replace(" ", "").replace("-", "")
    sessions = ParkingSession.query.filter_by(is_open=True).all()
    found = None
    for s in sessions:
        if plate_search in (s.meta_data.get("plate") or "").upper().replace(" ", "").replace("-", ""): found = s; break
    if not found: return jsonify({"status": "error", "message": "Véhicule non trouvé"})
    price = _compute_price(max(0.0, _now_ts() - found.opened_at), found.source)
    if price <= 0: return jsonify({"status": "free", "message": "Gratuit", "price": 0})
    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'], metadata={'plate': plate_search},
            line_items=[{'price_data': {'currency': 'eur', 'product_data': {'name': f'Stationnement - {plate_search}'}, 'unit_amount': int(price * 100)}, 'quantity': 1}],
            mode='payment', success_url=url_for('payment_success', _external=True) + f"?plate={plate_search}", cancel_url=url_for('portal', _external=True))
        return jsonify({"status": "ok", "price": f"{price:.2f}", "url": checkout_session.url})
    except Exception as e: return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/stripe_webhook', methods=['POST'])
def stripe_webhook():
    payload = request.get_data(as_text=True); sig_header = request.headers.get('Stripe-Signature'); webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    if not webhook_secret: return "Secret missing", 400
    try: event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except: return "Invalid", 400
    if event['type'] == 'checkout.session.completed':
        plate_target = event['data']['object'].get('metadata', {}).get('plate')
        if plate_target:
            with app.app_context():
                # On cherche la session active correspondante
                sessions = ParkingSession.query.filter_by(is_open=True).all()
                for s in sessions:
                    s_plate = (s.meta_data.get("plate") or "").upper().replace(" ", "").replace("-", "")
                    if plate_target == s_plate:
                        s.payment_time = _now_ts()
                        s.paid = True
                        db.session.commit()
                        
                        print(f"💰 [STRIPE] Paiement reçu pour {s_plate}", flush=True)
                        
                        try:
                            _ensure_mqtt()
                            mqtt_client.publish("parking/payment/success", "1")
                            print("✅ [MQTT] Ordre fermeture QR Code envoyé à la STM32")
                        except Exception as e:
                            print(f"⚠️ Erreur MQTT Success: {e}")
                        # --- LE MÊME DECLENCHEUR AUTOMATIQUE ---
                        # Si le client est devant la barrière (vu récemment), on ouvre !
                        if (_now_ts() - s.last_event) < 300:
                            print(f"🔓 [AUTO-EXIT] Déblocage immédiat suite paiement Stripe.", flush=True)
                            _handle_parking_event(s.identity, source="cam2", meta=s.meta_data)
                        # ---------------------------------------
                        break
    return "Success", 200

@app.route('/payment_success')
def payment_success(): return """<div style="text-align:center;margin-top:50px;"><h1>✅ Paiement validé</h1><p>Barrière ouverte à l'approche.</p><a href="/portal">Retour</a></div>"""

@app.route('/api/badges')
@login_required
def api_badges_route():
    # On croise la liste active de la STM32 avec les plaques en Base de Données
    combined = []
    seen = set()
    
    for uid in current_badges_from_stm32:
        if isinstance(uid, str) and uid not in seen:
            seen.add(uid)
            # On cherche la plaque en DB
            b_db = Badge.query.get(uid)
            plate = b_db.plate if b_db else ""
            combined.append({"uid": uid, "plate": plate})
            
    return jsonify(combined)

@app.route("/tarifs", methods=["GET", "POST"])
@login_required
def manage_tarifs():
    if request.method == "POST":
        try:
            # Récupération et conversion des valeurs du formulaire
            free_min = int(request.form.get("free_minutes", 30))
            chunk_min = int(request.form.get("chunk_minutes", 15))
            price = float(request.form.get("price_per_chunk", 0.5))
            d_max = float(request.form.get("daily_max", 20.0))
            
            # Sauvegarde en base (via SystemConfig)
            set_db_config("tariff_free_min", free_min)
            set_db_config("tariff_chunk_min", chunk_min)
            set_db_config("tariff_price_chunk", price)
            set_db_config("tariff_daily_max", d_max)
            
            flash("✅ Tarifs mis à jour avec succès !", "success")
        except ValueError:
            flash("❌ Erreur : Veuillez entrer des nombres valides.", "error")
        
        return redirect(url_for("manage_tarifs"))

    # Affichage de la page avec les valeurs actuelles
    return render_template("tarifs.html", p=get_pricing_config())

# Callback MQTT
def _on_mqtt_message(client, userdata, msg):
    global current_badges_from_stm32, _last_acl_ack, ascenseur_state
    
    topic = msg.topic
    # On décode proprement le payload
    try:
        payload = msg.payload.decode("utf-8", errors="ignore").strip().strip("\x00")
    except:
        return
    # --- DEBUG : AFFICHER TOUT CE QUI ARRIVE DE L'ASCENSEUR ---
    if "ascenseur" in topic:
        print(f"📥 [MQTT DEBUG] Topic: {topic} | Payload: '{payload}'", flush=True)
        
    #  Réception de la demande STM32 
    if topic == "parking/sync/req":
        print("📥 [MQTT] Demande de synchro reçue de la STM32", flush=True)
        # On lance la synchro dans un thread pour ne pas bloquer la boucle MQTT
        # On met 0.2s de délai entre les paquets pour éviter l'erreur "RX buffer"
        threading.Thread(target=sync_stm32_state, args=(0.2,)).start()
        return
    
    # 1. Mise à jour ascenseur
    if topic == "parking/ascenseur/state":
        val = None
        # On essaie d'interpréter le payload intelligemment
        try:
            # Cas 1 : C'est du JSON {"current": 1}
            data = json.loads(payload)
            if isinstance(data, dict):
                val = data.get("current")
            else:
                # Cas 2 : C'est juste un chiffre "1" envoyé en JSON valide
                val = data 
        except:
            # Cas 3 : C'est du texte brut (ex: "ETAGE1", "1", "RDC")
            payload_str = str(payload).upper()
            if "RDC" in payload_str or "0" in payload_str: val = 0
            elif "1" in payload_str: val = 1
            elif "2" in payload_str: val = 2
        
        # Si on a réussi à trouver une valeur, on met à jour
        if val is not None:
            try:
                # C'EST ICI QUE CA PLANTE
                ascenseur_state = {
                    "current": int(val), 
                    "at": time.strftime("%H:%M:%S")
                }
                print(f"✅ [ASCENSEUR] SUCCÈS : État mis à jour vers {val}", flush=True)
            except Exception as e:
                # 👇 CECI VA NOUS DONNER LA VRAIE CAUSE 👇
                print(f"🔥 [ASCENSEUR CRASH] Impossible de mettre à jour : {e}", flush=True)
                print(f"   -> Type de val: {type(val)} | Valeur: {val}")
        return

    # 2. Entrée par badge
    if topic == "parking/barriere":
        # CORRECTION : On vérifie si c'est le PINCODE avant de normaliser
        # CORRECTION : On vérifie si c'est le PINCODE avant de normaliser
        if payload == "PIN_IN":
            print(f"📥 [MQTT] Code PIN Entrée validé", flush=True)
            unique_id = f"PINCODE_{int(time.time())}" 
            
            #  FUSION CAMÉRA -> PIN 
            with app.app_context():
                # 1. On cherche une session Caméra "Orpheline" récente (< 60s)
                # C'est une voiture vue par la caméra mais qui tape son code juste après.
                orphan_cam_session = ParkingSession.query\
                    .filter(ParkingSession.is_open == True)\
                    .filter(ParkingSession.source.like('%cam%'))\
                    .filter(ParkingSession.opened_at > (time.time() - 60))\
                    .order_by(desc(ParkingSession.opened_at))\
                    .first()

                if orphan_cam_session:
                    # FUSION !
                    print(f"🔗 [FUSION PIN] La session Caméra {orphan_cam_session.id} devient une session PIN (Gratuite).")
                    
                    # On sauvegarde l'ancienne plaque dans les métadonnées
                    old_meta = dict(orphan_cam_session.meta_data)
                    plate_detected = old_meta.get("plate", orphan_cam_session.identity.replace("PLATE:", ""))
                    
                    # IMPORTANT : On change l'identité en "PINCODE_..." 
                    # Cela garantit que _compute_price renverra 0€ (Gratuit)
                    orphan_cam_session.identity = unique_id 
                    orphan_cam_session.source = "cam_et_pin"
                    
                    # On met à jour les métadonnées
                    old_meta["auth_method"] = "PIN"
                    if plate_detected and "plate" not in old_meta:
                        old_meta["plate"] = plate_detected
                    orphan_cam_session.meta_data = old_meta
                    
                    db.session.commit()
                    
                    # On signale au dashboard que c'est validé
                    socketio.emit('parking_event', {
                        "meta": {
                            "plate": "Code PIN OK",
                            "cam_id": "Fusion",
                            "image": ""
                        }
                    })
                
                else:
                    # PAS DE CAMÉRA VUE AVANT -> CRÉATION SESSION PIN CLASSIQUE
                    # On garde "plate": "Code PIN" pour que l'affichage reste propre
                    _handle_parking_event(unique_id, source="badge_entree", meta={"plate": "Code PIN"})
            
            # Mise à jour compteur (Commun aux deux cas)
            with app.app_context():
                count = ParkingSession.query.filter_by(is_open=True).count()
                socketio.emit('parking_update', {'count': count, 'capacity': PARKING_CAPACITY, 'last_update': _fmt_dt(_now_ts())})
            return

        elif payload == "PIN_OUT":
            print(f"📤 [MQTT] Code PIN Sortie validé", flush=True)
            
            with app.app_context():
                # 1. On cherche la plus ancienne session ouverte qui commence par "PINCODE"
                # .startswith() génère un LIKE 'PINCODE%' SQL
                oldest_pin_session = ParkingSession.query\
                    .filter(ParkingSession.identity.startswith("PINCODE"))\
                    .filter_by(is_open=True)\
                    .order_by(ParkingSession.opened_at.asc())\
                    .first()
                
                if oldest_pin_session:
                    print(f"👋 [AUTO-EXIT] Fermeture de la session PINCODE la plus ancienne : {oldest_pin_session.identity}")
                    
                    # 2. On déclenche la sortie pour cet identifiant précis (ex: PINCODE_1735123001)
                    # source="code_sortie" contient le mot "sortie", donc _handle_parking_event saura que c'est une sortie
                    _handle_parking_event(
                        oldest_pin_session.identity, 
                        source="code_sortie", 
                        meta={"plate": "Code PIN"}
                    )
                else:
                    print(f"⚠️ [AUTO-EXIT] Aucune session PINCODE ouverte à fermer.")
            return
        else:
            uid = _normalize_uid8(payload)
            
        if uid:
            # =================================================================
            # 1. PROTECTION ANTI-REBOND (COOLDOWN 15s)
            # =================================================================
            now = time.time()
            last_seen = _badge_cooldowns.get(uid, 0)
            
            if (now - last_seen) < 15.0:
                print(f"⏳ [COOLDOWN] Badge {uid} ignoré (déjà traité il y a {int(now - last_seen)}s)", flush=True)
                return

            _badge_cooldowns[uid] = now
            print(f"📥 [MQTT] Réception badge : {uid}", flush=True)

            # =================================================================
            # 2. MODE ENRÔLEMENT (SCAN)
            # =================================================================
            global enrollment_mode
            if enrollment_mode:
                print(f"✨ [ENROLL] Nouveau badge capturé : {uid}", flush=True)
                socketio.emit('enroll_event', {'uid': uid})
                enrollment_mode = False
                return 
            
            # =================================================================
            # 3. VERIFICATION : Le badge est-il connu ?
            # =================================================================
            badge_entry = None
            is_known = False
            
            with app.app_context():
                if uid == "PINCODE":
                    is_known = True
                else:
                    badge_entry = Badge.query.get(uid)
                    if badge_entry: is_known = True

            if not is_known:
                print(f"⛔ [ACCESS] Badge {uid} inconnu", flush=True)
                return

            # =================================================================
            # 4. LOGIQUE INTELLIGENTE : ENTRÉE OU SORTIE ?
            # =================================================================
            display_text = f"Badge {uid}"
            plate = None
            
            # Récupération des infos du badge
            if badge_entry and badge_entry.plate:
                plate = badge_entry.plate
                display_text = plate
            elif uid == "PINCODE":
                display_text = "Code PIN"

            source_decision = "badge_entree" # Valeur par défaut
            identity_to_use = ""

            with app.app_context():
                # On cherche si une session est DÉJÀ ouverte pour ce véhicule
                existing_session = None
                
                # A. Recherche par Plaque (si dispo)
                if plate:
                    open_sessions = ParkingSession.query.filter_by(is_open=True).all()
                    for s in open_sessions:
                        s_plate = s.meta_data.get("plate", "")
                        # Comparaison souple (sans tirets/espaces)
                        if s_plate.replace("-","").replace(" ","") == plate.replace("-","").replace(" ",""):
                            existing_session = s
                            break
                
                # B. Recherche par UID (si pas trouvé par plaque)
                if not existing_session:
                    existing_session = ParkingSession.query.filter_by(identity=f"BADGE:{uid}", is_open=True).first()

                # --- CAS 1 : LA SESSION EXISTE DÉJÀ ---
                if existing_session:
                    # 🛡️ PROTECTION "DOUBLE CHECK-IN" (Le Badge confirme l'entrée caméra)
                    # Si la session a moins de 60 secondes, on refuse de la fermer.
                    duree_vie = now - existing_session.opened_at
                    if duree_vie < 60:
                        print(f"🛡️ [FUSION] Badge scanné {int(duree_vie)}s après ouverture caméra.")
                        print(f"   -> Interprété comme CONFIRMATION D'ENTRÉE (et non sortie).")
                        
                        # On met juste à jour les métadonnées pour dire "Badge a confirmé"
                        current_meta = dict(existing_session.meta_data)
                        current_meta["badge_check"] = "confirmed"
                        existing_session.meta_data = current_meta
                        db.session.commit()
                        
                        # On renvoie l'ordre d'ouvrir la barrière (au cas où la caméra a raté l'ouverture physique)
                        send_cmd("barriere_entree", "100")
                        return # ON S'ARRÊTE ICI. Pas de sortie, pas de nouvelle session.

                    else:
                        # C'est une vraie sortie (> 60s)
                        print(f"🔄 [LOGIC] Véhicule sortant (Durée: {int(duree_vie/60)} min)")
                        source_decision = "badge_sortie"
                        identity_to_use = existing_session.identity
            
                # --- CAS 2 : PAS DE SESSION BADGE (ENTRÉE) -> TENTATIVE DE FUSION ---
                else:
                    # Avant de créer une nouvelle session "BADGE:...", on cherche une "Session Orpheline"
                    # Créée par une caméra ("cam") il y a moins de 15 secondes.
                    orphane_session = ParkingSession.query\
                        .filter(ParkingSession.is_open == True)\
                        .filter(ParkingSession.source.like('%cam%'))\
                        .filter(ParkingSession.opened_at > (now - 15))\
                        .order_by(desc(ParkingSession.opened_at))\
                        .first()

                    if orphane_session:
                        # 🔗 FUSION ! (MERGE)
                        print(f"🔗 [FUSION] Badge {uid} associé à la session existante {orphane_session.identity}")
                        
                        # On met à jour la session existante au lieu d'en créer une nouvelle
                        orphane_session.identity = f"PLATE:{plate}" if plate else f"BADGE:{uid}"
                        orphane_session.source = "cam_et_badge" # On note la double source
                        
                        # Mise à jour des métadonnées
                        current_meta = dict(orphane_session.meta_data)
                        current_meta["badge_uid"] = uid
                        if plate: current_meta["plate"] = plate
                        orphane_session.meta_data = current_meta
                        
                        db.session.commit()
                        
                        # Feedback immédiat
                        send_cmd("barriere_entree", "100")
                        mqtt_client.publish("parking/display/text", f"BIENVENUE {plate if plate else ''}")
                        
                        return # ON S'ARRÊTE ICI. La session caméra est devenue la session officielle.

                    else:
                        # Vraiment personne n'a été vu par la caméra -> Création nouvelle session standard
                        print(f"🆕 [LOGIC] Nouvelle entrée badge (Caméra aveugle ou moto)")
                        source_decision = "badge_entree"
                        if plate: identity_to_use = f"PLATE:{plate}"
                        else: identity_to_use = f"BADGE:{uid}"

            # =================================================================
            # 5. EXECUTION (Seulement si pas de fusion/protection ci-dessus)
            # =================================================================
            
            # A. Feedback Visuel Dashboard
            try:
                socketio.emit('parking_event', {
                    "meta": {
                        "plate": display_text,
                        "cam_id": "Badge",
                        "image": ""
                    }
                })
            except: pass

            # B. Action (Ouvrir barrière In ou Out, Calculer prix, etc.)
            _handle_parking_event(
                identity_to_use, 
                source=source_decision, 
                meta={"uid8": uid, "plate": plate} if plate else {"uid8": uid}
            )
            
            # C. Mise à jour compteur places
            with app.app_context():
                count = ParkingSession.query.filter_by(is_open=True).count()
                socketio.emit('parking_update', {'count': count, 'capacity': PARKING_CAPACITY, 'last_update': _fmt_dt(_now_ts())})

    # 3. Réception de la liste des badges
    if topic == "parking/acl/list":
        try:
            # La STM32 envoie : {"op": "LIST", "entries": ["UID1", "UID2"]}
            data = json.loads(payload)
            raw_entries = data.get("entries", [])
            
            # On met à jour la liste globale proprement
            new_list = []
            for item in raw_entries:
                if isinstance(item, dict):
                    new_list.append(item.get("uid"))
                else:
                    new_list.append(str(item))
            
            current_badges_from_stm32 = new_list
            print(f"[MQTT] Liste badges mise à jour : {len(current_badges_from_stm32)} badges reçus", flush=True)
        except Exception as e:
            print(f"[MQTT] Erreur parsing liste badges : {e}", flush=True)

mqtt_client.on_message = _on_mqtt_message


@app.route('/api/admin/adjust_count', methods=['POST'])
@login_required
def adjust_count():
    data = request.json or {}
    action = data.get("action") # "inc" ou "dec"
    
    with app.app_context():
        current_count = ParkingSession.query.filter_by(is_open=True).count()
        
        if action == "inc":
            if current_count >= PARKING_CAPACITY:
                return jsonify({"status": "error", "message": "Parking déjà complet"}), 400
            
            # On crée une session "Fantôme" pour occuper une place
            ts = int(time.time())
            ghost = ParkingSession(
                identity=f"MANUAL_{ts}", 
                source="admin_manual", 
                opened_at=time.time(), 
                last_event=time.time(), 
                is_open=True,
                meta_data={"plate": "Réservé / Manuel"}
            )
            db.session.add(ghost)
            db.session.commit()
            
        elif action == "dec":
            if current_count <= 0:
                return jsonify({"status": "error", "message": "Parking déjà vide"}), 400
            
            # Stratégie de suppression :
            # 1. D'abord on cherche une session "MANUAL" (Fantôme)
            target = ParkingSession.query.filter(
                ParkingSession.is_open == True, 
                ParkingSession.source == "admin_manual"
            ).first()
            
            # 2. Si pas de fantôme, on supprime la session LA PLUS ANCIENNE (Drift correction)
            if not target:
                target = ParkingSession.query.filter_by(is_open=True).order_by(ParkingSession.opened_at.asc()).first()
            
            if target:
                # On la supprime physiquement ou on la ferme proprement
                db.session.delete(target) 
                db.session.commit()
        
        # Mise à jour immédiate des clients
        new_count = ParkingSession.query.filter_by(is_open=True).count()
        socketio.emit('parking_update', {
            'count': new_count, 
            'capacity': PARKING_CAPACITY, 
            'last_update': _fmt_dt(time.time())
        })
        
        # Synchro STM32
        remaining = PARKING_CAPACITY - new_count
        msg = "COMPLET" if remaining <= 0 else f"LIBRE:{remaining}"
        _ensure_mqtt()
        mqtt_client.publish("parking/display/text", msg, retain=True)

    return jsonify({"status": "ok", "new_count": new_count})
    
# ==========================================
# REMPLACE LA FONCTION api_plate_event PAR CECI
# ==========================================
@app.route("/api/plate_event", methods=["POST"])
def api_plate_event():
    print("\n🔔 [DEBUG] REQUÊTE REÇUE sur /api/plate_event", flush=True)
    
    try:
        data = request.get_json(force=True) or {}
        p = data.get("plate")
        c = data.get("cam_id")
        img = data.get("image", "")

        if not p:
            return jsonify({"error": "no plate"}), 400

        print(f"✅ [DEBUG] Traitement Plaque : {p} | Cam : {c}", flush=True)

        # 👇👇👇 C'EST LE BLOC MAGIQUE QUI MANQUAIT 👇👇👇
        # On envoie immédiatement l'info au navigateur (Dashboard)
        try:
            socketio.emit('parking_event', {
                "meta": {
                    "plate": p,
                    "cam_id": str(c), # On s'assure que c'est une string
                    "image": img
                }
            })
            print("📡 [SOCKET] Event envoyé au navigateur avec succès !", flush=True)
        except Exception as e:
            print(f"⚠️ [SOCKET ERROR] Impossible d'envoyer au dashboard : {e}", flush=True)
        # 👆👆👆 FIN DU BLOC MAGIQUE 👆👆👆

        # Logique métier (Base de données, Barrière...)
        _handle_parking_event(
            f"PLATE:{p}", 
            source=f"cam_{c}", 
            meta={"plate": p, "cam_id": c, "image": img}
        )
        return jsonify({"status": "ok", "plate": p}), 200

    except Exception as e:
        print(f"🔥 [CRASH API] : {e}", flush=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/history')
@login_required
def api_history():
    now = time.time()
    labels = []
    data = []
    
    # On génère 24 points (1 par heure) pour les dernières 24h
    for i in range(24, -1, -1):
        # On remonte dans le temps : il y a 24h, 23h, ... jusqu'à maintenant
        t = now - (i * 3600)
        
        # Une voiture était présente à l'instant 't' si :
        # 1. Elle est entrée AVANT 't'
        # 2. ET (Elle est encore là OU elle est sortie APRÈS 't')
        count = ParkingSession.query.filter(
            ParkingSession.opened_at <= t,
            or_(ParkingSession.closed_at == None, ParkingSession.closed_at > t)
        ).count()
        
        # On formate l'heure (ex: "14h")
        # On utilise datetime.fromtimestamp car 't' est un float
        labels.append(datetime.fromtimestamp(t).strftime("%Hh"))
        data.append(count)
        
    return jsonify({"labels": labels, "data": data})

# ============================================================================
# TÂCHE DE FOND : NETTOYAGE BDD
# ============================================================================
def task_cleanup_db():
    """ Supprime les sessions fermées depuis plus de 30 jours """
    while True:
        try:
            # On attend 24h (86400 secondes)
            time.sleep(86400) 
            
            with app.app_context():
                cutoff = time.time() - (30 * 86400) # 30 jours
                # On supprime
                deleted_count = ParkingSession.query\
                    .filter(ParkingSession.is_open == False)\
                    .filter(ParkingSession.closed_at < cutoff)\
                    .delete()
                
                db.session.commit()
                if deleted_count > 0:
                    print(f"🧹 [MAINTENANCE] Nettoyage BDD : {deleted_count} vieilles sessions supprimées.", flush=True)
        except Exception as e:
            print(f"⚠️ Erreur nettoyage BDD: {e}", flush=True)

# Lancement au démarrage
threading.Thread(target=task_cleanup_db, daemon=True).start()

@app.before_request
def init_mqtt_once():
    if not getattr(app, "mqtt_init_done", False): _ensure_mqtt(); send_acl_list_request(); sync_stm32_state(); app.mqtt_init_done = True

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    socketio.run(app, host="0.0.0.0", port=port, debug=True)
