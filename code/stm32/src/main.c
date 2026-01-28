/*
 * STM32F746G-DISCO — Main Controller
 * Gestion double rôle : BORNE D'ENTRÉE / BORNE DE SORTIE
 */

#include <zephyr/sys/reboot.h>
#include <zephyr/logging/log.h>
LOG_MODULE_REGISTER(main, LOG_LEVEL_INF);

#include <zephyr/device.h>
#include <zephyr/devicetree.h>
#include <zephyr/drivers/display.h>
#include <zephyr/kernel.h>
#include <lvgl.h>
#include <zephyr/fs/fs.h>
#include <zephyr/storage/disk_access.h>
#include <ff.h>
#include <strings.h>
#include <string.h>
#include <stdio.h>
#include <ctype.h>
#include <errno.h>

/* Configuration des rôles */
#include "role_config.h"

/* Déclaration compatible LVGL v9 */
LV_IMAGE_DECLARE(QR_code);

/* -------------------- Config / Constantes -------------------- */
#define UID_STR_LEN         16
#define UID_HANDLER_STACK   4096
#define UID_HANDLER_PRIO    3
#define DEFAULT_PIN         "1234"
#define DEFAULT_EXIT_PIN    "0000"
#define SCREENSAVER_TIMEOUT 3000  /* 3000 * 10ms = 30 secondes */

/* -------------------- Globals -------------------- */
K_MUTEX_DEFINE(sd_lock);

K_SEM_DEFINE(payment_success_sem, 0, 1);

static char current_pin_code[10] = DEFAULT_PIN;
static char current_exit_pin_code[10] = DEFAULT_EXIT_PIN;
static int inactivity_counter = 0;
static bool is_dimmed = false;

/* UI Objects */
static lv_obj_t *home_scr, *pin_ta, *pin_kb, *label_status, *banner_cont = NULL, *banner_label = NULL;
static lv_obj_t *settings_scr, *new_pin_ta, *new_pin_kb = NULL, *label_admin_status;
static lv_obj_t *qr_popup = NULL; 
static lv_obj_t *dimmer_layer = NULL; /* Le voile noir */
static lv_timer_t *qr_autoclose_timer = NULL; 

/* Variable globale pour le sélecteur Admin */
static lv_obj_t *pin_type_roller = NULL;

/* Variables d'État */
static bool parking_is_full = false; /* false = places libres */
static bool admin_active = false;
static int64_t admin_expire_time = 0;
static bool admin_request_pending = false;
static bool add_badge_mode = false;
static lv_timer_t *admin_wait_timer = NULL;

/* Queue de message pour le paiement / infos serveur */
struct payment_info {
    char plate[16];
    char price[10];
    char cause[64];
};
K_MSGQ_DEFINE(payment_msgq, sizeof(struct payment_info), 4, 4);

/* Externs */
extern void mqtt_thread(void *, void *, void *);
extern void mqtt_send_uid(const char *uid);

/* Ces threads ne sont lancés qu'en mode ENTREE */
#ifdef BOARD_ROLE_ENTRY
    extern void ascenseur_thread(void *, void *, void *);
    K_THREAD_DEFINE(ascenseur_tid, 4096, ascenseur_thread, NULL, NULL, NULL, 8, 0, 0);
#endif

extern void publish_acl_list(void);

#define MQTT_THREAD_STACK_SIZE 4096
#define MQTT_THREAD_PRIORITY   1
K_THREAD_STACK_DEFINE(mqtt_stack_area, MQTT_THREAD_STACK_SIZE);
static struct k_thread mqtt_thread_data;

K_MSGQ_DEFINE(uid_msgq, UID_STR_LEN, 4, 4);

static const char * btnm_map[] = { "1", "2", "3", "\n", "4", "5", "6", "\n", "7", "8", "9", "\n", LV_SYMBOL_BACKSPACE, "0", LV_SYMBOL_OK, "" };
static const lv_btnmatrix_ctrl_t btnm_ctrl[] = { 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1 };

/* SD Card Utils */
static FATFS fat_fs;
static struct fs_mount_t fs_mnt = { .type = FS_FATFS, .mnt_point = "/SD:", .fs_data = &fat_fs };
static int sd_ready = 0;

static void load_pin_from_sd(void) {
    if (!sd_ready) return;
    struct fs_file_t f; 

    k_mutex_lock(&sd_lock, K_FOREVER);

    /* 1. Chargement PIN ENTRÉE */
    fs_file_t_init(&f);
    if (fs_open(&f, "/SD:/pin.txt", FS_O_READ) >= 0) {
        char buf[16]; ssize_t n = fs_read(&f, buf, sizeof(buf) - 1);
        if (n > 0) {
            buf[n] = '\0'; char *p = strpbrk(buf, "\r\n"); if (p) *p = '\0';
            if (strlen(buf) > 0) strncpy(current_pin_code, buf, sizeof(current_pin_code)-1);
        }
        fs_close(&f);
    } else {
        if (fs_open(&f, "/SD:/pin.txt", FS_O_CREATE | FS_O_WRITE) >= 0) {
            fs_write(&f, DEFAULT_PIN, strlen(DEFAULT_PIN)); fs_close(&f);
        }
    }

    /* 2. Chargement PIN SORTIE */
    fs_file_t_init(&f);
    if (fs_open(&f, "/SD:/exit_pin.txt", FS_O_READ) >= 0) {
        char buf[16]; ssize_t n = fs_read(&f, buf, sizeof(buf) - 1);
        if (n > 0) {
            buf[n] = '\0'; char *p = strpbrk(buf, "\r\n"); if (p) *p = '\0';
            if (strlen(buf) > 0) strncpy(current_exit_pin_code, buf, sizeof(current_exit_pin_code)-1);
        }
        fs_close(&f);
    } else {
        if (fs_open(&f, "/SD:/exit_pin.txt", FS_O_CREATE | FS_O_WRITE) >= 0) {
            fs_write(&f, DEFAULT_EXIT_PIN, strlen(DEFAULT_EXIT_PIN)); fs_close(&f);
        }
    }

    k_mutex_unlock(&sd_lock);
    LOG_INF("🔐 PINS Chargés: In='%s', Out='%s'", current_pin_code, current_exit_pin_code);
}

