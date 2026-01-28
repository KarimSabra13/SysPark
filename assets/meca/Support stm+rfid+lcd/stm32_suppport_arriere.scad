// --- PARAMÈTRES ---
$fn = 50;

// 1. DIMENSIONS EXACTES (Vos réglages validés)
pcb_w = 130.0;
pcb_h = 80.0;

// Positions exactes centres des 4 trous STM32 : 3.8 mm des bords G/D et 4 mm des bords H/B
hole_x   = (pcb_w / 2) - 3.8;   // = 65 - 3.8 = 61.2
pos_y_top = (pcb_h / 2) - 4.0;  // = 40 - 4 = 36
pos_y_bot = -((pcb_h / 2) - 4.0); // = -36

// LCD secondaire (infos places + météo/CO2)
lcd2_w = 98.0;
lcd2_h = 60.0;
lcd2_depth = 22.0;

lcd2_clearance = 0.4;     // jeu par côté
lcd2_frame_wall = 2.0;    // épaisseur du cadre de maintien
lcd2_ext_margin = 6.0;    // marge autour dans l’extension
lcd2_gap = 5.0;           // distance entre haut de plaque STM32 et fenêtre LCD2

mount_side = 7.0;   // +7 mm à gauche et +7 mm à droite pour zone de vissage arrière

// 2. ÉCRAN
screen_w = 105.0;
screen_h = 67.0;
screen_offset_y = 3.0; 

// 3. PARAMÈTRES DU STAND VERTICAL
plate_margin = 5.0; 
plate_thick = 3.0;  
spacer_h = 6.0;     
tilt_angle = 15;    // Inclinaison en arrière (degrés)
foot_depth = 60;    // Profondeur du pied

// Dimensions RFID RC522
pcb_width = 40;
pcb_height = 60;
hole_dist_x = 33; 
hole_dist_y = 54;
pcb_thickness = 1.6;

// Paramètres du boîtier
angle = 20;
wall_thick = 3.0;       // Épaisseur des murs extérieurs
front_layer = 0.8;      // Épaisseur de la façade (FIN pour bien capter !)
internal_depth = 15;    // Place pour les composants et les fils
cable_slot_w = 21.3;    // Largeur du trou pour les câbles


// --- MODULE PRINCIPAL (RFID) ---
module rfid_console_embedded() {
    
    // Dimensions totales du bloc
    box_w = pcb_width + (wall_thick * 2) + 4; // +4mm de marge
    box_h = pcb_height + (wall_thick * 2) + 4;
    box_d = internal_depth + front_layer + wall_thick; // Profondeur totale locale
    
    difference() {
        // 1. LE VOLUME EXTÉRIEUR (Le Pupitre)
        hull() {
            translate([0, 0, sin(angle)*box_h/2]) 
            rotate([angle, 0, 0])
                cube([box_w, box_h, box_d], center=true);

            translate([0, 20, -10])
                cube([box_w, 60, 2], center=true);
        }

        // 2. L'ÉVIDEMENT INTERNE (LA POCHE)
        translate([0, 0, sin(angle)*box_h/2]) 
        rotate([angle, 0, 0]) {
            translate([0, 0, front_layer+10+6.5]) 
                cube([pcb_width + 2, pcb_height + 2, box_d], center=true);

            translate([1.6, box_h/2 - 5+2, 0+5+5.4])
                cube([cable_slot_w, 10, 9], center=true);
        }

        // 3. TROU ARRIÈRE GLOBAL
        translate([0, 20, -4]) cube([box_w - 6, 90, 30], center=true);

        // 4. TROUS DE FIXATION TRAVERSANTS + POCHES ECROUS
        translate([0, 0, sin(angle)*box_h/2]) 
        rotate([angle, 0, 0]) {

            xL = -pcb_width/2;
            xR =  pcb_width/2;
            yB = -pcb_height/2;
            yT =  pcb_height/2;

            // ---- TROUS M3 PASSANTS ----
            translate([xL + 7.0,  yB + 6.8, 0])
                cylinder(d=3.2, h=box_d + 5, center=false);

            translate([xR - 7.0,  yB + 6.8, 0])
                cylinder(d=3.2, h=box_d + 5, center=false);

            translate([xR - 2.0,  yT - 15.0, -10])
                cylinder(d=3.2, h=box_d + 5, center=false);

            translate([xL + 2.5,  yT - 15.0, -10])
                cylinder(d=3.2, h=box_d + 5, center=false);

            // ---- POCHES POUR ECROUS ----
            nut_pocket_xy = 10;
            nut_pocket_z  = 6;
            nut_pocket_zc = -box_d/2 + 2;

            translate([xL + 7.0,  yB + 6.8, nut_pocket_zc+12])
                cube([nut_pocket_xy, nut_pocket_xy, nut_pocket_z], center=true);

            translate([xR - 7.0,  yB + 6.8, nut_pocket_zc+12])
                cube([nut_pocket_xy, nut_pocket_xy, nut_pocket_z], center=true);

            translate([xR - 2.0,  yT - 15.0, nut_pocket_zc])
                cube([nut_pocket_xy, nut_pocket_xy, nut_pocket_z], center=true);

            translate([xL + 2.5,  yT - 15.0, nut_pocket_zc])
                cube([nut_pocket_xy, nut_pocket_xy, nut_pocket_z], center=true);
        }
    }
}


