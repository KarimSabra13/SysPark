import sys
import time
import fcntl
import ctypes
import random
import threading
import paho.mqtt.client as mqtt

# --- Configuration Matérielle ---
DEVICE = "/dev/spidev0.0"
SPEED_HZ = 1000000
NUM_MODULES = 4

# --- Configuration MQTT ---
MQTT_BROKER = "127.0.0.1" # Le bridge tourne en local
MQTT_TOPIC = "parking/display/text"

# --- Variables Globales d'État ---
PARKING_STATUS = "NORMAL" # "NORMAL" ou "FULL"
FREE_SPOTS = "?"          # Nombre de places
CURRENT_TEXT = "LIBRE"    # Texte brut reçu

# --- Constantes SPI ---
SPI_IOC_MAGIC = ord('k')
SPI_IOC_MESSAGE_1 = 0x40206b00

class spi_ioc_transfer(ctypes.Structure):
    _fields_ = [
        ("tx_buf", ctypes.c_ulonglong),
        ("rx_buf", ctypes.c_ulonglong),
        ("len", ctypes.c_uint),
        ("speed_hz", ctypes.c_uint),
        ("delay_usecs", ctypes.c_ushort),
        ("bits_per_word", ctypes.c_ubyte),
        ("cs_change", ctypes.c_ubyte),
        ("tx_nbits", ctypes.c_ubyte),
        ("rx_nbits", ctypes.c_ubyte),
        ("pad", ctypes.c_ushort),
    ]

# --- POLICE D'ÉCRITURE ---
# --- POLICE D'ÉCRITURE CORRIGÉE (Ligne par ligne, Row 0 = Haut) ---
FONT = {
    ' ': [0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00],
    
    # --- LETTRES (8x8 Pixels) ---
    'B': [0xFC, 0x82, 0x82, 0xFC, 0x82, 0x82, 0xFC, 0x00],
    'I': [0x3C, 0x18, 0x18, 0x18, 0x18, 0x18, 0x3C, 0x00],
    'E': [0xFE, 0x80, 0x80, 0xF8, 0x80, 0x80, 0xFE, 0x00],
    'N': [0xC6, 0xE6, 0xF6, 0xDE, 0xCE, 0xC6, 0xC6, 0x00],
    'V': [0xC6, 0xC6, 0xC6, 0xC6, 0x6C, 0x38, 0x10, 0x00],
    'U': [0xC6, 0xC6, 0xC6, 0xC6, 0xC6, 0xC6, 0x7C, 0x00],
    
    # Corrections pour LIBRE / COMPLET
    'L': [0xC0, 0xC0, 0xC0, 0xC0, 0xC0, 0xC0, 0xFE, 0x00], # Barre gauche + Bas
    'R': [0xFC, 0x66, 0x66, 0x7C, 0x6C, 0x66, 0xE3, 0x00], # Jambe diagonale corrigée
    'C': [0x3C, 0x66, 0xC0, 0xC0, 0xC0, 0x66, 0x3C, 0x00], # Arrondi
    'O': [0x3C, 0x66, 0xC3, 0xC3, 0xC3, 0x66, 0x3C, 0x00],
    'M': [0xC3, 0xE7, 0xFF, 0xDB, 0xC3, 0xC3, 0xC3, 0x00], # M pointu
    'P': [0xFC, 0x66, 0x66, 0x7C, 0x60, 0x60, 0x60, 0x00], # Boucle en haut
    'T': [0xFE, 0x18, 0x18, 0x18, 0x18, 0x18, 0x18, 0x00], # Barre en haut
    'S': [0x3C, 0x66, 0x60, 0x3C, 0x06, 0x66, 0x3C, 0x00],
    'A': [0x18, 0x3C, 0x66, 0x66, 0x7E, 0x66, 0x66, 0x00],

    # --- CHIFFRES (Compact 4x8) ---
    '0': [0x60, 0x90, 0x90, 0x90, 0x90, 0x90, 0x60, 0x00],
    '1': [0x20, 0x60, 0x20, 0x20, 0x20, 0x20, 0x70, 0x00],
    '2': [0x60, 0x90, 0x10, 0x20, 0x40, 0x80, 0xF0, 0x00],
    '3': [0x60, 0x90, 0x10, 0x60, 0x10, 0x90, 0x60, 0x00],
    '4': [0x20, 0x60, 0xA0, 0xA0, 0xF0, 0x20, 0x20, 0x00],
    '5': [0xF0, 0x80, 0xE0, 0x10, 0x10, 0x90, 0x60, 0x00],
    '6': [0x60, 0x90, 0x80, 0xE0, 0x90, 0x90, 0x60, 0x00],
    '7': [0xF0, 0x10, 0x20, 0x40, 0x40, 0x40, 0x40, 0x00],
    '8': [0x60, 0x90, 0x90, 0x60, 0x90, 0x90, 0x60, 0x00],
    '9': [0x60, 0x90, 0x90, 0x70, 0x10, 0x90, 0x60, 0x00],
    ':': [0x00, 0x60, 0x60, 0x00, 0x60, 0x60, 0x00, 0x00],

    # AJOUT : La Croix "X" (Dessinée ligne par ligne)
    'x': [0xC3, 0xE7, 0x7E, 0x3C, 0x3C, 0x7E, 0xE7, 0xC3],
}

