/* src/role_config.h */
#ifndef ROLE_CONFIG_H
#define ROLE_CONFIG_H

/* ============================================================
 * CHOIX DU RÔLE DE LA CARTE (Décommenter UNE seule ligne)
 * ============================================================ */

// #define BOARD_ROLE_ENTRY  1  /* Borne d'Entrée (RFID, Moteur, Ascenseur, LCD, OLED) */
#define BOARD_ROLE_EXIT   1  /* Borne de Sortie (QR Code Paiement, Code Sortie uniquement) */

/* ============================================================ */

#if defined(BOARD_ROLE_ENTRY) && defined(BOARD_ROLE_EXIT)
    #error "Impossible d'activer ENTREE et SORTIE en même temps !"
#endif

#if !defined(BOARD_ROLE_ENTRY) && !defined(BOARD_ROLE_EXIT)
    #error "Veuillez choisir un role dans role_config.h"
#endif

#endif