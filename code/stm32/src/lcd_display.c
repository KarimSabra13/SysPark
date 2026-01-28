#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <zephyr/drivers/i2c.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>
#include <zephyr/logging/log.h>
LOG_MODULE_DECLARE(net_mqtt_publisher_sample, LOG_LEVEL_INF);

#include "cJSON.h"
#include "role_config.h"

#define I2C_NODE DT_NODELABEL(i2c1)
#define LCD_ADDR 0x27

#define LCD_STACK_SIZE 3072
#define LCD_PRIORITY   7
#define LCD_COLS       20
#define PARKING_CAPACITY 31 /* Ta capacité réelle */

static const struct device *i2c_dev;

/* === Synchronisation et sécurité === */
static K_MUTEX_DEFINE(lcd_lock);
static volatile bool lcd_force_show = false;
static int refresh_counter = 0;

/* =========================================================================
 * BAS NIVEAU LCD (Inchangé)
 * ========================================================================= */
static void lcd_send_cmd(uint8_t cmd) {
    k_mutex_lock(&lcd_lock, K_FOREVER);
    uint8_t u = cmd & 0xF0;
    uint8_t l = (cmd << 4) & 0xF0;
    uint8_t b[4] = { u|0x0C, u|0x08, l|0x0C, l|0x08 };
    for (int i=0; i<4; i++) {
        i2c_write(i2c_dev, &b[i], 1, LCD_ADDR);
        k_msleep(1);
    }
    k_mutex_unlock(&lcd_lock);
}

static void lcd_send_data(uint8_t d) {
    k_mutex_lock(&lcd_lock, K_FOREVER);
    uint8_t u = d & 0xF0;
    uint8_t l = (d << 4) & 0xF0;
    uint8_t b[4] = { u|0x0D, u|0x09, l|0x0D, l|0x09 };
    for (int i=0; i<4; i++) {
        i2c_write(i2c_dev, &b[i], 1, LCD_ADDR);
        k_msleep(1);
    }
    k_mutex_unlock(&lcd_lock);
}

static void lcd_clear(void) { lcd_send_cmd(0x01); k_msleep(2); }

static void lcd_set_cursor(uint8_t row, uint8_t col){
    static const uint8_t off[] = {0x00,0x40,0x14,0x54};
    lcd_send_cmd(0x80 | (off[row] + col));
}

static void lcd_print(const char *s){
    while(*s) lcd_send_data((uint8_t)*s++);
}

static void lcd_init(void){
    k_msleep(50);
    lcd_send_cmd(0x02);
    lcd_send_cmd(0x28); 
    lcd_send_cmd(0x0C); 
    lcd_send_cmd(0x06); 
    lcd_clear();
}

static void fit20(char *dst, size_t dstsz, const char *fmt, ...) {
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(dst, dstsz, fmt, ap);
    va_end(ap);
    size_t n = strlen(dst);
    if (n > LCD_COLS) dst[LCD_COLS] = '\0';
}

static void lcd_show_block(const char *lines[4]){
    k_mutex_lock(&lcd_lock, K_FOREVER);
    lcd_clear();
    for (int i=0;i<4;i++){ lcd_set_cursor(i,0); lcd_print(lines[i]); }
    k_mutex_unlock(&lcd_lock);
}

static void lcd_transition_to(const char *next[4]){
    k_mutex_lock(&lcd_lock, K_FOREVER);
    for (int i=0;i<4;i++){
        lcd_set_cursor(i,0);
        for (int j=0;j<LCD_COLS;j++) lcd_send_data(' ');
        k_msleep(50);
    }
    lcd_show_block(next);
    k_mutex_unlock(&lcd_lock);
}

/* =========================================================================
 * CONTENU DES PAGES (DYNAMIQUE)
 * ========================================================================= */
/* Page 1 : Places Libres */
static char p1_l1[LCD_COLS+1] = "=== Parking CPE ===";
static char p1_l2[LCD_COLS+1] = "                    ";
static char p1_l3[LCD_COLS+1] = "   Places: -- / 31 ";
static char p1_l4[LCD_COLS+1] = "                    ";
static const char *page1[4] = { p1_l1, p1_l2, p1_l3, p1_l4 };

/* Page 2 : Météo / Capteurs */
static char p2_l1[LCD_COLS+1] = "Temp: --.- C";
static char p2_l2[LCD_COLS+1] = "Humidite: -- %";
static char p2_l3[LCD_COLS+1] = "CO2: --- ppm";
static char p2_l4[LCD_COLS+1] = "Air: n/a";
static const char *page2[4] = { p2_l1, p2_l2, p2_l3, p2_l4 };

/* Page 3 : Prévisions */
static char p3_l1[LCD_COLS+1] = "Meteo: n/a";
static char p3_l2[LCD_COLS+1] = "Vent: --.- km/h";
static char p3_l3[LCD_COLS+1] = "Prevision: --.- C";
static char p3_l4[LCD_COLS+1] = "Aucune pluie";
static const char *page3[4] = { p3_l1, p3_l2, p3_l3, p3_l4 };

/* =========================================================================
 * THREAD D'AFFICHAGE
 * ========================================================================= */