# --- Gestion MQTT ---
def on_connect(client, userdata, flags, rc):
    print(f"[MQTT] Connecté au bridge local (Code: {rc})")
    
    # 1. On s'abonne pour recevoir les mises à jour
    client.subscribe(MQTT_TOPIC)
    
    # 2. C'EST LA CORRECTION MAGIQUE :
    # On crie au serveur : "Eh ! Je viens de m'allumer, donne-moi le nombre de places !"
    # Le serveur va répondre sur 'parking/display/text' quelques millisecondes plus tard.
    client.publish("parking/sync/req", "boot_request")

def on_message(client, userdata, msg):
    global PARKING_STATUS, FREE_SPOTS, CURRENT_TEXT
    try:
        text = msg.payload.decode('utf-8').strip()
        print(f"[MQTT] Reçu: {text}")
        
        if text == "COMPLET":
            PARKING_STATUS = "FULL"
        elif text.startswith("LIBRE:"):
            PARKING_STATUS = "NORMAL"
            parts = text.split(":")
            if len(parts) > 1:
                FREE_SPOTS = parts[1]
        else:
            # Cas fallback (ex: "BIENVENUE")
            PARKING_STATUS = "NORMAL"
            
        CURRENT_TEXT = text
    except Exception as e:
        print(f"Erreur Parsing MQTT: {e}")

def start_mqtt():
    client = mqtt.Client("led_controller")
    client.on_connect = on_connect
    client.on_message = on_message
    try:
        client.connect(MQTT_BROKER, 1883, 60)
        client.loop_start() # Thread séparé
    except Exception as e:
        print(f"Erreur connexion MQTT: {e}")

# --- Gestion SPI Bas Niveau ---
def send_spi(fd, data_bytes):
    data_array = bytearray(data_bytes)
    tx_buf = (ctypes.c_char * len(data_array)).from_buffer(data_array)
    transfer = spi_ioc_transfer()
    transfer.tx_buf = ctypes.addressof(tx_buf)
    transfer.rx_buf = 0
    transfer.len = len(data_array)
    transfer.speed_hz = SPEED_HZ
    transfer.bits_per_word = 8
    try:
        fcntl.ioctl(fd, SPI_IOC_MESSAGE_1, transfer)
    except OSError: pass

def send_command_all(fd, reg, value):
    payload = [reg, value] * NUM_MODULES
    send_spi(fd, payload)

def refresh_screen(fd, buffer_grid):
    for row_idx in range(8):
        payload = []
        for module_idx in range(NUM_MODULES - 1, -1, -1):
            payload.append(row_idx + 1)
            payload.append(buffer_grid[module_idx][row_idx])
        send_spi(fd, payload)

# --- Fonctions d'Affichage ---

def draw_char_at(buffer_grid, char, start_x):
    if char not in FONT: return
    pattern = FONT[char]
    width = 4 if char.isdigit() or char == ':' else 8
    for x in range(width):
        screen_x = start_x + x
        if 0 <= screen_x < 32:
            col_bit = 7 - x
            for row in range(8):
                if (pattern[row] >> col_bit) & 1:
                    module_idx = screen_x // 8
                    mod_col = screen_x % 8
                    target_module = 3 - module_idx
                    buffer_grid[target_module][row] |= (0x80 >> mod_col)

