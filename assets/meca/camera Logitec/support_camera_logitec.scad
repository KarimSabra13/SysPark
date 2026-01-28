// ==============================================
// PARAMETRES ET CONFIGURATION
// ==============================================

// METTRE A 'true' POUR IMPRIMER (STL)
// METTRE A 'false' POUR VOIR L'ASSEMBLAGE
mode_impression = true; 

// --- PARAMETRES DE PRECISION ---
$fn = 60; 
tol = 0.4; 

// --- VISSERIE ---
m3_hole = 3.2; 
m2_hole = 2.2; 
servo_screw_head_d = 7.0; 


// --- DIMENSIONS MATERIEL (Hitec HS-422) ---
s_len = 40.6;
s_wid = 20.0;
s_hgt = 37.0; 
s_tab_len = 54.0; 
hole_ax_L = 48.0; 
hole_ax_W = 10.0; 
wall = 4.0; 

// --- DIMENSIONS ECROU M3 ---
m3_nut_h = 3.0; 
m3_nut_w = 6.0; 

// --- DIMENSIONS PIGNON (GREEN GEAR - 18 DENTS) ---
pinion_pd = 25.4; // Diamètre primitif
pinion_teeth = 18;
pinion_h = 15.0; 
// Diametre hors-tout approximatif pour les trous de passage (base)
gear_outer_d = pinion_pd + 4.0; 

// --- DIMENSIONS CAMERA (ArduCam 8MP Cube) ---
cam_cube_side = 28.0; 
cam_cube_depth = 20.0; 
cam_lens_d = 9.0; 
cam_hole_dist = 21.0; 

// Dimensions connecteur FAKRA (Bleu)
fakra_d = 12.0; 

c_servo = "red";

// --- DIMENSIONS STRUCTURE ---
base_L = 65; 
base_W = 40;
base_X_start = 30; 

// --- DIMENSIONS CAMERA (Logitech C170) ---
// Dimensions officielles (enveloppe externe)
// Largeur (X), Profondeur (Y), Hauteur (Z)
c170_w = 70.3;
c170_d = 71.0;
c170_h = 60.5;

// Jeu d'emboîtement (à ajuster après test)
c170_fit = 0.6;

// Optionnel : diamètre passage câble USB (approx)
c170_cable_d = 4.0;

// ==============================================
// REFERENCE STL C170/C270 (QP058) : import + centrage + extraction du berceau
// ==============================================

c170_ref_file = "QP058_webcam_bracket_130.stl";

// Centre mesuré du STL (pour le mettre à l'origine)
c170_ref_center = [10.0, 72.9955, 11.5];

// Ajustements fins (si besoin plus tard)
c170_ref_rot   = [0, 0, 0];
c170_ref_shift = [0, 0, 0];

// Boite de découpe pour ne garder que le bloc du haut (berceau caméra)
// Dans le repère recentré (après translate(-c170_ref_center))
c170_keep_box_center = [0, 55, 0];     // on vise la zone "haut" du STL (à ajuster)
c170_keep_box_size   = [80, 60, 60];   // largeur, longueur, hauteur de la zone gardée

module ref_c170_qp058_centered() {
    translate(c170_ref_shift)
        rotate(c170_ref_rot)
            translate(-c170_ref_center)
                import(c170_ref_file, convexity=10);
}

module ref_c170_qp058_cradle_only() {
    intersection() {
        ref_c170_qp058_centered();
        translate(c170_keep_box_center)
            cube(c170_keep_box_size, center=true);
    }
}

// ==============================================
// POSE LOCALE : berceau STL par rapport au moyeu/pignon
// (celle que tu as validée)
// ==============================================
module pose_c170_cradle_local() {
    rotate([0, 90, 90])
        translate([-9.5, -33, -8.5])
            children();
}



// ==============================================
// MODULES
// ==============================================

module part_pinion_servo1() {

    difference() {
        union() {
            // Corps du pignon
            cylinder(d=pinion_pd, h=pinion_h);

            // Dents
            for(i=[0:360/pinion_teeth:360])
                rotate([0,0,i])
                    translate([pinion_pd/2-1, -1.5, 0])
                        cube([3, 3, pinion_h]);
        }

        // Trou traversant pour vis centrale (passage facile)
        translate([0,0,-0.5])
            cylinder(d=3.5, h=pinion_h + 1);
    }
}