void save_pin_to_sd(const char *new_pin) {
    if (!new_pin || strlen(new_pin) == 0) return;
    k_mutex_lock(&sd_lock, K_FOREVER);
    
    memset(current_pin_code, 0, sizeof(current_pin_code));
    strncpy(current_pin_code, new_pin, sizeof(current_pin_code)-1);
    LOG_INF("🔑 PIN Entrée MAJ en RAM: %s", current_pin_code);

    if (sd_ready) {
        struct fs_file_t f; fs_file_t_init(&f);
        if (fs_open(&f, "/SD:/pin.txt", FS_O_CREATE | FS_O_WRITE | FS_O_TRUNC) >= 0) {
            fs_write(&f, new_pin, strlen(new_pin)); fs_close(&f);
        }
    }
    k_mutex_unlock(&sd_lock);
}

void save_exit_pin_to_sd(const char *new_pin) {
    if (!new_pin || strlen(new_pin) == 0) return;
    k_mutex_lock(&sd_lock, K_FOREVER);
    
    memset(current_exit_pin_code, 0, sizeof(current_exit_pin_code));
    strncpy(current_exit_pin_code, new_pin, sizeof(current_exit_pin_code)-1);
    LOG_INF("🔑 PIN Sortie MAJ en RAM: %s", current_exit_pin_code);

    if (sd_ready) {
        struct fs_file_t f; fs_file_t_init(&f);
        if (fs_open(&f, "/SD:/exit_pin.txt", FS_O_CREATE | FS_O_WRITE | FS_O_TRUNC) >= 0) {
            fs_write(&f, new_pin, strlen(new_pin)); fs_close(&f);
        }
    }
    k_mutex_unlock(&sd_lock);
}

static void uid_normalize8(const char *in, char *out, size_t out_sz) {
    size_t j = 0;
    for (size_t i = 0; in[i] != '\0' && j < 8 && j < out_sz - 1; i++) {
        char c = in[i];
        if ((c >= '0' && c <= '9') || (c >= 'A' && c <= 'F') || (c >= 'a' && c <= 'f')) {
            if (c >= 'a' && c <= 'f') {
                c -= 32; 
            }
            out[j++] = c;
        }
    }
    out[j] = '\0';
}

static int append_user_badge_local(const char *uid_hex) {
    if (!sd_ready) return -1;
    char uid8[9]; uid_normalize8(uid_hex, uid8, sizeof(uid8));
    k_mutex_lock(&sd_lock, K_FOREVER);
    struct fs_file_t f; fs_file_t_init(&f);
    if (fs_open(&f, "/SD:/users.txt", FS_O_CREATE | FS_O_WRITE | FS_O_APPEND) < 0) { k_mutex_unlock(&sd_lock); return -1; }
    char line[64]; snprintf(line, sizeof(line), "badge:%s\n", uid8);
    fs_write(&f, line, strlen(line)); fs_close(&f);
    k_mutex_unlock(&sd_lock);
    return 0;
}

static void init_sd_card(void) {
    int rc = fs_mount(&fs_mnt);
    if (rc != 0 && rc != -EBUSY) { sd_ready = 0; return; }
    struct fs_file_t f; fs_file_t_init(&f);
    rc = fs_open(&f, "/SD:/users.txt", FS_O_READ);
    if (rc < 0 && rc != -ENOENT) { fs_close(&f); sd_ready = 0; return; }
    if (rc >= 0) fs_close(&f);
    sd_ready = 1; load_pin_from_sd();
}

static bool check_uid_in_file(const char *uid_hex) {
    if (!sd_ready) return false;
    struct fs_file_t f; fs_file_t_init(&f);
    k_mutex_lock(&sd_lock, K_FOREVER);
    if (fs_open(&f, "/SD:/users.txt", FS_O_READ) < 0) { k_mutex_unlock(&sd_lock); return false; }
    char line[128]; int pos = 0; char c; bool ok = false;
    char uid8[9], target8[9]; uid_normalize8(uid_hex, target8, sizeof(target8));
    while (fs_read(&f, &c, 1) == 1) {
        if (c == '\n' || pos >= (int)sizeof(line) - 1) {
            line[pos] = '\0'; pos = 0;
            if (strncasecmp(line, "badge:", 6) == 0) {
                uid_normalize8(line + 6, uid8, sizeof(uid8));
                if (strcmp(uid8, target8) == 0) { ok = true; break; }
            }
        } else line[pos++] = c;
    }
    fs_close(&f); k_mutex_unlock(&sd_lock); return ok;
}

