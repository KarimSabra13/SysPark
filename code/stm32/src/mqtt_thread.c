/*
 * MQTT Publisher Thread — Version Role-Aware
 * ---------------------------------------
 * S'adapte automatiquement selon BOARD_ROLE_ENTRY ou BOARD_ROLE_EXIT
 * défini dans role_config.h
 */

#include <zephyr/logging/log.h>
LOG_MODULE_REGISTER(net_mqtt_publisher_sample, LOG_LEVEL_INF);

#include <zephyr/kernel.h>
#include <zephyr/net/socket.h>
#include <zephyr/net/mqtt.h>
#include <zephyr/random/random.h>
#if defined(CONFIG_LOG_BACKEND_MQTT)
#include <zephyr/logging/log_backend_mqtt.h>
#endif

#include <strings.h>   /* pour strncasecmp */
#include <string.h>
#include <errno.h>
#include <zephyr/fs/fs.h>
#include <ff.h>
#include <zephyr/data/json.h>
#include <cJSON.h>
#include <zephyr/logging/log_output.h>

#include "uid_utils.h"
#include "config.h"
#include "net_sample_common.h"

/* CONFIGURATION DES RÔLES */
#include "role_config.h"

/* Structure pour passer l'info au Main */
struct payment_info {
    char plate[16];
    char price[10];
    char cause[64];
};
extern struct k_msgq payment_msgq; /* Définie dans main.c */

/* Référence au sémaphore défini dans main.c */
extern struct k_sem payment_success_sem;

/* === Configuration MQTT partagée avec le serveur === */
#ifndef MQTT_SECRET
#define MQTT_SECRET "CHANGE_ME"   /* même valeur que sur ton serveur Flask */
#endif

/* --- externs communs --- */
extern void update_parking_status(const char *text);
extern void save_exit_pin_to_sd(const char *new_pin);
extern void save_pin_to_sd(const char *new_pin);
extern void lcd_update_from_mqtt(const char *json_str);
extern void uid_normalize8(const char *in, char *out, size_t out_sz);

/* --- externs Spécifiques ENTREE --- */
#ifdef BOARD_ROLE_ENTRY
    extern void lcd_update_places(const char *text);
    extern int ascenseur_get_current_floor(void);
    extern void ascenseur_request_floor(int floor);
#endif

/* Référence au Mutex du fichier (défini dans main.c) */
extern struct k_mutex sd_lock;

/* --- buffers MQTT --- */
#define MQTT_BUF_SZ 1024
static uint8_t rx_buffer[MQTT_BUF_SZ];
static uint8_t tx_buffer[MQTT_BUF_SZ];

static struct mqtt_client client_ctx;
static struct sockaddr_storage broker;
static struct pollfd fds[1];
static int nfds;
static bool connected;


/* ============================================================
 * Helpers fichiers SD
 * ============================================================ */
static int write_full_acl_to_sd(cJSON *entries)
{
    k_mutex_lock(&sd_lock, K_FOREVER); 

    struct fs_file_t f;
    fs_file_t_init(&f);
    if (fs_open(&f, "/SD:/users.txt", FS_O_CREATE | FS_O_TRUNC | FS_O_WRITE) < 0) {
        k_mutex_unlock(&sd_lock); 
        return -1;
    }

    int n = cJSON_GetArraySize(entries);
    for (int i = 0; i < n; i++) {
        cJSON *item = cJSON_GetArrayItem(entries, i);
        const char *uid = cJSON_GetStringValue(cJSON_GetObjectItem(item, "uid"));
        if (!uid)
            continue;
        char line[128];
        snprintf(line, sizeof(line), "badge:%s\n", uid);
        fs_write(&f, line, strlen(line));
    }
    fs_close(&f);
    k_mutex_unlock(&sd_lock); 
    return 0;
}