module dummy_servo(show_gear=true) {
    difference() {
        union() {
            color(c_servo) {
                cube([s_len, s_wid, s_hgt], center=true);
                translate([0, 0, 10]) cube([s_tab_len, s_wid, 2.5], center=true); 
            }
            color("white") translate([10, 0, s_hgt/2]) 
                cylinder(d=6, h=6); 
            
            // Affiche le Pignon Vert (18 dents)
            if(show_gear) {
                translate([10, 0, s_hgt/2 + 2]) 
                color("Lime")
                union() {
                    cylinder(d=pinion_pd, h=pinion_h); 
                    for(i=[0:360/pinion_teeth:360]) rotate([0,0,i]) 
                        translate([pinion_pd/2-1, -1.5, 0]) cube([3, 3, pinion_h]);
                }
            }
        }
        for(i=[-1,1]) for(j=[-1,1]) {
             translate([i*hole_ax_L/2, j*hole_ax_W/2, 10])
                cylinder(d=m3_hole, h=10, center=true); 
        }
    }
}

// ==============================================
// PIGNON 1 (SERVO 1) – IMPRIMABLE, AVEC TROU CENTRAL
// ==============================================



module part_base() {
    difference() {
        union(){
            minkowski() { translate([base_X_start, -base_W/2, 0]) cube([base_L, base_W, 5]); sphere(r=2); }
            minkowski() { translate([30, -10, 0]) cube([6,20,37]); sphere(r=2); }
            minkowski() { translate([82, -10, 0]) cube([13,20,37]); sphere(r=2); }
            minkowski() { translate([91, -10, 37]) cube([4,20,16]); sphere(r=2); }
            difference() {
                minkowski() { translate([50, -20, 52]) cube([45,40,1]); sphere(r=2); }
                // Adaptation trou pour le pignon vert
                translate([69, 0, 50]) cylinder(h=37, d=gear_outer_d + 2); 
            }
        }
        translate([59.3, 0, 0]) { 
            for(i=[-1,1]) for(j=[-1,1]) {
                translate([i*hole_ax_L/2, j*hole_ax_W/2, 35]) cylinder(d=2.8, h=30, center=true); 
            }
        }
        translate([base_X_start + base_L/2, 0, 0]) { 
            for(i=[-1,1]) for(j=[-1,1]) {
                translate([i*(base_L/2 - 4), j*(base_W/2 - 4), 0]) cylinder(d=4, h=50, center=true); 
            }
        }
        translate([59.3, 0, 0]) { 
            for(i=[-1,1]) for(j=[-1,1]) {
                translate([i*hole_ax_L/2, j*hole_ax_W/2, 32]) cube([m3_nut_w, 20, m3_nut_h], center=true);
            }
        }
        translate([80, 0, 15]) cube([40, 12, 6], center=true);
    }
}

module part_u_bracket() {
    u_width_inside = s_wid + 1; 
    bracket_H = 50;
    center_offset_X = -bracket_H/2; 
    
    // Adaptation au pignon vert
    cup_wall = 3; 
    cup_OD = pinion_pd + 2*cup_wall + 4; // Un peu plus large pour la solidité
    
    slot_w = s_wid + 1.0; 
    
    difference() {
        union() {
            // Corps de la cloche (Hub)
            translate([0,0, -pinion_h + 5]) cylinder(h=pinion_h, d=cup_OD);
            cylinder(h=5, d=cup_OD);
            
            // Bras du U
            translate([center_offset_X, -15, 5]) {
                cube([bracket_H, 30, wall]); 
                translate([0, 0, 0]) cube([wall, 30, u_width_inside + wall + 5]);
                translate([-5, 0, 0]) cube([6, 14, u_width_inside + wall + 5]);
                translate([bracket_H-wall, 0, 0]) cube([wall, 30, u_width_inside + wall + 5]); 
                translate([bracket_H-wall+3, 0, 0]) cube([6, 14, u_width_inside + wall + 5]);
            }
        }
        
        // --- SOUSTRACTION DU PIGNON VERT (EMBOITEMENT) ---
        // On reproduit la forme du pignon en négatif avec tolérance
        translate([0,0, -pinion_h + 5 - 0.1]) {
             cylinder(d=pinion_pd + tol, h=pinion_h + 0.1); 
             for(i=[0:360/pinion_teeth:360]) rotate([0,0,i]) 
                translate([pinion_pd/2-1 - tol/2, -1.5 - tol/2, 0]) 
                cube([3 + tol, 3 + tol, pinion_h + 0.1]);
        }
        
        // Fentes verticales
        translate([center_offset_X - 3, -slot_w/2, 5 + wall + s_wid/2 -10]) cube([wall+4, 3, 50]); 
        translate([center_offset_X + bracket_H - wall - 1, -slot_w/2, 5 + wall + s_wid/2 -10]) cube([wall+4, 3, 50]); 
        
        // Trou central vis
        translate([0,0, -20]) cylinder(h=50, d=3.5); 
        
        // Trous fixation servo 2
        translate([center_offset_X - 1, 0, 5 + wall + s_wid/2]) rotate([0,90,0]) {
             translate([hole_ax_L/2, 0, 0]) cylinder(h=10, d=3.5);
             translate([-hole_ax_L/2, 0, 0]) cylinder(h=10, d=3.5);
             translate([hole_ax_L/2, hole_ax_W/2, 0]) cylinder(h=10, d=3.5);
             translate([hole_ax_L/2, -hole_ax_W/2, 0]) cylinder(h=10, d=3.5);
             translate([-hole_ax_L/2, hole_ax_W/2, 0]) cylinder(h=10, d=3.5);
             translate([-hole_ax_L/2, -hole_ax_W/2, 0]) cylinder(h=10, d=3.5);
        }
        
        // Trou passage cable tilt
        translate([22, 13, 20]) cube([10, 6, 12], center=true);
    }
}