static bool is_admin(const char *uid_hex) {
    char uid8[9]; uid_normalize8(uid_hex, uid8, sizeof(uid8));
    return (strcmp(uid8, "BBC7CD05") == 0);
}

/* Fonction appelée par MQTT Thread pour mettre à jour l'état COMPLET/LIBRE */
void update_parking_status(const char *text) {
    if (strstr(text, "COMPLET") != NULL) {
        parking_is_full = true;
    } else {
        parking_is_full = false;
    }
    
    if (label_status) {
        if (parking_is_full) {
            lv_label_set_text(label_status, "PARKING COMPLET");
            lv_obj_set_style_text_color(label_status, lv_color_hex(0xFF0000), 0);
        } else {
            #ifdef BOARD_ROLE_ENTRY
                lv_label_set_text(label_status, "Veuillez badger");
            #else
                lv_label_set_text(label_status, "Bonne route !");
            #endif
            lv_obj_set_style_text_color(label_status, lv_color_white(), 0);
        }
    }
}

/* UI Callbacks */
static void reset_home_timer_cb(lv_timer_t *t) {
    if (lv_scr_act() == home_scr) { 
        if (parking_is_full) {
            lv_label_set_text(label_status, "PARKING COMPLET");
            lv_obj_set_style_text_color(label_status, lv_color_hex(0xFF0000), 0); // ROUGE
        } else {
            #ifdef BOARD_ROLE_ENTRY
                lv_label_set_text(label_status, "Veuillez badger ou saisir le code");
            #else
                lv_label_set_text(label_status, "Saisissez votre code de sortie");
            #endif
            lv_obj_set_style_text_color(label_status, lv_color_white(), 0); // BLANC
        }
        
        lv_textarea_set_text(pin_ta, ""); 
    }
    lv_timer_del(t);
}

static void hide_banner_cb(lv_timer_t *t) { if (banner_cont) lv_obj_add_flag(banner_cont, LV_OBJ_FLAG_HIDDEN); lv_timer_del(t); }

static void show_banner(const char* text, uint32_t color) {
    inactivity_counter = 0;
    if (is_dimmed && dimmer_layer) {
        lv_obj_add_flag(dimmer_layer, LV_OBJ_FLAG_HIDDEN);
        is_dimmed = false;
    }

    if (!banner_cont) return;
    
    lv_label_set_text(banner_label, text); 
    lv_obj_set_style_bg_color(banner_cont, lv_color_hex(color), 0);
    
    lv_obj_clear_flag(banner_cont, LV_OBJ_FLAG_HIDDEN); 
    lv_obj_move_foreground(banner_cont);
    
    lv_timer_t *t = lv_timer_create(hide_banner_cb, 2000, NULL); 
    lv_timer_set_repeat_count(t, 1);
}

static void show_success_banner(void) { show_banner("OUVERTURE\nAUTORISEE", 0x28a745); }
static void show_denied_banner(void)  { show_banner("ACCES REFUSE", 0xdc3545); }

static void return_to_home(void) {
    admin_active = false; admin_request_pending = false; add_badge_mode = false;
    if (admin_wait_timer) { lv_timer_del(admin_wait_timer); admin_wait_timer = NULL; }
    if (lv_scr_act() != home_scr) lv_scr_load_anim(home_scr, LV_SCR_LOAD_ANIM_MOVE_RIGHT, 200, 0, false);
    lv_textarea_set_text(pin_ta, ""); 
    
    // Remise à zéro du label selon l'état
    lv_timer_t *t = lv_timer_create(reset_home_timer_cb, 100, NULL); 
    lv_timer_set_repeat_count(t, 1);
}

/* Gestion du clavier avec Distinction des Rôles */
static void pin_kb_event_cb(lv_event_t *e) {
    if (lv_event_get_code(e) == LV_EVENT_READY) { 
        const char *txt = lv_textarea_get_text(pin_ta);

        /* ============================
         * LOGIQUE POUR BORNE D'ENTRÉE
         * ============================ */
        #ifdef BOARD_ROLE_ENTRY
            if (strcmp(txt, current_pin_code) == 0) {
                /* 🛑 PROTECTION : On vérifie si c'est COMPLET */
                if (parking_is_full) {
                    show_denied_banner();
                    lv_label_set_text(label_status, "PARKING COMPLET !");
                    lv_obj_set_style_text_color(label_status, lv_color_hex(0xFF0000), 0);
                } else {
                    show_success_banner(); 
                    mqtt_send_uid("PIN_IN"); 
                    lv_label_set_text(label_status, "Code Entree OK");
                }
            } else {
                show_denied_banner(); 
                lv_label_set_text(label_status, "Code incorrect !");
            }
        
        /* ============================
         * LOGIQUE POUR BORNE DE SORTIE
         * ============================ */
        #else 
            if (strcmp(txt, current_exit_pin_code) == 0) {
                /* Sortie toujours autorisée même si complet */
                show_success_banner(); 
                mqtt_send_uid("PIN_OUT"); 
                lv_label_set_text(label_status, "Code Sortie OK");
            }
            else {
                show_denied_banner(); 
                lv_label_set_text(label_status, "Code incorrect !");
            }
        #endif

        lv_timer_t *t = lv_timer_create(reset_home_timer_cb, 3000, NULL); lv_timer_set_repeat_count(t, 1);
        lv_textarea_set_text(pin_ta, "");
    }
}