static int append_acl_to_sd(const char *uid)
{
    k_mutex_lock(&sd_lock, K_FOREVER); 

    struct fs_file_t f;
    fs_file_t_init(&f);
    if (fs_open(&f, "/SD:/users.txt", FS_O_CREATE | FS_O_APPEND | FS_O_WRITE) < 0) {
        k_mutex_unlock(&sd_lock); 
        return -1;
    }

    char line[128];
    snprintf(line, sizeof(line), "badge:%s\n", uid);
    fs_write(&f, line, strlen(line));
    fs_close(&f);
    k_mutex_unlock(&sd_lock); 
    return 0;
}

static int delete_acl_from_sd(const char *uid)
{
    k_mutex_lock(&sd_lock, K_FOREVER); 

    struct fs_file_t f_in, f_out;
    fs_file_t_init(&f_in);
    fs_file_t_init(&f_out);
    
    if (fs_open(&f_in, "/SD:/users.txt", FS_O_READ) < 0){
        k_mutex_unlock(&sd_lock); 
        return -1;
    }
    if (fs_open(&f_out, "/SD:/tmp.txt", FS_O_CREATE | FS_O_TRUNC | FS_O_WRITE) < 0) {
        fs_close(&f_in);
        k_mutex_unlock(&sd_lock); 
        return -1;
    }

    char line[128];
    int pos = 0;
    char c;
    char uid8[9], tmp8[9];

    while (fs_read(&f_in, &c, 1) == 1) {
        if (c == '\n' || pos >= (int)sizeof(line) - 1) {
            line[pos] = '\0';
            pos = 0;

            if (strncasecmp(line, "badge:", 6) == 0) {
                const char *fuid = line + 6;
                uid_normalize8(fuid, uid8, sizeof(uid8));
                uid_normalize8(uid, tmp8, sizeof(tmp8));
                if (strcmp(uid8, tmp8) == 0)
                    continue; /* skip : on ne recopie pas la ligne à supprimer */
            }

            fs_write(&f_out, line, strlen(line));
            fs_write(&f_out, "\n", 1);
        } else {
            line[pos++] = c;
        }
    }

    fs_close(&f_in);
    fs_close(&f_out);
    
    fs_unlink("/SD:/users.txt");
    fs_rename("/SD:/tmp.txt", "/SD:/users.txt");
    
    k_mutex_unlock(&sd_lock); 
    return 0;
}

/* ============================================================
 * MQTT outils
 * ============================================================ */
static void prepare_fds(struct mqtt_client *client)
{
    if (client->transport.type == MQTT_TRANSPORT_NON_SECURE)
        fds[0].fd = client->transport.tcp.sock;
#if defined(CONFIG_MQTT_LIB_TLS)
    else if (client->transport.type == MQTT_TRANSPORT_SECURE)
        fds[0].fd = client->transport.tls.sock;
#endif
    fds[0].events = POLLIN;
    nfds = 1;
}

static void clear_fds(void) { nfds = 0; }

static int wait_evt(int timeout)
{
    int ret = 0;
    if (nfds > 0) {
        ret = poll(fds, nfds, timeout);
        if (ret < 0)
            LOG_ERR("poll error: %d", errno);
    }
    return ret;
}

/* ============================================================
 * Publication d’un message JSON (état ascenseur)
 * ============================================================ */
static void mqtt_publish_state(int floor) {
    if (!connected) return;

    char json[64];
    snprintf(json, sizeof(json), "{\"current\": %d}", floor);

    struct mqtt_publish_param pub = {0};
    pub.message.topic.topic.utf8 = (uint8_t *)"parking/ascenseur/state";
    pub.message.topic.topic.size = strlen("parking/ascenseur/state");
    pub.message.payload.data = json;
    pub.message.payload.len = strlen(json);
    pub.message.topic.qos = MQTT_QOS_0_AT_MOST_ONCE;
    pub.message_id = sys_rand16_get();
    
    pub.retain_flag = 1U;
    
    mqtt_publish(&client_ctx, &pub);
    LOG_INF("📤 État ascenseur publié : étage %d", floor);
}


/* ============================================================
 * Publication UID badge vers serveur
 * ============================================================ */