static void lcd_display_thread(void *a, void *b, void *c){

    #ifndef BOARD_ROLE_ENTRY
        // Pas de logs ici car pas de LOG_MODULE_REGISTER dans ce fichier
        while (1) k_sleep(K_FOREVER);
    #endif


    ARG_UNUSED(a); ARG_UNUSED(b); ARG_UNUSED(c);

    i2c_dev = DEVICE_DT_GET(I2C_NODE);
    if (!device_is_ready(i2c_dev)) {
        LOG_ERR("I2C device not ready");
        return;
    }

    lcd_init();
    const char **pages[] = { page1, page2, page3 };
    const int n = ARRAY_SIZE(pages);

    while (1){
        for (int i=0;i<n;i++){
            if (refresh_counter++ > 30) {
                LOG_WRN("🔄 Réinitialisation automatique du LCD");
                lcd_init();
                refresh_counter = 0;
            }

            if (lcd_force_show) {
                lcd_transition_to(page2);
                k_sleep(K_SECONDS(3));
                lcd_transition_to(page3);
                lcd_force_show = false;
            } else {
                lcd_show_block(pages[i]);
                k_sleep(K_SECONDS(5));
                lcd_transition_to(pages[(i+1)%n]);
            }
        }
    }
}

/* =========================================================================
 * MISE A JOUR VIA MQTT (PLACES & METEO)
 * ========================================================================= */
 
/* Appelée quand on reçoit "LIBRE:x" ou "COMPLET" */
void lcd_update_places(const char *text) {
    k_mutex_lock(&lcd_lock, K_FOREVER);
    
    // Si le topic contient "text", c'est peut-être un message générique, 
    // mais ici on s'attend à "LIBRE:x" ou "COMPLET"
    
    if (strstr(text, "COMPLET") != NULL) {
        // Affiche 31 / 31 si complet
        fit20(p1_l3, sizeof(p1_l3), "   Voitures: %d / %d ", PARKING_CAPACITY, PARKING_CAPACITY);
    } 
    else if (strncmp(text, "LIBRE:", 6) == 0) {
        /* Le serveur envoie les places LIBRES */
        int places_libres = atoi(text + 6);
        
        /* Tu veux afficher les voitures PRÉSENTES */
        int voitures_presentes = PARKING_CAPACITY - places_libres;
        
        // Sécurité pour ne pas afficher de nombres négatifs
        if (voitures_presentes < 0) voitures_presentes = 0;
        if (voitures_presentes > PARKING_CAPACITY) voitures_presentes = PARKING_CAPACITY;

        fit20(p1_l3, sizeof(p1_l3), "   Voitures: %d / %d ", voitures_presentes, PARKING_CAPACITY);
    }
    
    k_mutex_unlock(&lcd_lock);
}

void lcd_update_from_mqtt(const char *json_str)
{
    LOG_INF("📺 LCD update JSON: %s", json_str ? json_str : "(null)");
    if (!json_str || !*json_str) return;

    cJSON *root = cJSON_Parse(json_str);
    if (!root) return;

    /* ... parsing inchangé ... */
    const cJSON *temp = cJSON_GetObjectItem(root, "temperature");
    const cJSON *hum  = cJSON_GetObjectItem(root, "humidite");
    const cJSON *co2  = cJSON_GetObjectItem(root, "co2");
    const cJSON *air  = cJSON_GetObjectItem(root, "air");
    const cJSON *desc = cJSON_GetObjectItem(root, "description");
    const cJSON *vent = cJSON_GetObjectItem(root, "vent");
    const cJSON *prev = cJSON_GetObjectItem(root, "prevision");
    const cJSON *plui = cJSON_GetObjectItem(root, "pluie");

    k_mutex_lock(&lcd_lock, K_FOREVER);
    fit20(p2_l1, sizeof(p2_l1), "Temp: %.1f C", temp ? temp->valuedouble : 0.0);
    fit20(p2_l2, sizeof(p2_l2), "Humidite: %d %%", hum ? hum->valueint : 0);
    fit20(p2_l3, sizeof(p2_l3), "CO2: %d ppm", co2 ? co2->valueint : 0);
    fit20(p2_l4, sizeof(p2_l4), "Air: %s", (air && air->valuestring) ? air->valuestring : "n/a");

    fit20(p3_l1, sizeof(p3_l1), "Meteo: %s", (desc && desc->valuestring) ? desc->valuestring : "n/a");
    fit20(p3_l2, sizeof(p3_l2), "Vent: %.1f km/h", vent ? vent->valuedouble : 0.0);
    fit20(p3_l3, sizeof(p3_l3), "Prevision: %.1f C", prev ? prev->valuedouble : 0.0);
    fit20(p3_l4, sizeof(p3_l4), "%s", (plui && plui->valuestring) ? plui->valuestring : "n/a");
    k_mutex_unlock(&lcd_lock);

    lcd_force_show = true;
    refresh_counter = 0;
    cJSON_Delete(root);
}

K_THREAD_DEFINE(lcd_display_tid, LCD_STACK_SIZE, lcd_display_thread,
                NULL, NULL, NULL, LCD_PRIORITY, 0, 0);