static void kb_visibility_cb(lv_event_t *e) {
    if (!new_pin_kb) return;
    lv_event_code_t code = lv_event_get_code(e);
    if (code == LV_EVENT_CLICKED || code == LV_EVENT_FOCUSED) { 
        lv_keyboard_set_textarea(new_pin_kb, new_pin_ta); lv_obj_clear_flag(new_pin_kb, LV_OBJ_FLAG_HIDDEN); 
    }
    else if (code == LV_EVENT_READY || code == LV_EVENT_DEFOCUSED) { lv_obj_add_flag(new_pin_kb, LV_OBJ_FLAG_HIDDEN); }
}

static void settings_btn_cb(lv_event_t *e) {
    if (admin_active && k_uptime_get() < admin_expire_time) { lv_scr_load_anim(settings_scr, LV_SCR_LOAD_ANIM_MOVE_LEFT, 200, 0, false); return; }
    admin_request_pending = true; lv_label_set_text(label_status, "BADGEZ ADMIN SVP...");
    if (admin_wait_timer) lv_timer_del(admin_wait_timer);
    admin_wait_timer = lv_timer_create((lv_timer_cb_t)return_to_home, 5000, NULL); lv_timer_set_repeat_count(admin_wait_timer, 1);
}

/* Callback de sauvegarde AVEC choix Entrée/Sortie */
static void save_new_pin_cb(lv_event_t *e) {
    const char *txt = lv_textarea_get_text(new_pin_ta);
    if (strlen(txt) >= 4) {
        /* On regarde la roulette */
        uint16_t selected = lv_roller_get_selected(pin_type_roller);
        
        if (selected == 0) {
            save_pin_to_sd(txt);
            lv_label_set_text(label_admin_status, "Code ENTREE MAJ !");
        } else {
            save_exit_pin_to_sd(txt);
            lv_label_set_text(label_admin_status, "Code SORTIE MAJ !");
        }
        
        lv_textarea_set_text(new_pin_ta, ""); 
        if(new_pin_kb) lv_obj_add_flag(new_pin_kb, LV_OBJ_FLAG_HIDDEN); 
    }
}

static void add_badge_wait_cb(lv_event_t *e) {
    add_badge_mode = true; lv_label_set_text(label_admin_status, "BADGEZ LE NOUVEAU...");
    admin_expire_time = k_uptime_get() + 20000; 
}

/* --- LOGIQUE QR CODE --- */
static void close_qr_cb(lv_event_t *e) {
    if (qr_popup) lv_obj_add_flag(qr_popup, LV_OBJ_FLAG_HIDDEN);
    if (qr_autoclose_timer) {
        lv_timer_del(qr_autoclose_timer);
        qr_autoclose_timer = NULL;
    }
}

static lv_obj_t *lbl_qr_plate = NULL;
static lv_obj_t *lbl_qr_price = NULL;
static lv_obj_t *lbl_qr_warning = NULL;
static lv_obj_t *lbl_qr_title = NULL; 
static lv_obj_t *img_qr_obj = NULL; 

static void qr_autoclose_cb(lv_timer_t *t) {
    if (qr_popup) lv_obj_add_flag(qr_popup, LV_OBJ_FLAG_HIDDEN);
    qr_autoclose_timer = NULL; 
}

