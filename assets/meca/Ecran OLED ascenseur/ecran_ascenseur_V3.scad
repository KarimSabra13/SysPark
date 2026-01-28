// --- PARTIE 1 : PARAMÈTRES ---
$fn = 50;

// --- PARAMÈTRES BOUTONS ---
btn_total_h = 8.0;   
btn_cyl_h   = 6.0;   
btn_stick_out = 3.0; 

facade_thick = btn_cyl_h - btn_stick_out; 

btn_body_size = 6.4; 
btn_body_size_largeur = 8;
btn_cyl_dia = 4.5;   
btn_vertical_spacing = 11; 
btn_x_offset = 28;   
side_panel_w = 18;   

// --- PARAMÈTRES OLED ---
pcb_width = 35.5;
pcb_height = 33.7; 
screen_width = 24;   
screen_height = 15;
screen_offset_y = -2; 

// Trous recentrés
hole_dist_x = 31.0; 
hole_dist_y = 29.0; 

// Diamètre vis M3
hole_dia = 3.2;     

// --- PARAMÈTRES BOÎTIER ---
wall_thick = 2.0;
inner_depth_oled = 6; 
tolerance = 0.4;

// Passage de câbles élargi
pin_cutout_width = 20; 

total_oled_h = facade_thick + inner_depth_oled;

// --- NOUVEAUX PARAMÈTRES DE DIMENSION (CORRECTION -1CM) ---
// Ancienne longueur : 136. Nouvelle : 126.
base_length = 126; 

// Position GLOBALE (Adaptée à la nouvelle longueur)
// On décale l'écran de 10mm vers la gauche pour garder les proportions
oled_global_x = 61.5; // Était 71.5
oled_global_z = 60 - 23;   
oled_rot = [90, 180, 0];


// --- MODULES (Formes) ---

module shape_boitier_solid(marge=0) {
    outer_w = pcb_width + (wall_thick * 2) + tolerance;
    outer_h = pcb_height + (wall_thick * 2) + tolerance;

    union() {
        cube([outer_w + marge, outer_h + marge, total_oled_h], center=true);
        translate([ (outer_w/2) + (side_panel_w/2) - 2, 0, (total_oled_h/2) - (facade_thick/2)]) 
            cube([side_panel_w + marge, outer_h + marge, facade_thick], center=true);
    }
}

module oled_case_gray() {
    outer_w = pcb_width + (wall_thick * 2) + tolerance;
    outer_h = pcb_height + (wall_thick * 2) + tolerance;

    difference() {
        shape_boitier_solid(marge=0);

        // Interieur
        translate([0, 0, facade_thick])
            cube([pcb_width + tolerance, pcb_height + tolerance, inner_depth_oled + 1], center=true);
        translate([0, screen_offset_y, 0])
            cube([screen_width, screen_height, total_oled_h + 2], center=true);
        
        // Trous Vis
        for (x = [-1, 1], y = [-1, 1]) {
            translate([x * (hole_dist_x / 2), y * (hole_dist_y / 2), 0])
                cylinder(d=hole_dia, h=total_oled_h + 2, center=true);
        }
        
        // Passage nappe
        translate([0, (outer_h/2), 0])
            cube([pin_cutout_width, wall_thick * 4, total_oled_h * 2], center=true);

        // Boutons
        for (i = [-1, 0, 1]) {
            translate([btn_x_offset, i * btn_vertical_spacing, (total_oled_h/2) - (facade_thick/2)]) {
                cylinder(d=btn_cyl_dia, h=facade_thick*3, center=true);
            }
        }
    }
}

module holes_in_green_support() {
    // Trous vis traversants
    for (x = [-1, 1], y = [-1, 1]) {
        translate([x * (hole_dist_x / 2), y * (hole_dist_y / 2), 0])
            cylinder(d=hole_dia, h=50, center=true); 
    }
    
    // Passage nappe traversant
    translate([0, 17, 0]) 
        cube([pin_cutout_width, 7, 50], center=true);
        
    for (i = [-1, 0, 1]) {
        translate([btn_x_offset, i * btn_vertical_spacing, 0])
            cube([btn_body_size_largeur, btn_body_size, 50], center=true); 
    }
}

module support_base() {
    rod_x = 5;      
    rod_y = 5;      
    rod_dia = 11;   
    boss_dia = 16;  

    difference() {
        union() {
            // MODIFICATION ICI : Longueur passée à base_length (126mm)
            color("Green") translate([0, 0, 0]) cube([base_length, 10, 65]);
            translate([rod_x, rod_y, 65/2]) 
                cylinder(d=boss_dia, h=65, center=true);
        }
        
        // MODIFICATION ICI : Décalage de l'encoche de fin (-10mm)
        // Ancienne pos : 122.7. Nouvelle : 112.7 pour suivre la réduction
        translate([112.7, -5, 0]) cube([10.3, 20, 60]); 
        
        translate([rod_x, rod_y, 0]) 
            cylinder(d=rod_dia, h=120, center=true); 
    }
}

// --- MISE EN PLACE POUR IMPRESSION (PLATEAU) ---

offset_flush = -(total_oled_h / 2);

union() {
    
    // PIÈCE 1 : Le Support Vert (Couché sur le dos)
    translate([0, 0, 0]) 
    rotate([90, 0, 0])   
    difference() {
        support_base();
        
        // On recrée les trous avec la marge de 0.4mm
        translate([oled_global_x, 0, oled_global_z]) 
        rotate(oled_rot) {
            translate([0, 0, offset_flush]) 
                shape_boitier_solid(marge=0.4); 
            translate([0, 0, -10])
                holes_in_green_support();
        }
    }

    // PIÈCE 2 : Le Boîtier Gris (Façade contre plateau)
    translate([70, -100, 0]) 
    rotate([0, 180, 0]) 
        oled_case_gray();
}