void mqtt_send_uid(const char *uid)
{
    if (!connected || uid == NULL || uid[0] == '\0') {
        LOG_WRN("MQTT non connecté ou UID vide");
        return;
    }

    struct mqtt_publish_param param = {0};
    param.message.topic.topic.utf8 = (uint8_t *)"parking/barriere";
    param.message.topic.topic.size = strlen("parking/barriere");
    param.message.topic.qos = MQTT_QOS_1_AT_LEAST_ONCE;
    param.message.payload.data = (void *)uid;
    param.message.payload.len = strlen(uid);
    param.message_id = sys_rand16_get();
    param.dup_flag = 0U;
    param.retain_flag = 0U;

    int rc = mqtt_publish(&client_ctx, &param);
    if (rc)
        LOG_ERR("mqtt_publish UID failed: %d", rc);
    else
        LOG_INF("UID envoyé sur MQTT (QoS 1) : %s", uid);
}

/* ============================================================
 * Handler des événements MQTT
 * ============================================================ */
static void request_server_sync(void) {
    if (!connected) return;
    struct mqtt_publish_param pub = {0};
    pub.message.topic.topic.utf8 = (uint8_t *)"parking/sync/req";
    pub.message.topic.topic.size = strlen("parking/sync/req");
    pub.message.payload.data = "1";
    pub.message.payload.len = 1;
    pub.message.topic.qos = MQTT_QOS_1_AT_LEAST_ONCE;
    pub.message_id = sys_rand16_get();
    mqtt_publish(&client_ctx, &pub);
    LOG_INF("🔄 Demande de synchronisation envoyée au serveur");
}

/* --- Prototypes internes --- */
void publish_acl_list(void);