// --- MODULE 1 : LA FAÇADE COMPLÈTE (Plaque + Trous + Piliers) ---
module head_assembly() {

    // Jeu (par côté) pour insertion
    screen_clearance = 0.4;

    // Écran principal : cadre arrière
    screen_depth = 5.0;
    screen_frame_wall = 2.0;

    // Centre découpe écran principal (coin sup droit : 12 mm du bord droit, 6 mm du bord haut)
    screen_cx = (pcb_w/2) - (screen_w/2) - 12;
    screen_cy = (pcb_h/2) - (screen_h/2) - 6;

    // LCD2 : fenêtre visible (97x40) + rebord intérieur 5mm
    lcd2_screen_w = 97.0;
    lcd2_screen_h = 40.0;

    // Placement fenêtre visible LCD2 : coin inférieur gauche à 0.5 mm du bord gauche et 9 mm du bas
    lcd2_screen_off_left = 0.5;
    lcd2_screen_off_bottom = 9.0;

    // Trous LCD2 (M3) : centre à 2.5 mm du bord gauche/droit et 2 mm du bas/haut
    lcd2_hole_off_x = 2.5;
    lcd2_hole_off_y = 2.0;
    lcd2_hole_d = 3.5;

    // Dimensions plaque (élargie)
    plate_w_base = pcb_w + 2*plate_margin;
    plate_w      = plate_w_base + 2*mount_side;
    plate_h      = pcb_h + 2*plate_margin;

    plate_top = (pcb_h/2) + plate_margin;
    lcd2_cx = 0;
    lcd2_cy = plate_top + lcd2_gap + (lcd2_h/2);

    // Extension LCD2 : même largeur que la plaque STM32
    ext_w = plate_w;
    ext_h = lcd2_h + 2*lcd2_ext_margin;

    // Vis boitier avant <-> arrière
    case_screw_d    = 3.2;
    case_screw_edge = 12.0;
    case_screw_x = (plate_w/2) - (mount_side/2);

    case_screw_y1 = -(plate_h/2) + case_screw_edge - 60;
    case_screw_y3 = (lcd2_cy + ext_h/2) - case_screw_edge;
    case_screw_y2 = (case_screw_y1 + case_screw_y3) / 2;

    // Bords LCD2
    lcd2_xL = lcd2_cx - lcd2_w/2;
    lcd2_xR = lcd2_cx + lcd2_w/2;
    lcd2_yB = lcd2_cy - lcd2_h/2;
    lcd2_yT = lcd2_cy + lcd2_h/2;

    // Centre fenêtre visible LCD2
    lcd2_screen_cx = lcd2_xL + lcd2_screen_off_left + (lcd2_screen_w/2);
    lcd2_screen_cy = lcd2_yB + lcd2_screen_off_bottom + (lcd2_screen_h/2);

    // Rebord intérieur LCD2
    lcd2_screen_depth = 5.0;
    lcd2_screen_frame_wall = 2.0;

    union() {

