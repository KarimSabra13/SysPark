#!/usr/bin/env python3
import requests
import time
import json
import paho.mqtt.client as mqtt

# === CONFIGURATION ===
SERVER_URL = "https://parking-server-r38v.onrender.com/api/meteo"  # <-- nouvelle URL Render
API_KEY = "0f52c0a3ca9f37943729976bdf075d96"          # clé OpenWeatherMap
CITY = "Lyon,FR"
POLL_SECONDS = 60  # 10 min entre deux mises à jour

MQTT_BROKER = "192.168.10.1"  # IP de ta BeagleBone (broker MQTT)
MQTT_PORT = 1883
MQTT_TOPIC = "parking/meteo"

# === INITIALISATION MQTT ===
mqtt_client = mqtt.Client("BeagleBone_Meteo")

def connect_mqtt():
    """(Ré)établit une connexion MQTT fiable"""
    connected = False
    while not connected:
        try:
            mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
            print(f"📡 Connecté au broker MQTT ({MQTT_BROKER}:{MQTT_PORT})")
            connected = True
        except Exception as e:
            print("⚠️ MQTT broker non joignable :", e)
            print("⏳ Nouvelle tentative dans 5 secondes...")
            time.sleep(5)

connect_mqtt()


# === FONCTION MÉTÉO ===
def get_weather_and_air():
    """Récupère la météo + qualité de l’air"""
    try:
        # --- Données météo ---
        url_weather = f"http://api.openweathermap.org/data/2.5/weather?q={CITY}&appid={API_KEY}&units=metric&lang=fr"
        meteo_resp = requests.get(url_weather, timeout=10)
        meteo = meteo_resp.json()

        if "main" not in meteo or "weather" not in meteo:
            print("❌ Erreur API météo :", meteo)
            return None

        lat, lon = meteo["coord"]["lat"], meteo["coord"]["lon"]

        # --- Données qualité de l’air ---
        url_air = f"http://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={API_KEY}"
        air_resp = requests.get(url_air, timeout=10)
        air = air_resp.json()

        if "list" not in air:
            print("❌ Erreur API air :", air)
            return None

        # --- Extraction utile ---
        co2 = round(air["list"][0]["components"].get("co", 0))
        aqi = air["list"][0]["main"]["aqi"]  # 1=Bon, 5=Mauvais
        air_label = "sain" if aqi <= 2 else "pollué"

        pluie = "Aucune pluie"
        if "rain" in meteo:
            rain_1h = meteo["rain"].get("1h", 0)
            if rain_1h > 0:
                pluie = f"Pluie: {rain_1h} mm/h"

        meteo_data = {
            "ville": meteo.get("name", CITY),
            "description": meteo["weather"][0]["description"].capitalize(),
            "temperature": meteo["main"]["temp"],
            "humidite": meteo["main"]["humidity"],
            "vent": round(meteo["wind"]["speed"] * 3.6, 1),
            "vent_dir": meteo["wind"].get("deg", 0),
            "prevision": meteo["main"]["temp_max"],
            "pluie": pluie,
            "co2": co2,
            "air": air_label
        }

        print("✅ Données météo + air récupérées :", json.dumps(meteo_data, ensure_ascii=False))
        return meteo_data

    except Exception as e:
        print("❌ Erreur de récupération météo :", e)
        return None


# === FONCTIONS D’ENVOI ===
def send_to_server(data):
    try:
        r = requests.post(SERVER_URL, json=data, timeout=5)
        if r.ok:
            print("📤 Données envoyées au serveur Flask :", r.json())
        else:
            print("⚠️ Erreur serveur Flask :", r.status_code, r.text)
    except Exception as e:
        print("❌ Erreur d’envoi Flask :", e)


def send_to_mqtt(data):
    """Publie les données sur le topic MQTT"""
    global mqtt_client
    try:
        payload = json.dumps(data)
        mqtt_client.publish(MQTT_TOPIC, payload, retain=True)
        print(f"📤 Message MQTT envoyé → {MQTT_TOPIC} : {payload}")
    except Exception as e:
        print("❌ Erreur d’envoi MQTT :", e)
        print("🔄 Tentative de reconnexion MQTT...")
        connect_mqtt()


# === BOUCLE PRINCIPALE ===
if __name__ == "__main__":
    print("🚀 Service météo lancé. Boucle de mise à jour active...\n")
    while True:
        try:
            meteo = get_weather_and_air()
            if meteo:
                send_to_server(meteo)
                send_to_mqtt(meteo)
            else:
                print("⚠️ Aucune donnée météo disponible (API vide ou erreur réseau).")

            print(f"⏲️ Prochaine mise à jour dans {POLL_SECONDS/60:.0f} minutes...\n")
            time.sleep(POLL_SECONDS)

        except KeyboardInterrupt:
            print("🛑 Arrêt manuel détecté.")
            break
        except Exception as e:
            print("❌ Erreur inattendue :", e)
            print("🔁 Nouvelle tentative dans 10 secondes...")
            time.sleep(10)

