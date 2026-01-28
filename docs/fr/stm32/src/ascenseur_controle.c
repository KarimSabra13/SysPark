#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <zephyr/drivers/spi.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/logging/log.h>
#include <zephyr/sys/util.h>
#include <stdlib.h>
#include <string.h>
#include "role_config.h"

LOG_MODULE_REGISTER(ascenseur, LOG_LEVEL_INF);

/* =========================================================
 * CONFIGURATION TMC5160
 * ========================================================= */
#define TMC5160_GCONF          0x00
#define TMC5160_GSTAT          0x01
#define TMC5160_IHOLD_IRUN     0x10
#define TMC5160_GLOBAL_SCALER  0x0B
#define TMC5160_CHOPCONF       0x6C

static const struct spi_dt_spec spi_spec =
    SPI_DT_SPEC_GET(DT_NODELABEL(tmc5160),
                    SPI_WORD_SET(8) | SPI_MODE_CPOL | SPI_MODE_CPHA);

static const struct gpio_dt_spec en_spec   = GPIO_DT_SPEC_GET(DT_ALIAS(motor_enable), gpios);
static const struct gpio_dt_spec step_spec = GPIO_DT_SPEC_GET(DT_ALIAS(motor_step), gpios);
static const struct gpio_dt_spec dir_spec  = GPIO_DT_SPEC_GET(DT_ALIAS(motor_dir), gpios);
static const struct gpio_dt_spec limit_sw  = GPIO_DT_SPEC_GET(DT_ALIAS(limit_switch), gpios);

/* =========================================================
 * CONFIGURATION MÉCANIQUE
 * ========================================================= */
#define MICROSTEPS     16
#define STEP_PER_FLOOR (3850 * MICROSTEPS) 

#define ACCEL_STEPS    (200 * MICROSTEPS)
#define DECEL_STEPS    (200 * MICROSTEPS)

#define MIN_DELAY_US   200  
#define MAX_DELAY_US   2000 
#define STOP_DELAY_MS  3000

#define BTN_RDC_PIN    2 
#define BTN_1_PIN      6 
#define BTN_2_PIN      7 

static int  current_floor = 0;
static bool going_up = true;
static int  target_floor = -1;
static bool up_requests[3]   = {false, false, false};
static bool down_requests[3] = {false, false, false};
static bool position_lost = false; /* Pour gérer la perte d'alim pendant mouvement */

static bool is_homing = false;

/* =========================================================
 * FONCTIONS BAS NIVEAU TMC5160
 * ========================================================= */
static int tmc_write(uint8_t addr, uint32_t data)
{
    uint8_t tx[5];
    tx[0] = addr | 0x80;
    tx[1] = (uint8_t)(data >> 24);
    tx[2] = (uint8_t)(data >> 16);
    tx[3] = (uint8_t)(data >> 8);
    tx[4] = (uint8_t)(data);
    struct spi_buf buf = { .buf = tx, .len = sizeof(tx) };
    struct spi_buf_set set = { .buffers = &buf, .count = 1 };
    return spi_write_dt(&spi_spec, &set);
}

static int tmc_read(uint8_t addr, uint32_t *data)
{
    uint8_t tx1[5] = { addr & 0x7F, 0, 0, 0, 0 };
    uint8_t rx1[5] = {0};
    uint8_t tx2[5] = {0};
    uint8_t rx2[5] = {0};

    struct spi_buf buf1 = { .buf = tx1, .len = 5 };
    struct spi_buf_set set1 = { .buffers = &buf1, .count = 1 };
    struct spi_buf r_buf1 = { .buf = rx1, .len = 5 };
    struct spi_buf_set r_set1 = { .buffers = &r_buf1, .count = 1 };
    
    /* 1er transfert : adresse */
    if (spi_transceive_dt(&spi_spec, &set1, &r_set1) != 0) return -1;

    struct spi_buf buf2 = { .buf = tx2, .len = 5 };
    struct spi_buf_set set2 = { .buffers = &buf2, .count = 1 };
    struct spi_buf r_buf2 = { .buf = rx2, .len = 5 };
    struct spi_buf_set r_set2 = { .buffers = &r_buf2, .count = 1 };

    /* 2ème transfert : data */
    if (spi_transceive_dt(&spi_spec, &set2, &r_set2) != 0) return -1;

    *data = ((uint32_t)rx2[1] << 24) | ((uint32_t)rx2[2] << 16) | 
            ((uint32_t)rx2[3] << 8)  | (uint32_t)rx2[4];
    return 0;
}