void mqtt_evt_handler(struct mqtt_client *const client,
                      const struct mqtt_evt *evt)
{
    int err;

    switch (evt->type) {

    case MQTT_EVT_CONNACK:
        if (evt->result != 0) {
            LOG_ERR("MQTT connect failed %d", evt->result);
            break;
        }
        connected = true;
        LOG_INF("✅ MQTT connecté au broker");

        /* souscriptions */
        {
            const char *topics[] = {
                "parking/meteo",
                "parking/acl/add",
                "parking/acl/del",
                "parking/acl/full",
                "parking/acl/enroll",
                "parking/acl/get",
                "parking/ascenseur/cmd",
                "parking/ascenseur/get",
                "parking/config/pin",
                "parking/config/exit_pin",
                "parking/payment/req",
                "parking/display/text",
                "parking/payment/success"
            };
            for (int i = 0; i < ARRAY_SIZE(topics); i++) {
                struct mqtt_topic subs_topic = {
                    .topic = {.utf8 = (uint8_t *)topics[i],
                              .size = strlen(topics[i])},
                    .qos = MQTT_QOS_0_AT_MOST_ONCE};
                struct mqtt_subscription_list subs = {
                    .list = &subs_topic,
                    .list_count = 1U,
                    .message_id = sys_rand16_get()};
                err = mqtt_subscribe(client, &subs);
                LOG_INF("📡 Souscrit à %s (rc=%d)", topics[i], err);
            }
        }
        publish_acl_list();

        k_sleep(K_MSEC(100)); 
        request_server_sync();

        break;

    case MQTT_EVT_PUBLISH: {
        const struct mqtt_publish_param *p = &evt->param.publish;
        char payload[1024];
        
        memset(payload, 0, sizeof(payload));  

        int total = mqtt_readall_publish_payload(client, payload, sizeof(payload) - 1);

        if (total < 0) {
            if (total == -EIO) {
                LOG_WRN("MQTT: lecture interrompue (-EIO)");
            } else {
                LOG_ERR("Erreur lecture MQTT payload: %d", total);
                break;
            }
        } else {
            payload[total] = '\0';
        }
        payload[sizeof(payload) - 1] = '\0';

        const char *topic = p->message.topic.topic.utf8;
        LOG_INF("[MQTT] Reçu sur %s: %s", topic, payload);

        if (strncmp(topic, "parking/meteo", 13) == 0) {
            lcd_update_from_mqtt(payload);
        } 
        
        /* --- GESTION SPECIFIQUE ENTREE (Ascenseur) --- */
        else if (strncmp(topic, "parking/ascenseur/cmd", 21) == 0) {
            #ifdef BOARD_ROLE_ENTRY
                if (strcmp(payload, "RDC") == 0) ascenseur_request_floor(0);
                else if (strcmp(payload, "ETAGE1") == 0) ascenseur_request_floor(1);
                else if (strcmp(payload, "ETAGE2") == 0) ascenseur_request_floor(2);
            #endif
        }
        else if (strncmp(topic, "parking/ascenseur/get", 21) == 0) {
            #ifdef BOARD_ROLE_ENTRY
                LOG_INF("❓ Demande état ascenseur reçue, réponse immédiate...");
                mqtt_publish_state(ascenseur_get_current_floor());
            #endif
        }
        
        /* --- GESTION DES CONFIGS (Pour tous) --- */
        else if (strncmp(topic, "parking/config/exit_pin", 23) == 0) {
            LOG_INF("🔑 Nouveau PIN SORTIE : %s", payload);
            save_exit_pin_to_sd(payload);
        }
        else if (strncmp(topic, "parking/config/pin", 18) == 0) {
            LOG_INF("🔑 Nouveau PIN ENTRÉE : %s", payload);
            save_pin_to_sd(payload);
        }
        
        /* --- GESTION PAIEMENT (Pour SORTIE uniquement) --- */
        else if (strncmp(topic, "parking/payment/req", 19) == 0) {
            #ifdef BOARD_ROLE_EXIT
                cJSON *root = cJSON_Parse(payload);
                if (root) {
                    struct payment_info info; 
                    memset(&info, 0, sizeof(info));
                    
                    const char *pl = cJSON_GetStringValue(cJSON_GetObjectItem(root, "plate"));
                    const char *pr = cJSON_GetStringValue(cJSON_GetObjectItem(root, "price"));
                    const char *ca = cJSON_GetStringValue(cJSON_GetObjectItem(root, "cause")); 

                    if (pl) strncpy(info.plate, pl, sizeof(info.plate)-1);
                    if (pr) strncpy(info.price, pr, sizeof(info.price)-1);
                    if (ca) strncpy(info.cause, ca, sizeof(info.cause)-1);
                    else info.cause[0] = '\0'; 

                    k_msgq_put(&payment_msgq, &info, K_NO_WAIT);
                    cJSON_Delete(root);
                }
            /* Pour BOARD_ROLE_ENTRY : Si le prix est "STOP" (Complet), on traite aussi */
            #else
                /* Si c'est un message STOP (Complet), on l'envoie aussi à l'entrée */
                if (strstr(payload, "STOP") != NULL) {
                     cJSON *root = cJSON_Parse(payload);
                     if (root) {
                        struct payment_info info; 
                        memset(&info, 0, sizeof(info));
                        const char *pl = cJSON_GetStringValue(cJSON_GetObjectItem(root, "plate"));
                        strncpy(info.price, "STOP", sizeof(info.price)-1); // On force le STOP
                        if (pl) strncpy(info.plate, pl, sizeof(info.plate)-1);
                        k_msgq_put(&payment_msgq, &info, K_NO_WAIT);
                        cJSON_Delete(root);
                     }
                }
            #endif
        }
        else if (strncmp(topic, "parking/payment/success", 23) == 0) {
            LOG_INF("✅ MQTT : Paiement validé par serveur");
            k_sem_give(&payment_success_sem);
        }
        
        /* --- AFFICHAGE TEXTE (LCD Entrée + UI les deux) --- */
        else if (strncmp(topic, "parking/display/text", 20) == 0) {
            LOG_INF("📟 Mise à jour LCD Places reçue : %s", payload);
            #ifdef BOARD_ROLE_ENTRY
                lcd_update_places(payload); // Seule l'entrée a un écran LCD physique I2C
            #endif
            update_parking_status(payload); // Met à jour l'UI (Label LVGL) pour tout le monde
        }
        
        /* --- GESTION LISTE UTILISATEURS (SD) --- */
        else if (strncmp(topic, "parking/acl/", 12) == 0) {
            cJSON *root = cJSON_Parse(payload);
            if (!root) break;

            const char *op = cJSON_GetStringValue(cJSON_GetObjectItem(root, "op"));
            const char *uid = cJSON_GetStringValue(cJSON_GetObjectItem(root, "uid"));
            int status = -1;

            if (op && strcmp(op, "LIST_REQ") == 0) {
                publish_acl_list();
                cJSON_Delete(root);
                return;
            }

            if (op && strcmp(op, "FULL") == 0) {
                status = write_full_acl_to_sd(cJSON_GetObjectItem(root, "entries"));
            } else if (op && strcmp(op, "ADD") == 0 && uid) {
                status = append_acl_to_sd(uid);
            } else if (op && strcmp(op, "DEL") == 0 && uid) {
                status = delete_acl_from_sd(uid);
            }

            if (status == 0) {
                publish_acl_list();
            }

            /* Accusé de réception (seulement l'entrée répond pour éviter le spam ?) */
            /* Ou les deux répondent, mais avec un ID différent ? */
            /* Pour simplifier, on laisse les deux répondre, le serveur gérera */
            cJSON *ack = cJSON_CreateObject();
            cJSON_AddStringToObject(ack, "op", "SD_WRITE");
            cJSON_AddStringToObject(ack, "status", (status == 0) ? "ok" : "error");
            cJSON_AddStringToObject(ack, "secret", MQTT_SECRET);
            char *ack_str = cJSON_PrintUnformatted(ack);

            struct mqtt_publish_param pub = {0};
            pub.message.topic.topic.utf8 = (uint8_t *)"parking/acl/event";
            pub.message.topic.topic.size = strlen("parking/acl/event");
            pub.message.topic.qos = MQTT_QOS_0_AT_MOST_ONCE;
            pub.message.payload.data = ack_str;
            pub.message.payload.len = strlen(ack_str);
            pub.message_id = sys_rand16_get();
            mqtt_publish(&client_ctx, &pub);

            cJSON_free(ack_str);
            cJSON_Delete(ack);
            cJSON_Delete(root);
        }

        break;
    }

    case MQTT_EVT_DISCONNECT:
        LOG_WRN("⚠️ Déconnecté du broker (%d)", evt->result);
        connected = false;
        clear_fds();
        break;

    default:
        break;
    }
}

