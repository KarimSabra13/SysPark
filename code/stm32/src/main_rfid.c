#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <zephyr/drivers/spi.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/sys/printk.h>
#include <zephyr/logging/log.h>
#include <string.h>
#include <stdio.h>
#include "role_config.h"

LOG_MODULE_REGISTER(rfid_rc522, LOG_LEVEL_INF);

extern struct k_msgq uid_msgq;
#define UID_STR_LEN 16

#define RFID_STACK_SIZE 2048
#define RFID_PRIORITY   5

/* RST matériel RC522 : Toujours sur PG6 */
#define RC522_RST_NODE   DT_NODELABEL(gpiog)
#define RC522_RST_PIN    6

/* Registres MFRC522 */
#define CommandReg       0x01
#define ComIrqReg        0x04
#define ErrorReg         0x06
#define FIFODataReg      0x09
#define FIFOLevelReg     0x0A
#define ControlReg       0x0C
#define BitFramingReg    0x0D
#define CollReg          0x0E
#define ModeReg          0x11
#define TxControlReg     0x14
#define TxASKReg         0x15
#define RFCfgReg         0x26
#define TModeReg         0x2A
#define TPrescalerReg    0x2B
#define TReloadRegH      0x2C
#define TReloadRegL      0x2D
#define CRCResultRegH    0x21
#define CRCResultRegL    0x22
#define VersionReg       0x37

#define PCD_IDLE         0x00
#define PCD_TRANSCEIVE   0x0C
#define PCD_RESETPHASE   0x0F
#define PCD_CALCCRC      0x03
#define PICC_REQIDL      0x26
#define PICC_ANTICOLL    0x93
#define PICC_SELECT_CL1  0x93
#define PICC_HALT        0x50
#define DivIrqReg        0x05

/* * Récupération de la config SPI depuis le DeviceTree 
 * Cela va automatiquement utiliser le CS défini dans l'overlay (PA15)
 */
static const struct spi_dt_spec spi_rc522 =
    SPI_DT_SPEC_GET(DT_NODELABEL(rc522),
                    SPI_WORD_SET(8) | SPI_TRANSFER_MSB | SPI_OP_MODE_MASTER);

static const struct device *gpio_rst;

/* Helpers SPI */
static inline void rc522_write(uint8_t reg, uint8_t val)
{
    uint8_t tx[2] = { (uint8_t)((reg << 1) & 0x7E), val };
    struct spi_buf b = { .buf = tx, .len = 2 };
    struct spi_buf_set s = { .buffers = &b, .count = 1 };
    spi_write_dt(&spi_rc522, &s);
}

static inline uint8_t rc522_read(uint8_t reg)
{
    uint8_t tx[2] = { (uint8_t)(((reg << 1) & 0x7E) | 0x80), 0x00 };
    uint8_t rx[2];
    struct spi_buf bt = { .buf = tx, .len = 2 };
    struct spi_buf br = { .buf = rx, .len = 2 };
    struct spi_buf_set ts = { .buffers = &bt, .count = 1 };
    struct spi_buf_set rs = { .buffers = &br, .count = 1 };
    spi_transceive_dt(&spi_rc522, &ts, &rs);
    return rx[1];
}
    
static inline void rc522_set_bits(uint8_t reg, uint8_t mask) { rc522_write(reg, rc522_read(reg) | mask); }
static inline void rc522_clear_bits(uint8_t reg, uint8_t mask) { rc522_write(reg, rc522_read(reg) & (uint8_t)~mask); }

static void rc522_antenna_on(void)
{
    uint8_t t = rc522_read(TxControlReg);
    if ((t & 0x03) != 0x03) rc522_write(TxControlReg, t | 0x03);
}

static void rc522_init_full(void)
{
    if (device_is_ready(gpio_rst)) {
        gpio_pin_set(gpio_rst, RC522_RST_PIN, 0); k_msleep(5);
        gpio_pin_set(gpio_rst, RC522_RST_PIN, 1); k_msleep(5);
    }
    rc522_write(CommandReg, PCD_RESETPHASE); k_msleep(5);
    rc522_write(TModeReg, 0x8D);
    rc522_write(TPrescalerReg, 0x3E);
    rc522_write(TReloadRegL, 30);
    rc522_write(TReloadRegH, 0);
    rc522_write(ModeReg, 0x3D);
    rc522_write(TxASKReg, 0x40);
    rc522_write(RFCfgReg, 0x70);
    rc522_antenna_on();
}
 
static void rc522_calc_crc(const uint8_t *data, size_t len, uint8_t *crc2)
{
    rc522_write(CommandReg, PCD_IDLE);
    rc522_write(FIFOLevelReg, 0x80);
    for (size_t i = 0; i < len; ++i) rc522_write(FIFODataReg, data[i]);
    rc522_write(DivIrqReg, 0x04);
    rc522_write(CommandReg, PCD_CALCCRC);
    for (int i = 0; i < 25; ++i) {
        if (rc522_read(DivIrqReg) & 0x04) break;
        k_busy_wait(200);
    }
    crc2[0] = rc522_read(CRCResultRegL);
    crc2[1] = rc522_read(CRCResultRegH);
}