static void open_qr_popup(const char *plate, const char *price, const char *cause) {
    inactivity_counter = 0;
    if (is_dimmed && dimmer_layer) { lv_obj_add_flag(dimmer_layer, LV_OBJ_FLAG_HIDDEN); is_dimmed = false; }

    if (!qr_popup) {
        qr_popup = lv_obj_create(home_scr);
        lv_obj_set_size(qr_popup, 320, 240); 
        lv_obj_center(qr_popup);
        lv_obj_set_style_bg_color(qr_popup, lv_color_white(), 0);
        lv_obj_set_style_border_width(qr_popup, 3, 0);
        
        lbl_qr_title = lv_label_create(qr_popup);
        lv_obj_align(lbl_qr_title, LV_ALIGN_TOP_MID, 0, -5); 
        
        img_qr_obj = lv_image_create(qr_popup);
        lv_image_set_src(img_qr_obj, &QR_code);
        lv_obj_align(img_qr_obj, LV_ALIGN_LEFT_MID, 5, 10); 

        lbl_qr_plate = lv_label_create(qr_popup);
        lv_obj_align(lbl_qr_plate, LV_ALIGN_TOP_RIGHT, -10, 40);
        lv_obj_set_style_text_align(lbl_qr_plate, LV_TEXT_ALIGN_RIGHT, 0);
        
        lbl_qr_price = lv_label_create(qr_popup);
        lv_obj_align(lbl_qr_price, LV_ALIGN_TOP_RIGHT, -10, 75); 
        lv_obj_set_style_text_align(lbl_qr_price, LV_TEXT_ALIGN_RIGHT, 0);
        lv_obj_set_style_text_color(lbl_qr_price, lv_color_hex(0xe74c3c), 0); 

        lbl_qr_warning = lv_label_create(qr_popup);
        lv_obj_set_width(lbl_qr_warning, 140); 
        lv_label_set_long_mode(lbl_qr_warning, LV_LABEL_LONG_WRAP); 
        lv_obj_set_style_text_align(lbl_qr_warning, LV_TEXT_ALIGN_RIGHT, 0); 
        lv_obj_align(lbl_qr_warning, LV_ALIGN_TOP_RIGHT, -10, 100); 
        lv_obj_set_style_text_color(lbl_qr_warning, lv_color_hex(0xFF0000), 0); 

        lv_obj_t *btn_close = lv_btn_create(qr_popup);
        lv_obj_set_size(btn_close, 80, 30);
        lv_obj_align(btn_close, LV_ALIGN_BOTTOM_RIGHT, -5, -5);
        lv_obj_set_style_bg_color(btn_close, lv_color_hex(0x555555), 0);
        lv_obj_add_event_cb(btn_close, close_qr_cb, LV_EVENT_CLICKED, NULL);
        lv_obj_t *lbl_cl = lv_label_create(btn_close);
        lv_label_set_text(lbl_cl, "Fermer"); lv_obj_center(lbl_cl);
    }
    
    if(img_qr_obj) lv_obj_clear_flag(img_qr_obj, LV_OBJ_FLAG_HIDDEN);
    lv_obj_clear_flag(lbl_qr_plate, LV_OBJ_FLAG_HIDDEN);
    lv_obj_clear_flag(lbl_qr_price, LV_OBJ_FLAG_HIDDEN);

    /* CAS 1 : MODE MANUEL */
    if (plate == NULL && price == NULL) {
        lv_label_set_text(lbl_qr_title, "Scannez pour payer");
        lv_obj_set_style_text_color(lbl_qr_title, lv_color_black(), 0);
        lv_obj_set_style_border_color(qr_popup, lv_color_hex(0xf1c40f), 0);
        lv_obj_align(img_qr_obj, LV_ALIGN_CENTER, 0, -10);
        lv_obj_add_flag(lbl_qr_plate, LV_OBJ_FLAG_HIDDEN);
        lv_obj_add_flag(lbl_qr_price, LV_OBJ_FLAG_HIDDEN);
        lv_obj_add_flag(lbl_qr_warning, LV_OBJ_FLAG_HIDDEN);
    }
    /* CAS 2 : PAIEMENT REQUIS */
    else {
        lv_label_set_text(lbl_qr_title, "Paiement Requis");
        lv_obj_set_style_text_color(lbl_qr_title, lv_color_black(), 0);
        lv_obj_set_style_border_color(qr_popup, lv_color_hex(0xf1c40f), 0);
        lv_obj_align(img_qr_obj, LV_ALIGN_LEFT_MID, 5, 10);

        if (plate) lv_label_set_text_fmt(lbl_qr_plate, "Vehicule :\n%s", plate);
        if (price) lv_label_set_text_fmt(lbl_qr_price, "%s E", price);
    }

    if (cause && strlen(cause) > 0) {
        lv_label_set_text(lbl_qr_warning, cause);
        lv_obj_clear_flag(lbl_qr_warning, LV_OBJ_FLAG_HIDDEN);
    } else {
        lv_obj_add_flag(lbl_qr_warning, LV_OBJ_FLAG_HIDDEN);
    }

    if (qr_autoclose_timer) {
        lv_timer_del(qr_autoclose_timer);
        qr_autoclose_timer = NULL;
    }

    if (price == NULL || strcmp(price, "STOP") != 0) {
        qr_autoclose_timer = lv_timer_create(qr_autoclose_cb, 15000, NULL); 
        lv_timer_set_repeat_count(qr_autoclose_timer, 1); 
    }

    lv_obj_clear_flag(qr_popup, LV_OBJ_FLAG_HIDDEN); 
    lv_obj_move_foreground(qr_popup);
}

static void show_qr_cb(lv_event_t *e) { open_qr_popup(NULL, NULL, NULL); }

/* --- LOGIQUE SCREENSAVER --- */
static void dimming_wake_cb(lv_event_t *e) {
    inactivity_counter = 0;
    if (is_dimmed && dimmer_layer) {
        lv_obj_add_flag(dimmer_layer, LV_OBJ_FLAG_HIDDEN);
        is_dimmed = false;
    }
}