void publish_acl_list(void)
{
    struct fs_file_t f;
    fs_file_t_init(&f);

    k_mutex_lock(&sd_lock, K_FOREVER); 
    int rc = fs_open(&f, "/SD:/users.txt", FS_O_READ);
    if (rc < 0) {
        k_mutex_unlock(&sd_lock); 
        LOG_WRN("Impossible d'ouvrir users.txt (%d)", rc);
        return;
    }

    char line[128];
    int pos = 0;
    char c;

    cJSON *root = cJSON_CreateObject();
    cJSON_AddStringToObject(root, "op", "LIST");
    cJSON_AddStringToObject(root, "secret", MQTT_SECRET);
    cJSON *entries = cJSON_CreateArray();

    while (fs_read(&f, &c, 1) == 1) {
        if (c == '\n' || pos >= (int)sizeof(line) - 1) {
            line[pos] = '\0';
            pos = 0;

            if (strncmp(line, "badge:", 6) == 0) {
                const char *uid = line + 6;
                cJSON_AddItemToArray(entries, cJSON_CreateString(uid));
            }
        } else {
            line[pos++] = c;
        }
    }

    fs_close(&f);
    k_mutex_unlock(&sd_lock); 

    cJSON_AddItemToObject(root, "entries", entries);
    char *json_str = cJSON_PrintUnformatted(root);
    
    struct mqtt_publish_param pub = {0};
    pub.message.topic.topic.utf8 = (uint8_t *)"parking/acl/list";
    pub.message.topic.topic.size = strlen("parking/acl/list");
    pub.message.topic.qos = MQTT_QOS_0_AT_MOST_ONCE;
    pub.message.payload.data = json_str;
    pub.message.payload.len = strlen(json_str);
    pub.message_id = sys_rand16_get();

    pub.retain_flag = 1U;

    int pub_rc = mqtt_publish(&client_ctx, &pub);
    if (pub_rc == 0)
        LOG_INF("📤 Liste ACL publiée (%d badges)", cJSON_GetArraySize(entries));
    else
        LOG_ERR("Erreur mqtt_publish LIST (%d)", pub_rc);

    k_msleep(300);

    cJSON_free(json_str);
    cJSON_Delete(root);
}