        // A. Plaque + découpes
        difference() {

            union() {
                // Corps principal (STM32)
                translate([0, 0, plate_thick/2])
                    cube([plate_w, plate_h, plate_thick], center=true);

                // Extension LCD2
                translate([lcd2_cx, lcd2_cy, plate_thick/2])
                    cube([ext_w, ext_h, plate_thick], center=true);

                // Pattes latérales descendantes
                total_h = plate_h + (lcd2_gap + lcd2_h + 2*lcd2_ext_margin + 53);

                for (sx = [-1, 1]) {
                    translate([sx * (plate_w/2 - mount_side/2), (lcd2_cy - ext_h/2)/2 - 17, plate_thick/2])
                        cube([mount_side, total_h, plate_thick], center=true);
                }
            }

            // Découpe écran principal
            translate([screen_cx, screen_cy, 0])
                cube([screen_w + 2*screen_clearance,
                      screen_h + 2*screen_clearance,
                      plate_thick + 10], center=true);

            // Fenêtre LCD2
            translate([lcd2_screen_cx, lcd2_screen_cy, 0])
                cube([lcd2_screen_w + 2*screen_clearance,
                      lcd2_screen_h + 2*screen_clearance,
                      plate_thick + 10], center=true);

            // Trous fixation STM32 (M3)
            for (sx = [-1, 1]) for (sy = [-1, 1]) {
                translate([ sx * (pcb_w/2 - 3.8),  sy * (pcb_h/2 - 4.0), 0 ])
                    cylinder(d=3.5, h=20, center=true);
            }

            // Trous fixation LCD2 (M3)
            for (hx = [lcd2_xL + lcd2_hole_off_x, lcd2_xR - lcd2_hole_off_x])
            for (hy = [lcd2_yB + lcd2_hole_off_y, lcd2_yT - lcd2_hole_off_y]) {
                translate([hx, hy, 0])
                    cylinder(d=lcd2_hole_d, h=20, center=true);
            }

            // Trous boitier avant/arrière (6x M3)
            for (sx = [-1, 1])
            for (yy = [case_screw_y1, case_screw_y2, case_screw_y3]) {
                translate([sx * case_screw_x, yy, 0])
                    cylinder(d=case_screw_d, h=30, center=true);
            }
        }

        // B. Cadre arrière écran principal (5 mm)
        translate([screen_cx, screen_cy, plate_thick + screen_depth/2])
        difference() {
            cube([(screen_w + 2*screen_clearance) + 2*screen_frame_wall,
                  (screen_h + 2*screen_clearance) + 2*screen_frame_wall,
                  screen_depth], center=true);

            cube([(screen_w + 2*screen_clearance),
                  (screen_h + 2*screen_clearance),
                  screen_depth + 0.2], center=true);
        }

        // C. Rebord intérieur LCD2 (5 mm)
        translate([lcd2_screen_cx, lcd2_screen_cy, plate_thick + lcd2_screen_depth/2])
        difference() {
            cube([(lcd2_screen_w + 2*screen_clearance) + 2*lcd2_screen_frame_wall,
                  (lcd2_screen_h + 2*screen_clearance) + 2*lcd2_screen_frame_wall,
                  lcd2_screen_depth], center=true);

            cube([(lcd2_screen_w + 2*screen_clearance),
                  (lcd2_screen_h + 2*screen_clearance),
                  lcd2_screen_depth + 0.2], center=true);
        }

        // C2. Piliers LCD2
        lcd2_standoff_d = 7.0;
        lcd2_standoff_h = 8.0;
        lcd2_standoff_hole_d = 3.2;

        for (hx = [lcd2_xL + lcd2_hole_off_x, lcd2_xR - lcd2_hole_off_x])
        for (hy = [lcd2_yB + lcd2_hole_off_y, lcd2_yT - lcd2_hole_off_y]) {
            translate([hx, hy, plate_thick + lcd2_standoff_h/2])
            difference() {
                cylinder(d=lcd2_standoff_d, h=lcd2_standoff_h, center=true);
                cylinder(d=lcd2_standoff_hole_d, h=lcd2_standoff_h + 2, center=true);
            }
        }

        // D. Piliers STM32
        translate([0, 0, plate_thick]) {
            for (dir_x = [-1, 1]) {
                translate([dir_x * hole_x, pos_y_top, 0]) standoff_pillar();
                translate([dir_x * hole_x, pos_y_bot, 0]) standoff_pillar();
            }
        }
    }
}

module standoff_pillar() {
    difference() {
        cylinder(d=7.0, h=spacer_h+2);
        translate([0,0,-1])
            cylinder(d=3.2, h=spacer_h + 4);
    }
}