module part_pinion_gear() {
    pd = pinion_pd; 
    teeth = pinion_teeth; 
    
    difference() {
        union() {
            cylinder(d=pd, h=pinion_h); 
            for(i=[0:360/teeth:360]) rotate([0,0,i]) translate([pd/2-1, -1.5, 0]) cube([3, 3, pinion_h]);
        }
        cylinder(d=8, h=20, center=true); 
        for(r=[0:90:360]) rotate([0,0,r]) translate([8,0,0]) cylinder(d=2.5, h=20, center=true);
            
    translate([0,0,-0.5])
            cylinder(d=m3_hole, h=pinion_h+1);
    }
    
}

// ==============================================
// SUPPORT CAMERA C170 : moyeu pignon + bras + berceau STL (QP058)
// ==============================================
module part_camera_mount_c170() {

    pd = pinion_pd;
    teeth = pinion_teeth;

    hub_d = pd + 10;
    hub_h = 15;

    arm_len = 20;

    difference() {
        union() {
            // 1) Moyeu (interface pignon)
            cylinder(d=hub_d, h=hub_h + wall);

            // 2) Bras (si utile, on ajustera après)
            translate([-hub_d/2, -arm_len, 0])
                cube([hub_d, arm_len, hub_h + wall]);

            // 3) Le berceau STL devient la pièce support caméra
            pose_c170_cradle_local()
                ref_c170_qp058_cradle_only();
        }

        // Négatif pignon (emboîtement)
        translate([0,0, -0.1]) {
            cylinder(d=pd + tol, h=hub_h + 0.1);
            for(i=[0:360/teeth:360]) rotate([0,0,i])
                translate([pd/2-1 - tol/2, -1.5 - tol/2, 0])
                    cube([3 + tol, 3 + tol, hub_h + 0.1]);
        }

        // Trou central vis
        translate([0,0, -5]) cylinder(d=3.5, h=50);
    }
}



// ==============================================
// VISUALISATION / GENERATION
// ==============================================

if (mode_impression) {
    // --- DISPOSITION A PLAT POUR IMPRESSION 3D ---
    
    // 1. La Base
    part_base();

    // 2. Le U-Bracket (décalé)
    translate([100, 40, 0]) 
        part_u_bracket();

// 3. Le Support Caméra (décalé)
translate([150, 0, 0])
    part_camera_mount_c170();

    // 4. Le Pignon 
    translate([100, -50, 15]) 
    rotate([180, 0, 0])
        part_pinion_gear();
    
        // 5. Le Pignon Le 2e pignon
    translate([150, -50, 15]) 
    rotate([180, 0, 0])
        part_pinion_gear();
        
} else {
    // --- MODE ASSEMBLAGE (VISUEL) ---
    
    // 1. Base
    color("Silver") part_base();

    // 2. Servo 1 
    translate([59.3, 0, 30]) %dummy_servo(show_gear=true);

    // 3. U-Bracket monté sur servo 1
    translate([69.3, 0, 52 + pinion_h]) { 
        rotate([0,0,0]) {
            color("SkyBlue") part_u_bracket();
        }
    }

    // 4. SERVO 2 (FIXE)
    translate([68.5,0 ,87 ]) 
            rotate([90, 0, 0]) 
            %dummy_servo(show_gear=false);

    // 5. PIGNON (FIXE SUR SERVO 2)
    translate([79, 0, 97])        
        rotate([90, 90, 0])          
        translate([10, 0, 21]) 
        color("Lime") part_pinion_gear();

// 6. SUPPORT CAMERA C170 (test)
translate([79, 0, 97])
    rotate([90, 90, 0])
    translate([10, 0, 21])
        color("Gold") part_camera_mount_c170();

        
// 7. BERCEAU CAMERA (REFERENCE STL QP058, sans le pied)
pose_c170_cradle_ref()
    %ref_c170_qp058_cradle_only();




}