static int tmc_init_minimal(void)
{
    int ret;
    ret = tmc_write(TMC5160_GSTAT, 0x00000007); if (ret) return ret;
    ret = tmc_write(TMC5160_GCONF, 0x00000000); if (ret) return ret;
    ret = tmc_write(TMC5160_IHOLD_IRUN, (6U << 16) | (25U << 8) | 8U); if (ret) return ret;
    ret = tmc_write(TMC5160_GLOBAL_SCALER, 128); if (ret) return ret;
    uint32_t chopconf = 0x000100C3 | (1U << 28) | (4U << 24);
    ret = tmc_write(TMC5160_CHOPCONF, chopconf);
    
    LOG_INF("✅ TMC5160 (Re)configuré");
    return ret;
}

/* Renvoie true si problème d'alim détecté */
static bool tmc_check_health(void)
{
    uint32_t gstat = 0;
    int err = tmc_read(TMC5160_GSTAT, &gstat);
    
    if (err != 0) return true; /* Erreur SPI */

    /* Bit 0 = Reset, Bit 2 = Undervoltage */
    if ((gstat & 0x01) || (gstat & 0x04)) {
        LOG_WRN("⚠️ ALERTE ALIM: GSTAT=0x%x -> Réinit", gstat);
        tmc_init_minimal();
        gpio_pin_set_dt(&en_spec, 1);
        return true; 
    }
    return false;
}

static inline void step_pulse_once(void)
{
    gpio_pin_set_dt(&step_spec, 1);
    k_busy_wait(2);
    gpio_pin_set_dt(&step_spec, 0);
}

/* =========================================================
 * PROCÉDURE DE HOMING (LOGIQUE CORRIGÉE)
 * ========================================================= */
static void homing_procedure(void)
{
    is_homing = true; /* Début du mode Homing */

    if (!gpio_is_ready_dt(&limit_sw)) {
        LOG_ERR("Erreur: Capteur Fin de course non prêt");
	is_homing = false;
        return;
    }
    
    gpio_pin_configure_dt(&limit_sw, GPIO_INPUT);

    /* Si déjà touché au départ */
    if (gpio_pin_get_dt(&limit_sw) == 1) {
        LOG_INF("🎚️ Déjà au RDC");
        current_floor = 0;
	is_homing = false;
        return;
    }

    LOG_INF("🏠 Homing Rapide: Descente vers RDC...");

    /* Direction BAS (1) */
    gpio_pin_set_dt(&dir_spec, 1); 

    /* Variable de vitesse dynamique pour l'accélération */
    uint32_t current_delay = MAX_DELAY_US;

    /* Tant que le capteur n'est PAS touché (0) */
    while (gpio_pin_get_dt(&limit_sw) == 0) {
        
        tmc_check_health();
        
        step_pulse_once();
        k_usleep(current_delay); 

        /* ACCÉLÉRATION : On réduit le délai à chaque pas jusqu'à atteindre la vitesse max */
        if (current_delay > MIN_DELAY_US) {
            /* On enlève 2µs à chaque pas pour une accélération douce */
            current_delay -= 2; 
            if (current_delay < MIN_DELAY_US) {
                current_delay = MIN_DELAY_US;
            }
        }
    }

    LOG_INF("✅ Fin de course touché !");
    current_floor = 0;
    
    /* Petit dégagement vers le haut */
    gpio_pin_set_dt(&dir_spec, 0); // Haut
    for (int i=0; i<100; i++) {
        step_pulse_once();
        k_usleep(1000);
    }
    
    current_floor = 0;
    position_lost = false;
    
    up_requests[0]=up_requests[1]=up_requests[2]=false;
    down_requests[0]=down_requests[1]=down_requests[2]=false;
    is_homing = false; /* Fin du mode Homing */
}

/* =========================================================
 * LOGIQUE REQUÊTES
 * ========================================================= */