static bool rc522_reqa(uint8_t *atqa)
{
    rc522_write(ComIrqReg, 0x7F); rc522_write(FIFOLevelReg, 0x80);
    rc522_write(BitFramingReg, 0x07); rc522_write(FIFODataReg, PICC_REQIDL);
    rc522_write(CommandReg, PCD_TRANSCEIVE); rc522_set_bits(BitFramingReg, 0x80);
    for (int i=0; i<80; ++i) { if (rc522_read(ComIrqReg) & 0x30) break; k_busy_wait(400); }
    rc522_clear_bits(BitFramingReg, 0x80);
    if ((rc522_read(ErrorReg) & 0x13) || (rc522_read(FIFOLevelReg) < 2)) return false;
    atqa[0] = rc522_read(FIFODataReg); atqa[1] = rc522_read(FIFODataReg);
    return true;
}
    
static bool rc522_anticoll(uint8_t *uid5)
{   
    rc522_write(ComIrqReg, 0x7F); rc522_write(FIFOLevelReg, 0x80); 
    rc522_write(BitFramingReg, 0x00); rc522_write(FIFODataReg, PICC_ANTICOLL); rc522_write(FIFODataReg, 0x20);
    rc522_write(CommandReg, PCD_TRANSCEIVE); rc522_set_bits(BitFramingReg, 0x80);
    for (int i=0; i<80; ++i) { if (rc522_read(ComIrqReg) & 0x30) break; k_busy_wait(400); }
    rc522_clear_bits(BitFramingReg, 0x80);
    if ((rc522_read(ErrorReg) & 0x1B) || (rc522_read(FIFOLevelReg) < 5)) return false;
    for (int i=0; i<5; ++i) uid5[i] = rc522_read(FIFODataReg);
    return true;
}
    
static bool rc522_select_uid5(const uint8_t uid5[5], uint8_t *sak)
{
    uint8_t frame[9] = { PICC_SELECT_CL1, 0x70 };
    for (int i=0; i<5; ++i) frame[2+i] = uid5[i];
    uint8_t crc[2]; rc522_calc_crc(frame, 7, crc);
    frame[7] = crc[0]; frame[8] = crc[1];
    
    rc522_write(CommandReg, PCD_IDLE); rc522_write(ComIrqReg, 0x7F);
    rc522_write(FIFOLevelReg, 0x80); rc522_write(BitFramingReg, 0x00);
    for (int i=0; i<9; ++i) rc522_write(FIFODataReg, frame[i]);
    rc522_write(CommandReg, PCD_TRANSCEIVE); rc522_set_bits(BitFramingReg, 0x80);
    for (int i=0; i<80; ++i) { if (rc522_read(ComIrqReg) & 0x30) break; k_busy_wait(400); }
    rc522_clear_bits(BitFramingReg, 0x80);
    if ((rc522_read(ErrorReg) & 0x13) || (rc522_read(FIFOLevelReg) < 1)) return false;
    *sak = rc522_read(FIFODataReg);
    return true;
}

/* ---------- Thread Principal ---------- */
void rfid_thread(void *p1, void *p2, void *p3)
{

    /* 👇 DÉSACTIVATION SI MODE SORTIE 👇 */
    #ifndef BOARD_ROLE_ENTRY
        LOG_INF("💤 Thread RFID DÉSACTIVÉ (Mode Sortie)");
        while (1) k_sleep(K_FOREVER);
    #endif


    ARG_UNUSED(p1); ARG_UNUSED(p2); ARG_UNUSED(p3);
    printk("\n=== RC522 prêt (SPI2 CS=PA15) ===\n");
    
    gpio_rst = DEVICE_DT_GET(RC522_RST_NODE);
    if (device_is_ready(gpio_rst)) {
        gpio_pin_configure(gpio_rst, RC522_RST_PIN, GPIO_OUTPUT_ACTIVE);
        gpio_pin_set(gpio_rst, RC522_RST_PIN, 1);
    } else {
        LOG_WRN("GPIO RST (PG6) non prêt");
    }

    if (!spi_is_ready_dt(&spi_rc522)) {
        LOG_ERR("SPI RC522 non prêt");
        return;
    }
    
    rc522_init_full();
    LOG_INF("VersionReg = 0x%02X", rc522_read(VersionReg));
    
    uint8_t atqa[2], uid[5], last_uid[5] = {0};
    bool last_valid = false;
    char uid_hex[UID_STR_LEN] = {0};
    
    while (1) {
        if (rc522_reqa(atqa)) {
            if (rc522_anticoll(uid)) {  
                uint8_t sak = 0;
                if (rc522_select_uid5(uid, &sak)) {
                    if (!last_valid || memcmp(uid, last_uid, 5) != 0) {
                        memcpy(last_uid, uid, 5);
                        last_valid = true;
                        LOG_INF("UID: %02X %02X %02X %02X", uid[0], uid[1], uid[2], uid[3]);
                        snprintf(uid_hex, sizeof(uid_hex), "%02X%02X%02X%02X%02X",
                                 uid[0], uid[1], uid[2], uid[3], uid[4]);
                        k_msgq_put(&uid_msgq, uid_hex, K_NO_WAIT);
                    }
                } 
            }
        } else {
            last_valid = false;
        }
        k_msleep(150);
    }
}
K_THREAD_DEFINE(rfid_tid, RFID_STACK_SIZE, rfid_thread, NULL, NULL, NULL, RFID_PRIORITY, 0, 0);