def show_clock(fd, duration=3):
    # Heure UTC+1 (Patch rapide)
    timestamp = time.time() + 3600 
    time_struct = time.localtime(timestamp)
    now = time.strftime("%H:%M", time_struct)
    
    video_buffer = [[0]*8 for _ in range(NUM_MODULES)]
    positions = [2, 8, 14, 18, 24] # Positionnement précis HH:MM
    
    for i, char in enumerate(now):
        if i < len(positions):
            draw_char_at(video_buffer, char, positions[i])
        
    refresh_screen(fd, video_buffer)
    time.sleep(duration)

def show_message_scroll(fd, text, speed=0.03):
    """
    Fait défiler un message de la DROITE vers la GAUCHE.
    Méthode 'Scanner' (Identique à final_demo.py pour garantir le sens).
    """
    # 1. Pré-calcul de la position de chaque caractère
    # car la largeur varie (4px pour les chiffres, 8px pour les lettres)
    char_offsets = []
    current_offset = 0
    total_width = 0
    
    for char in text:
        char_offsets.append(current_offset)
        # Largeur : 4px pour chiffres/:, 8px pour le reste
        w = 4 if char.isdigit() or char == ':' else 8
        current_offset += w
    
    total_width = current_offset
    
    # 2. Boucle de défilement (Pixel par Pixel)
    # On part de -32 (texte caché à droite) et on avance vers la fin du texte
    # Ce qui donne l'impression que le texte glisse vers la GAUCHE.
    for scroll_x in range(-32, total_width + 1):
        video_buffer = [[0]*8 for _ in range(NUM_MODULES)]
        
        # Pour chaque colonne de l'écran physique (0 à 31)
        for screen_x in range(32):
            # Quelle colonne du texte global on doit afficher ici ?
            text_x = scroll_x + screen_x
            
            # Si on est dans les limites du texte
            if 0 <= text_x < total_width:
                # Retrouver quel caractère correspond à ce pixel 'text_x'
                # On parcourt les offsets à l'envers pour trouver le bon
                found_char = None
                col_in_char = 0
                
                # Recherche rapide du caractère correspondant
                for i, offset in enumerate(char_offsets):
                    char_width = 4 if text[i].isdigit() or text[i] == ':' else 8
                    if offset <= text_x < (offset + char_width):
                        found_char = text[i]
                        col_in_char = text_x - offset
                        break
                
                if found_char and found_char in FONT:
                    pattern = FONT[found_char]
                    
                    # Dessin du pixel
                    for row in range(8):
                        # Bit 7 est à gauche. On décale selon la colonne interne du caractère
                        # col_in_char va de 0 (gauche) à 7 (droite)
                        if (pattern[row] >> (7 - col_in_char)) & 1:
                            
                            # Logique matérielle (Inversion des modules)
                            module_idx = screen_x // 8
                            module_col = screen_x % 8
                            target_module = 3 - module_idx # Inversion 3, 2, 1, 0
                            
                            video_buffer[target_module][row] |= (0x80 >> module_col)

        refresh_screen(fd, video_buffer)
        time.sleep(speed)