/* ============================================================
 * Setup / boucle principale
 * ============================================================ */
static void broker_init(void)
{
    struct sockaddr_in *broker4 = (struct sockaddr_in *)&broker;
    broker4->sin_family = AF_INET;
    broker4->sin_port = htons(SERVER_PORT);
    inet_pton(AF_INET, SERVER_ADDR, &broker4->sin_addr);
}

static void client_init(struct mqtt_client *client)
{
    mqtt_client_init(client);
    broker_init();

    client->broker = &broker;
    client->evt_cb = mqtt_evt_handler;
    client->client_id.utf8 = (uint8_t *)MQTT_CLIENTID;
    client->client_id.size = strlen(MQTT_CLIENTID);

    client->rx_buf = rx_buffer;
    client->rx_buf_size = sizeof(rx_buffer);
    client->tx_buf = tx_buffer;
    client->tx_buf_size = sizeof(tx_buffer);

    client->transport.type = MQTT_TRANSPORT_NON_SECURE;
    client->protocol_version = MQTT_VERSION_3_1_1;
    client->clean_session = 1U;
    client->keepalive = 25U;
}

static int try_to_connect(struct mqtt_client *client)
{
    int rc;
    for (int i = 0; i < 5 && !connected; i++) {
        client_init(client);
        rc = mqtt_connect(client);
        if (rc != 0) {
            LOG_WRN("MQTT connect err %d (tentative %d)", rc, i);
            k_sleep(K_SECONDS(1));
            continue;
        }
        prepare_fds(client);
        if (wait_evt(2000))
            mqtt_input(client);
        if (!connected)
            mqtt_abort(client);
    }
    return connected ? 0 : -EIO;
}

static void mqtt_loop(void)
{
    #ifdef BOARD_ROLE_ENTRY
    int last_floor = -1;
    int64_t next_state_pub = 0;
    #endif

    while (1) {
        LOG_INF("🔁 Tentative de connexion MQTT...");
        int rc = try_to_connect(&client_ctx);
        if (rc != 0) {
            LOG_ERR("Connexion MQTT échouée (%d)", rc);
            k_sleep(K_SECONDS(3));
            continue;
        }

        LOG_INF("✅ Connecté, écoute en cours...");
        int64_t next_ping = k_uptime_get() + 12000;
        while (connected) {
            rc = mqtt_input(&client_ctx);
            if (rc < 0 && rc != -EAGAIN)
                break;

            int64_t now = k_uptime_get();
            if (now >= next_ping) {
                rc = mqtt_live(&client_ctx);
                next_ping = now + (client_ctx.keepalive * 1000 / 2);
            }
            
            // --- Publication périodique de l’état ascenseur ---
            // Uniquement si on est sur la borne d'Entrée
            #ifdef BOARD_ROLE_ENTRY
            if (now >= next_state_pub) {
                int floor = ascenseur_get_current_floor();
                if (floor != last_floor) {
                    mqtt_publish_state(floor);
                    last_floor = floor;
                }
                next_state_pub = now + 5000; // toutes les 5 s
            }
            #endif

            k_sleep(K_MSEC(200));
        }

        mqtt_disconnect(&client_ctx, NULL);
        connected = false;
        LOG_WRN("🔌 Déconnecté, reconnexion dans 3 s...");
        k_sleep(K_SECONDS(3));
    }
}

/* ============================================================
 * Thread principal MQTT
 * ============================================================ */
void mqtt_thread(void *p1, void *p2, void *p3)
{
    LOG_INF("Démarrage MQTT Thread (SD supposée déjà montée par main)");
    wait_for_network();
    mqtt_loop();
}