static void create_dimmer_layer(void) {
    dimmer_layer = lv_obj_create(lv_layer_top());
    lv_obj_set_size(dimmer_layer, 480, 272);
    lv_obj_set_style_bg_color(dimmer_layer, lv_color_black(), 0);
    lv_obj_set_style_bg_opa(dimmer_layer, LV_OPA_90, 0); 
    lv_obj_set_style_border_width(dimmer_layer, 0, 0);
    lv_obj_add_flag(dimmer_layer, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_add_event_cb(dimmer_layer, dimming_wake_cb, LV_EVENT_CLICKED, NULL);
    lv_obj_add_flag(dimmer_layer, LV_OBJ_FLAG_HIDDEN);
}

static void build_home_screen(void) {
    home_scr = lv_obj_create(NULL); lv_obj_set_style_bg_color(home_scr, lv_color_hex(0x101820), 0);
    
    lv_obj_t *btn = lv_btn_create(home_scr); lv_obj_align(btn, LV_ALIGN_TOP_RIGHT, -5, 5); lv_obj_add_event_cb(btn, settings_btn_cb, LV_EVENT_CLICKED, NULL);
    lv_obj_t *lbl = lv_label_create(btn); lv_label_set_text(lbl, LV_SYMBOL_SETTINGS); lv_obj_center(lbl);
    
    lv_obj_t *btn_qr = lv_btn_create(home_scr); 
    lv_obj_set_size(btn_qr, 40, 40); lv_obj_align(btn_qr, LV_ALIGN_TOP_LEFT, 5, 5); 
    lv_obj_set_style_bg_color(btn_qr, lv_color_hex(0xf1c40f), 0);
    lv_obj_add_event_cb(btn_qr, show_qr_cb, LV_EVENT_CLICKED, NULL);
    lv_obj_t *lbl_qr = lv_label_create(btn_qr); lv_label_set_text(lbl_qr, "$"); lv_obj_center(lbl_qr);

    lv_obj_t *title = lv_label_create(home_scr);
    
    #ifdef BOARD_ROLE_ENTRY
        lv_label_set_text(title, "BORNE ENTREE"); 
        lv_obj_set_style_text_color(title, lv_color_hex(0xFFD700), 0);
    #else
        lv_label_set_text(title, "BORNE SORTIE"); 
        lv_obj_set_style_text_color(title, lv_color_hex(0xe74c3c), 0);
    #endif
    
    lv_obj_align(title, LV_ALIGN_TOP_MID, 0, 10);
    label_status = lv_label_create(home_scr); lv_label_set_text(label_status, "Veuillez badger"); lv_obj_align(label_status, LV_ALIGN_TOP_MID, 0, 45);
    lv_obj_set_style_text_color(label_status, lv_color_white(), 0);
    
    pin_ta = lv_textarea_create(home_scr); lv_textarea_set_password_mode(pin_ta, true); lv_textarea_set_one_line(pin_ta, true);
    lv_obj_align(pin_ta, LV_ALIGN_TOP_MID, 0, 65); lv_obj_set_width(pin_ta, 160);
    
    pin_kb = lv_keyboard_create(home_scr); lv_keyboard_set_map(pin_kb, LV_KEYBOARD_MODE_USER_1, btnm_map, btnm_ctrl);
    lv_keyboard_set_mode(pin_kb, LV_KEYBOARD_MODE_USER_1); lv_keyboard_set_textarea(pin_kb, pin_ta);
    lv_obj_align(pin_kb, LV_ALIGN_BOTTOM_MID, 0, -5); lv_obj_set_size(pin_kb, 320, 155); lv_obj_add_event_cb(pin_kb, pin_kb_event_cb, LV_EVENT_READY, NULL);
    
    banner_cont = lv_obj_create(home_scr); lv_obj_set_size(banner_cont, 350, 100); lv_obj_center(banner_cont); lv_obj_add_flag(banner_cont, LV_OBJ_FLAG_HIDDEN);
    banner_label = lv_label_create(banner_cont); lv_obj_center(banner_label);
}

static void build_settings_screen(void) {
    settings_scr = lv_obj_create(NULL); lv_obj_set_style_bg_color(settings_scr, lv_color_hex(0x1E1E1E), 0);
    
    lv_obj_t *header_panel = lv_obj_create(settings_scr);
    lv_obj_set_size(header_panel, 480, 50); lv_obj_align(header_panel, LV_ALIGN_TOP_MID, 0, 0);
    lv_obj_set_style_bg_color(header_panel, lv_color_hex(0x000000), 0); lv_obj_set_style_bg_opa(header_panel, LV_OPA_50, 0);

    lv_obj_t *title = lv_label_create(header_panel);
    lv_label_set_text(title, LV_SYMBOL_SETTINGS "  ADMINISTRATION"); lv_obj_set_style_text_color(title, lv_color_hex(0xFFFFFF), 0);
    lv_obj_align(title, LV_ALIGN_LEFT_MID, 10, 0);

    label_admin_status = lv_label_create(header_panel);
    lv_label_set_text(label_admin_status, "Pret"); lv_obj_set_style_text_color(label_admin_status, lv_color_hex(0x2ecc71), 0);
    lv_obj_align(label_admin_status, LV_ALIGN_RIGHT_MID, -10, 0);

    pin_type_roller = lv_roller_create(settings_scr);
    lv_roller_set_options(pin_type_roller, "Code ENTREE\nCode SORTIE", LV_ROLLER_MODE_NORMAL);
    lv_obj_set_width(pin_type_roller, 200);
    lv_obj_set_height(pin_type_roller, 80);
    lv_obj_align(pin_type_roller, LV_ALIGN_TOP_MID, 0, 60);

    lv_obj_t *pin_cont = lv_obj_create(settings_scr);
    lv_obj_set_size(pin_cont, 420, 65); 
    lv_obj_align(pin_cont, LV_ALIGN_TOP_MID, 0, 150); 
    lv_obj_set_style_bg_color(pin_cont, lv_color_hex(0x333333), 0);
    lv_obj_set_style_border_width(pin_cont, 0, 0); 

    lv_obj_t *lbl_pin = lv_label_create(pin_cont);
    lv_label_set_text(lbl_pin, "Nouveau Code :"); lv_obj_set_style_text_color(lbl_pin, lv_color_white(), 0);
    lv_obj_align(lbl_pin, LV_ALIGN_LEFT_MID, 10, 0);

    new_pin_ta = lv_textarea_create(pin_cont);
    lv_textarea_set_one_line(new_pin_ta, true); lv_textarea_set_password_mode(new_pin_ta, false);
    lv_textarea_set_max_length(new_pin_ta, 8); lv_obj_set_width(new_pin_ta, 140); 
    lv_obj_align(new_pin_ta, LV_ALIGN_CENTER, 40, 0); 
    lv_obj_add_event_cb(new_pin_ta, kb_visibility_cb, LV_EVENT_ALL, NULL);

    lv_obj_t *btn_save = lv_btn_create(pin_cont);
    lv_obj_set_size(btn_save, 50, 45); lv_obj_align(btn_save, LV_ALIGN_RIGHT_MID, -5, 0);
    lv_obj_set_style_bg_color(btn_save, lv_color_hex(0x2ecc71), 0);
    lv_obj_add_event_cb(btn_save, save_new_pin_cb, LV_EVENT_CLICKED, NULL);
    lv_obj_t *lbl_save = lv_label_create(btn_save); lv_label_set_text(lbl_save, LV_SYMBOL_SAVE); lv_obj_center(lbl_save);

    lv_obj_t *btn_badge = lv_btn_create(settings_scr);
    lv_obj_set_size(btn_badge, 220, 50);
    lv_obj_align(btn_badge, LV_ALIGN_TOP_MID, 40, 230); 
    lv_obj_set_style_bg_color(btn_badge, lv_color_hex(0x3498db), 0);
    lv_obj_add_event_cb(btn_badge, add_badge_wait_cb, LV_EVENT_CLICKED, NULL);
    lv_obj_t *l_badge = lv_label_create(btn_badge); lv_label_set_text(l_badge, LV_SYMBOL_PLUS "  AJOUTER UN BADGE"); lv_obj_center(l_badge);

    lv_obj_t *btn_back = lv_btn_create(settings_scr);
    lv_obj_set_size(btn_back, 60, 50);
    lv_obj_align(btn_back, LV_ALIGN_BOTTOM_LEFT, 40, 10); 
    lv_obj_set_style_bg_color(btn_back, lv_color_hex(0xe74c3c), 0);
    lv_obj_add_event_cb(btn_back, (lv_event_cb_t)return_to_home, LV_EVENT_CLICKED, NULL);
    lv_obj_t *l_back = lv_label_create(btn_back); lv_label_set_text(l_back, LV_SYMBOL_LEFT); lv_obj_center(l_back);

    new_pin_kb = lv_keyboard_create(settings_scr);
    lv_keyboard_set_mode(new_pin_kb, LV_KEYBOARD_MODE_NUMBER);
    lv_keyboard_set_textarea(new_pin_kb, new_pin_ta);
    lv_obj_set_size(new_pin_kb, 480, 140); lv_obj_align(new_pin_kb, LV_ALIGN_BOTTOM_MID, 0, 0);
    lv_obj_add_flag(new_pin_kb, LV_OBJ_FLAG_HIDDEN);
    lv_obj_add_event_cb(new_pin_kb, kb_visibility_cb, LV_EVENT_READY, NULL);
}

static void uid_handler_thread(void *p1, void *p2, void *p3) {
    /* * CE THREAD EST LANCE PAR LE KERNEL MAIS BLOQUÉ SI BOARD_ROLE_EXIT
     * Cependant, la gestion du RFID n'est faite QUE dans main_rfid.c 
     * Ici on ne fait que traiter les messages reçus de main_rfid.c
     */
    
    #ifdef BOARD_ROLE_EXIT
        LOG_INF("💤 UID Handler désactivé (Mode Sortie)");
        while(1) k_sleep(K_FOREVER);
    #endif

    char uid_hex[UID_STR_LEN];
    while (1) {
        if (k_msgq_get(&uid_msgq, uid_hex, K_FOREVER) == 0) {
            inactivity_counter = 0;
            if (is_dimmed && dimmer_layer) { lv_obj_add_flag(dimmer_layer, LV_OBJ_FLAG_HIDDEN); is_dimmed = false; }

            if (admin_request_pending) {
                if (is_admin(uid_hex)) {
                    admin_active = true; admin_expire_time = k_uptime_get() + 30000; admin_request_pending = false;
                    if (admin_wait_timer) { lv_timer_del(admin_wait_timer); admin_wait_timer = NULL; }
                    lv_scr_load_anim(settings_scr, LV_SCR_LOAD_ANIM_MOVE_LEFT, 200, 0, false);
                    lv_label_set_text(label_admin_status, "Mode Admin Actif");
                } else {
                    admin_request_pending = false; lv_label_set_text(label_status, "Pas le badge Admin!");
                    lv_timer_t *t = lv_timer_create(reset_home_timer_cb, 3000, NULL); lv_timer_set_repeat_count(t, 1);
                }
            } 
            else if (add_badge_mode) {
                if (append_user_badge_local(uid_hex) == 0) {
                    lv_label_set_text(label_admin_status, "Badge ajoute !"); publish_acl_list(); 
                } else { lv_label_set_text(label_admin_status, "Erreur SD"); }
                add_badge_mode = false;
            }
            else if (admin_active && lv_scr_act() == settings_scr) {
                admin_expire_time = k_uptime_get() + 30000;
                lv_label_set_text(label_admin_status, "Badge lu (ignore)");
            }
            else {
                mqtt_send_uid(uid_hex);
                if (check_uid_in_file(uid_hex)) {
                    /* Protection COMPLET aussi pour les badges */
                    if (parking_is_full) {
                        show_denied_banner();
                        lv_label_set_text(label_status, "PARKING COMPLET !");
                        lv_obj_set_style_text_color(label_status, lv_color_hex(0xFF0000), 0);
                    } else {
                        show_success_banner();
                    }
                    lv_timer_t *t = lv_timer_create(reset_home_timer_cb, 5000, NULL); lv_timer_set_repeat_count(t, 1);
                } else {
                    show_denied_banner(); lv_label_set_text(label_status, "Badge Inconnu");
                    lv_timer_t *t = lv_timer_create(reset_home_timer_cb, 3000, NULL); lv_timer_set_repeat_count(t, 1);
                }
            }
            k_msleep(500);
        }
    }
}

K_THREAD_DEFINE(uid_handler_tid, UID_HANDLER_STACK, uid_handler_thread, NULL, NULL, NULL, UID_HANDLER_PRIO, 0, 0);

int main(void) {
    k_msleep(1000);
    const struct device *display_dev = DEVICE_DT_GET(DT_CHOSEN(zephyr_display));
    if (!device_is_ready(display_dev)) return 0;
    
    init_sd_card();
    
    /* Le MQTT tourne sur les deux rôles */
    k_thread_create(&mqtt_thread_data, mqtt_stack_area, K_THREAD_STACK_SIZEOF(mqtt_stack_area), mqtt_thread, NULL, NULL, NULL, MQTT_THREAD_PRIORITY, 0, K_NO_WAIT);
    
    build_home_screen(); 
    build_settings_screen();
    create_dimmer_layer(); 
    
    lv_scr_load(home_scr); 
    display_blanking_off(display_dev);
    
    struct payment_info pay_info;
    
    while (1) { 
        lv_timer_handler(); 
        
        lv_indev_t * indev = lv_indev_get_act();

        if (k_msgq_get(&payment_msgq, &pay_info, K_NO_WAIT) == 0) {
            
            /* GESTION DOUBLE RÔLE DES MESSAGES PAIEMENT */
            
            if (strcmp(pay_info.price, "STOP") == 0) {
                // CAS 1 : "STOP" (Parking Complet) -> Seulement pertinent pour l'ENTRÉE
                #ifdef BOARD_ROLE_ENTRY
                    show_denied_banner(); 
                    char status_msg[64];
                    snprintf(status_msg, sizeof(status_msg), "COMPLET (%s)", pay_info.plate);
                    lv_label_set_text(label_status, status_msg);
                    lv_obj_set_style_text_color(label_status, lv_color_hex(0xFF0000), 0);
                    
                    lv_timer_t *t = lv_timer_create(reset_home_timer_cb, 3000, NULL); 
                    lv_timer_set_repeat_count(t, 1);
                #endif
            } else {
                // CAS 2 : Vrai Prix -> Seulement pertinent pour la SORTIE (QR Code)
                #ifdef BOARD_ROLE_EXIT
                    open_qr_popup(pay_info.plate, pay_info.price, pay_info.cause);
                #endif
            }
        }

	    if (k_sem_take(&payment_success_sem, K_NO_WAIT) == 0) {
            /* Succès Paiement : Utile pour fermer le QR Code sur la sortie */
            LOG_INF("💰 Succès paiement reçu -> Fermeture Popup");
            
            if (qr_popup) {
                lv_obj_add_flag(qr_popup, LV_OBJ_FLAG_HIDDEN);
            }

	        if (qr_autoclose_timer) {
                lv_timer_del(qr_autoclose_timer);
                qr_autoclose_timer = NULL;
            }

            /* Feedback visuel */
            show_success_banner(); 
            
            /* Réveil écran */
            inactivity_counter = 0;
            if (is_dimmed && dimmer_layer) { 
                lv_obj_add_flag(dimmer_layer, LV_OBJ_FLAG_HIDDEN); 
                is_dimmed = false; 
            }
        }

        /* Screensaver Logic */
        if (indev && lv_indev_get_state(indev) == LV_INDEV_STATE_PRESSED) {
            inactivity_counter = 0;
            if (is_dimmed) { is_dimmed = false; if (dimmer_layer) lv_obj_add_flag(dimmer_layer, LV_OBJ_FLAG_HIDDEN); }
        } else {
            inactivity_counter++;
            if (inactivity_counter > SCREENSAVER_TIMEOUT && !is_dimmed) {
                if (dimmer_layer) { lv_obj_clear_flag(dimmer_layer, LV_OBJ_FLAG_HIDDEN); lv_obj_move_foreground(dimmer_layer); }
                is_dimmed = true;
            }
        }
        k_msleep(10); 
    }
}