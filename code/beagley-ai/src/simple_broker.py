import asyncio
import logging
from amqtt.broker import Broker

# Configuration SIMPLE
# On laisse amqtt trouver ses plugins tout seul, on fixe juste le bug de l'intervalle
config = {
    "listeners": {
        "default": {
            "type": "tcp",
            "bind": "0.0.0.0:1883"
        }
    },
    "sys_interval": 10,
    "auth": {
        "allow_anonymous": True
    }
}

async def start_broker():
    # On garde les logs simples
    formatter = "[%(asctime)s] %(name)s %(levelname)s - %(message)s"
    logging.basicConfig(level=logging.INFO, format=formatter)
    
    # On fait taire les logs inutiles
    logging.getLogger("transitions").setLevel(logging.WARNING)
    
    broker = Broker(config)
    await broker.start()
    print("🚀 Broker MQTT démarré sur le port 1883 (Config: Auto + Fix)")
    
    while True:
        await asyncio.sleep(10)

if __name__ == "__main__":
    try:
        asyncio.run(start_broker())
    except KeyboardInterrupt:
        print("Arrêt du broker.")