def run_ball_pass(fd):
    """Une seule traversée de balle (Droite -> Gauche)"""
    pos_x, pos_y = 31.0, 0.0
    vel_x, vel_y = -0.6, 0.0 # Un peu plus rapide
    gravity = 0.25
    bounce = -0.85

    # Tant que la balle est dans l'écran
    while pos_x > -2:
        video_buffer = [[0]*8 for _ in range(NUM_MODULES)]
        
        vel_y += gravity
        pos_y += vel_y
        pos_x += vel_x
        
        if pos_y > 7:
            pos_y = 7
            vel_y *= bounce
            if abs(vel_y) < gravity: vel_y = 0
        if pos_y < 0: pos_y = 0; vel_y *= -0.5

        dx, dy = int(pos_x), int(pos_y)
        if 0 <= dx < 32 and 0 <= dy < 8:
            target_mod = 3 - (dx // 8)
            video_buffer[target_mod][dy] |= (0x80 >> (dx % 8))
            
        refresh_screen(fd, video_buffer)
        time.sleep(0.03)

# --- Boucle Principale ---
# --- Initialisation Agressive (Anti-Bug Boot) ---
def hard_reset_display(fd):
    print("🧹 [SPI] Nettoyage du bus et reset modules...")
    
    # 1. Envoi de commandes NO-OP (0x00) pour vider le registre à décalage
    # Si des bits parasites traînent, on les pousse dehors.
    for _ in range(NUM_MODULES * 2):
        send_spi(fd, [0x00, 0x00])
        
    time.sleep(0.1)

    # 2. FORCE BRUTE : Désactiver le "Display Test" (C'est lui qui allume tout)
    # On l'envoie 3 fois pour être sûr.
    for _ in range(3):
        send_command_all(fd, 0x0F, 0x00) # Registre 0x0F = Display Test -> 0 = OFF
    
    # 3. Shutdown puis Wakeup (Reboot logiciel du MAX7219)
    send_command_all(fd, 0x0C, 0x00) # Shutdown
    time.sleep(0.2)
    send_command_all(fd, 0x0C, 0x01) # Wakeup
    
    # 4. Configuration standard
    send_command_all(fd, 0x09, 0x00) # No Decode
    send_command_all(fd, 0x0A, 0x01) # Intensité (Faible au début)
    send_command_all(fd, 0x0B, 0x07) # Scan Limit (Toutes lignes)
    
    # 5. Effacer l'écran (Tout éteindre)
    video_buffer = [[0]*8 for _ in range(NUM_MODULES)]
    refresh_screen(fd, video_buffer)
    print("✅ [SPI] Initialisation terminée.")

def adjust_brightness(fd):
    """Règle la luminosité selon l'heure (Mode Nuit automatique)"""
    # Récupère l'heure actuelle (0-23)
    # Note: Nécessite que l'heure Linux soit à peu près correcte
    current_hour = time.localtime().tm_hour
    
    # Nuit (20h - 07h) -> Intensité MINIMUM (0)
    # Jour (07h - 20h) -> Intensité MOYENNE (2) ou FORTE (5 à 15)
    if current_hour >= 20 or current_hour < 7:
        intensity = 0 
    else:
        intensity = 2 # Tu peux monter jusqu'à 15 si c'est en plein soleil
        
    # On envoie la commande au registre INTENSITY (0x0A) sur tous les modules
    send_command_all(fd, 0x0A, intensity)

# --- Boucle Principale ---
def main_loop():
    # 1. Démarrer MQTT en arrière-plan
    start_mqtt()
    
    while True:
        fd = None
        try:
            fd = open(DEVICE, "wb+", buffering=0)
            
            # Reset agressif au démarrage (comme vu précédemment)
            hard_reset_display(fd)

            while True:
                # --- GESTION LUMINOSITÉ (Mode Nuit) ---
                # On le fait à chaque cycle pour s'adapter en temps réel
                adjust_brightness(fd)

                # ---------------------------------------------------------
                # SCÉNARIO 1 : PARKING COMPLET
                # ---------------------------------------------------------
                if PARKING_STATUS == "FULL":
                    # A. Clignotement de la CROIX (4 fois)
                    # On affiche le motif 'x' sur les 4 écrans simultanément
                    video_buffer = [[0]*8 for _ in range(NUM_MODULES)]
                    cross_pattern = FONT['x']
                    
                    # Remplissage du buffer avec des croix partout
                    for mod_idx in range(NUM_MODULES):
                        target = 3 - mod_idx # Inversion matérielle
                        for row in range(8):
                            video_buffer[target][row] = cross_pattern[row]
                    
                    # Clignotement
                    for _ in range(3): 
                        refresh_screen(fd, video_buffer) # Allumé (Croix)
                        time.sleep(0.6)
                        
                        # Eteint (Buffer vide)
                        refresh_screen(fd, [[0]*8 for _ in range(NUM_MODULES)])
                        time.sleep(0.3)

                    # B. Message "COMPLET" (Défilement)
                    show_message_scroll(fd, "COMPLET ", speed=0.04)
                    
                    # C. Heure
                    show_clock(fd, duration=2)

                # ---------------------------------------------------------
                # SCÉNARIO 2 : NORMAL (Place libre)
                # ---------------------------------------------------------
                else:
                    # 1. Balle rebondissante
                    run_ball_pass(fd)
                    
                    # 2. Bienvenue
                    show_message_scroll(fd, "BIENVENUE ")
                    
                    # 3. Libre
                    msg_libre = f"LIBRE: {FREE_SPOTS} "
                    show_message_scroll(fd, msg_libre)
                    
                    # 4. Heure
                    show_clock(fd, duration=3)

        except Exception as e:
            print(f"Erreur main_loop: {e}")
            if fd: 
                try: fd.close() 
                except: pass
            time.sleep(5)

if __name__ == "__main__":
    try:
        main_loop()
    except KeyboardInterrupt:
        print("Arrêt.")