// --- MODULE 2 : ASSEMBLAGE FINAL (Avec le pied) ---
module vertical_stand() {
    total_h_plate = pcb_h + plate_margin*2;
    difference(){
        union() {
            // 1. La Tête (Inclinée)
            translate([0, 0, (total_h_plate/2) * sin(tilt_angle) + 2])
                translate([0, total_h_plate/2+60, -13.7])
                    head_assembly();

            // 2. Le Pied
            translate([0, foot_depth/2 - 10 + 10, plate_thick/2])
                cube([pcb_w + plate_margin*2, foot_depth, plate_thick], center=true);

            // 3. Renforts sur les cotés
            for(mx = [-1, 1]) {
                translate([mx * ((pcb_w/2) + plate_margin - 1.5)-1.5, 0, plate_thick])
                rotate([90, 0, 90])
                linear_extrude(3)
                polygon([[0,0],[foot_depth - 5 + 20, 0],[0, 50]]);
            }
        }
        rotate([0, 0, 0]) translate([-12.3, 34+6.4, -5]) cube([15+6.35, 11, 10]);
    }
}


// --- BOITIER ARRIERE ---
module face_arriere() {

    case_wall   = 7.0;
    rear_depth  = 50.0;
    open_bottom = 55.0;

    plate_w_base = pcb_w + 2*plate_margin;
    plate_w      = plate_w_base + 2*mount_side;
    plate_h      = pcb_h + 2*plate_margin;

    plate_top = (pcb_h/2) + plate_margin;
    lcd2_cx   = 0;
    lcd2_cy   = plate_top + lcd2_gap + (lcd2_h/2);

    ext_w = plate_w;
    ext_h = lcd2_h + 2*lcd2_ext_margin;

    case_screw_d    = 3.2;
    case_screw_edge = 12.0;
    case_screw_x    = (plate_w/2) - (mount_side/2);

    case_screw_y1 = -(plate_h/2) + case_screw_edge - 60;
    case_screw_y3 = (lcd2_cy + ext_h/2) - case_screw_edge;
    case_screw_y2 = (case_screw_y1 + case_screw_y3) / 2;

    z0 = plate_thick;

    y_leg_center = (lcd2_cy - ext_h/2)/2 - 17;
    total_h      = plate_h + (lcd2_gap + lcd2_h + 2*lcd2_ext_margin + 53);
    y_bottom_all = y_leg_center - total_h/2;

    difference() {
        hull() {
            translate([0, 0, z0 + rear_depth/2])
                cube([plate_w, plate_h, rear_depth], center=true);

            translate([lcd2_cx, lcd2_cy+60, z0 + rear_depth/2])
                cube([ext_w, ext_h, rear_depth], center=true);
        }

        hull() {
            translate([0, 40, z0 + (rear_depth - case_wall)/2])
                cube([plate_w - 2*case_wall, plate_h - 2*case_wall + 190, rear_depth - case_wall], center=true);

            translate([lcd2_cx, lcd2_cy, z0 + (rear_depth - case_wall)/2])
                cube([ext_w - 2*case_wall, ext_h - 2*case_wall, rear_depth - case_wall], center=true);
        }

        translate([0, y_bottom_all + open_bottom/2, z0 + rear_depth/2])
            cube([plate_w + 80, open_bottom, rear_depth + 80], center=true);

        for (sx = [-1, 1])
        for (yy = [case_screw_y1, case_screw_y2, case_screw_y3]) {
            translate([sx * case_screw_x, yy + 60, z0 + rear_depth/2])
                cylinder(d=case_screw_d, h=rear_depth + 20, center=true);
        }
    }
}


// --- RENDU / EXPORT (TOUT DANS LE MEME STL) ---
eps = 0.2; // petit recouvrement pour éviter surfaces coplanaires (fusion plus fiable)

module all_in_one() {
    render(convexity=10)
/*
    union() {

        // structure principale
        rotate([0, 90, 0])
            vertical_stand();

        // pupitre RFID
        rotate([180, 270, 90])
            translate([0, -30, 11])
                rfid_console_embedded();
*/
        // boitier arrière (légèrement "poussé" dans l'avant pour souder)
        rotate([90, 90, 0])
            translate([0, 25 + 0, plate_thick - eps-56])
                face_arriere();

    
}

all_in_one();