static void clear_request(int f) { up_requests[f] = false; down_requests[f] = false; }

static int next_up(void) {
    for (int f = current_floor + 1; f <= 2; f++) if (up_requests[f] || down_requests[f]) return f;
    return -1;
}
static int next_down(void) {
    for (int f = current_floor - 1; f >= 0; f--) if (up_requests[f] || down_requests[f]) return f;
    return -1;
}
static bool any_above(void) { return next_up() != -1; }
static bool any_below(void) { return next_down() != -1; }

static void move_to_target(int target)
{
    /* Si la position est perdue, on refuse de bouger 'normalement' */
    if (position_lost) {
        LOG_WRN("Position perdue, Homing requis !");
        return; 
    }

    if (tmc_check_health()) {
        position_lost = true;
        return;
    }

    bool up = (target > current_floor);
    
    /* SÉCURITÉ BUTÉE BASSE (LOGIQUE CORRIGÉE) */
    /* Si on veut descendre ALORS qu'on touche le capteur (1), Stop */
    if (!up && gpio_pin_get_dt(&limit_sw) == 1) {
        LOG_WRN("⛔ Butée basse (1), impossible de descendre !");
        current_floor = 0;
        clear_request(target);
        return;
    }

    int floors_to_go = abs(target - current_floor);
    int total_steps = floors_to_go * STEP_PER_FLOOR;
    int current_step = 0;

    /* 0=Haut, 1=Bas */
    gpio_pin_set_dt(&dir_spec, up ? 0 : 1);

    LOG_INF("Départ %s vers %d (%d steps)", up ? "↑" : "↓", target, total_steps);

    int64_t last_check_time = k_uptime_get();

    while (current_step < total_steps) {
        
        /* Check santé moteur toutes les 50ms */
        int64_t now = k_uptime_get();
        if ((now - last_check_time) > 50) {
            if (tmc_check_health()) {
                LOG_ERR("⛔ COUPURE ALIM PENDANT MOUVEMENT -> Position Perdue");
                position_lost = true;
                return; /* ABORT */
            }
            last_check_time = now;
        }

        /* SÉCURITÉ CAPTEUR PENDANT DESCENTE (LOGIQUE CORRIGÉE) */
        if (!up && gpio_pin_get_dt(&limit_sw) == 1) {
            LOG_INF("⛔ Arrêt sur capteur (RDC atteint prématurément)");
            current_floor = 0;
            clear_request(target);
            return;
        }

        uint32_t delay_us;

        if (current_step < ACCEL_STEPS) {
            delay_us = MAX_DELAY_US - ((MAX_DELAY_US - MIN_DELAY_US) * current_step) / ACCEL_STEPS;
        } 
        else if (current_step > (total_steps - DECEL_STEPS)) {
            int remaining = total_steps - current_step;
            delay_us = MIN_DELAY_US + ((MAX_DELAY_US - MIN_DELAY_US) * (DECEL_STEPS - remaining)) / DECEL_STEPS;
        } 
        else {
            delay_us = MIN_DELAY_US;
        }

        step_pulse_once();
        k_usleep(delay_us);
        
        current_step++;

        if ((current_step % STEP_PER_FLOOR) == 0) {
            current_floor += up ? 1 : -1;
            LOG_INF("Passage étage %d (théorique)", current_floor);

            if (up_requests[current_floor] || down_requests[current_floor]) {
                LOG_INF("Arrêt intermédiaire");
                clear_request(current_floor);
                k_msleep(STOP_DELAY_MS);
            }
        }
    }

    current_floor = target;
    LOG_INF("✅ Arrivé étage %d", current_floor);
    clear_request(current_floor);
    k_msleep(STOP_DELAY_MS);
}

/* =========================================================
 * INTERFACE & THREAD
 * ========================================================= */
static void handle_button(int f) {
    if (f > current_floor) up_requests[f] = true;
    else if (f < current_floor) down_requests[f] = true;
    else up_requests[f] = true;
    LOG_INF("Bouton étage %d", f);
}

static struct gpio_callback cb_rdc, cb_1, cb_2;
static void button_isr(const struct device *dev, struct gpio_callback *cb, uint32_t pins) {
    if (pins & BIT(BTN_RDC_PIN)) handle_button(0);
    if (pins & BIT(BTN_1_PIN)) handle_button(1);
    if (pins & BIT(BTN_2_PIN)) handle_button(2);
}

