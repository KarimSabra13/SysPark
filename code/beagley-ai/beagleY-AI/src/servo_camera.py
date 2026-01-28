import time
import os
import sys
import math

# ===========================================================================
# CONFIGURATION I2C / PCA9685
# ===========================================================================
I2C_BUS_ID = 1
PCA9685_ADDRESS = 0x40
SERVO_FREQ = 50 

SERVOS = {
    "cam1_pan":  {"port": 0, "min": 0,  "max": 180},
    "cam1_tilt": {"port": 1, "min": 20,  "max": 115},
    "cam2_pan":  {"port": 99,  "min": 0,  "max": 180},
    "cam2_tilt": {"port": 99,  "min": 0, "max": 180}  
}

angles = {"cam1_pan": 90, "cam1_tilt": 90, "cam2_pan": 90, "cam2_tilt": 90}
STEP = 5 

# ===========================================================================
# CLASSE DRIVER PCA9685
# ===========================================================================
try:
    from smbus2 import SMBus
except ImportError:
    print("❌ ERREUR: Librairie smbus2 manquante.")
    sys.exit(1)

class PCA9685:
    MODE1 = 0x00
    PRESCALE = 0xFE
    LED0_ON_L = 0x06

    def __init__(self, bus_id, address):
        # On ne met pas de try/except ici pour laisser l'erreur remonter
        # à la fonction appelante (init_hardware) qui gérera la boucle de retry
        self.bus = SMBus(bus_id)
        self.address = address
        self.reset()
        self.set_pwm_freq(SERVO_FREQ)
        print(f"✅ PCA9685 Init OK sur Bus {bus_id} @ 0x{address:02X}")

    def write(self, reg, value):
        if self.bus: 
            try:
                self.bus.write_byte_data(self.address, reg, value)
            except OSError:
                print("⚠️ Erreur I/O I2C")

    def read(self, reg):
        if self.bus:
            try:
                return self.bus.read_byte_data(self.address, reg)
            except OSError:
                return 0
        return 0

    def reset(self):
        self.write(self.MODE1, 0x00)
        time.sleep(0.01)

    def set_pwm_freq(self, freq_hz):
        prescaleval = 25000000.0 / 4096.0 / float(freq_hz) - 1.0
        prescale = int(math.floor(prescaleval + 0.5))
        oldmode = self.read(self.MODE1)
        newmode = (oldmode & 0x7F) | 0x10
        self.write(self.MODE1, newmode)
        self.write(self.PRESCALE, prescale)
        self.write(self.MODE1, oldmode)
        time.sleep(0.01)
        self.write(self.MODE1, oldmode | 0x80)

    def set_pwm(self, channel, on, off):
        base_reg = self.LED0_ON_L + 4 * channel
        self.write(base_reg, on & 0xFF)
        self.write(base_reg + 1, on >> 8)
        self.write(base_reg + 2, off & 0xFF)
        self.write(base_reg + 3, off >> 8)

    def set_angle(self, channel, angle):
        if not self.bus: return
        angle = max(0, min(180, angle))
        min_pulse = 150
        max_pulse = 600
        pulse = int(min_pulse + (angle / 180.0) * (max_pulse - min_pulse))
        self.set_pwm(channel, 0, pulse)

# ===========================================================================
# LOGIQUE MQTT & MAIN
# ===========================================================================
try:
    import paho.mqtt.client as mqtt
except ImportError:
    print("❌ ERREUR: Librairie paho-mqtt manquante.")
    sys.exit(1)

pca = None

def init_hardware():
    global pca
    # BOUCLE DE CONNEXION HARDWARE
    # On reste bloqué ici tant que le module n'est pas vu sur le bus I2C
    while pca is None:
        try:
            print(f"⏳ Tentative de connexion au PCA9685 (Bus {I2C_BUS_ID})...")
            pca = PCA9685(I2C_BUS_ID, PCA9685_ADDRESS)
            
            # Si on arrive ici, c'est que ça a marché, on positionne les moteurs
            print("⚙️  Positionnement initial des moteurs...")
            for name, conf in SERVOS.items():
                port = conf["port"]
                if port != 99:
                    pca.set_angle(port, angles[name])
                    
        except Exception as e:
            print(f"⚠️ Echec init I2C: {e}")
            print("   -> Nouvelle tentative dans 5 secondes...")
            pca = None # On s'assure que pca reste None
            time.sleep(5) # On attend avant de réessayer

def on_connect(client, userdata, flags, rc):
    print(f"✅ Connecté au broker MQTT (rc={rc})")
    client.subscribe("parking/camera/cmd")

def on_message(client, userdata, msg):
    # Si le hardware a planté entre temps, on ignore
    if pca is None: 
        print("⛔ Commande ignorée (Hardware non prêt)")
        return

    payload = msg.payload.decode("utf-8")
    if payload.startswith("{") or "ville" in payload: return 
    print(f"📩 Commande Reçue: {payload}")
    
    try:
        if ":" not in payload: return
        cam_id, direction = payload.split(":", 1)
        
        pan_key = f"{cam_id}_pan"
        tilt_key = f"{cam_id}_tilt"
        target_key = None
        delta = 0
        
        if direction == "left":   target_key, delta = pan_key, STEP 
        elif direction == "right": target_key, delta = pan_key, -STEP
        elif direction == "up":    target_key, delta = tilt_key, -STEP 
        elif direction == "down":  target_key, delta = tilt_key, STEP
        
        if target_key and target_key in angles:
            servo_conf = SERVOS.get(target_key)
            if not servo_conf: return

            current_angle = angles[target_key]
            calc_angle = current_angle + delta
            limit_min = servo_conf.get("min", 0)
            limit_max = servo_conf.get("max", 180)
            new_angle = max(limit_min, min(limit_max, calc_angle))
            angles[target_key] = new_angle
            
            if servo_conf["port"] != 99:
                pca.set_angle(servo_conf["port"], new_angle)
                print(f"   -> Moteur {servo_conf['port']} (Angle {new_angle}°)")

    except Exception as e:
        print(f"❌ Erreur Traitement: {e}")

if __name__ == "__main__":
    # Lancement de l'init qui contient maintenant la boucle de sécurité
    init_hardware()
    
    client = mqtt.Client("beagley_servo_i2c")
    client.on_connect = on_connect
    client.on_message = on_message
    
    try:
        # On ajoute une boucle de retry pour le MQTT aussi au cas où
        while True:
            try:
                client.connect("127.0.0.1", 1883, 60)
                print("🚀 Service Servo I2C Démarré.")
                break
            except:
                print("⏳ Attente du Broker MQTT...")
                time.sleep(5)

        client.loop_forever()
    except KeyboardInterrupt:
        print("\nArrêt.")