int ascenseur_get_current_floor(void) { return current_floor; }
int ascenseur_get_target_floor(void)  { return target_floor; }
bool ascenseur_is_going_up(void)      { return going_up; }
bool ascenseur_is_homing(void)        { return is_homing; }

void ascenseur_request_floor(int floor) {
    if (floor < 0 || floor > 2 || floor == current_floor) return;
    going_up = (floor > current_floor);
    target_floor = floor;
    if (going_up) up_requests[floor] = true;
    else down_requests[floor] = true;
    LOG_INF("Requête externe: étage %d", floor);
}

void ascenseur_thread(void *p1, void *p2, void *p3)
{

    /* 👇 DÉSACTIVATION SI MODE SORTIE 👇 */
    #ifndef BOARD_ROLE_ENTRY
        LOG_INF("💤 Thread Ascenseur DÉSACTIVÉ (Mode Sortie)");
        while (1) k_sleep(K_FOREVER);
    #endif


    LOG_INF("Démarrage Ascenseur (Safe Homing)");

    if (!spi_is_ready_dt(&spi_spec)) return;
    if (!gpio_is_ready_dt(&en_spec) || !gpio_is_ready_dt(&step_spec) || !gpio_is_ready_dt(&dir_spec)) return;
    if (!gpio_is_ready_dt(&limit_sw)) { LOG_ERR("GPIO Limit Switch HS"); return; }

    gpio_pin_configure_dt(&en_spec, GPIO_OUTPUT_INACTIVE);
    gpio_pin_configure_dt(&step_spec, GPIO_OUTPUT_INACTIVE);
    gpio_pin_configure_dt(&dir_spec, GPIO_OUTPUT_INACTIVE);

    if (tmc_init_minimal() != 0) { LOG_ERR("TMC Init Failed"); return; }
    
    gpio_pin_set_dt(&en_spec, 1); 

    const struct device *portc = DEVICE_DT_GET(DT_NODELABEL(gpioc));
    const struct device *porti = DEVICE_DT_GET(DT_NODELABEL(gpioi));
    
    gpio_pin_configure(porti, BTN_RDC_PIN, GPIO_INPUT | GPIO_PULL_UP);
    gpio_pin_configure(portc, BTN_1_PIN,   GPIO_INPUT | GPIO_PULL_UP);
    gpio_pin_configure(portc, BTN_2_PIN,   GPIO_INPUT | GPIO_PULL_UP);
    
    gpio_pin_interrupt_configure(porti, BTN_RDC_PIN, GPIO_INT_EDGE_FALLING);
    gpio_pin_interrupt_configure(portc, BTN_1_PIN,   GPIO_INT_EDGE_FALLING);
    gpio_pin_interrupt_configure(portc, BTN_2_PIN,   GPIO_INT_EDGE_FALLING);
    
    gpio_init_callback(&cb_rdc, button_isr, BIT(BTN_RDC_PIN)); gpio_add_callback(porti, &cb_rdc);
    gpio_init_callback(&cb_1, button_isr, BIT(BTN_1_PIN)); gpio_add_callback(portc, &cb_1);
    gpio_init_callback(&cb_2, button_isr, BIT(BTN_2_PIN)); gpio_add_callback(portc, &cb_2);

    /* === LANCEMENT DU HOMING === */
    k_msleep(500); 
    homing_procedure();

    while (1) {
        /* Si on a perdu la position (coupure pendant mouvement), on refait un homing */
        if (position_lost) {
            LOG_WRN("Position inconnue -> Homing auto");
            homing_procedure();
        }

        /* Vérif santé au repos */
        if (tmc_check_health()) {
            position_lost = true;
        }

        if (going_up) {
            if (any_above()) { target_floor = next_up(); move_to_target(target_floor); }
            else if (any_below()) { going_up = false; }
            else { k_msleep(200); }
        } else {
            if (any_below()) { target_floor = next_down(); move_to_target(target_floor); }
            else if (any_above()) { going_up = true; }
            else { k_msleep(200); }
        }
    }
}