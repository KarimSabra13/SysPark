
# Create Project

create_project -force -name nexys4ddr -part xc7a100tcsg324-1
set_msg_config -id {Common 17-55} -new_severity {Warning}

# Add project commands


# Add Sources

read_verilog {/home/karim/fpga/pythondata-cpu-vexriscv-smp/pythondata_cpu_vexriscv_smp/verilog/Ram_1w_1rs_Generic.v}
read_verilog {/home/karim/fpga/pythondata-cpu-vexriscv-smp/pythondata_cpu_vexriscv_smp/verilog/VexRiscvLitexSmpCluster_Cc2_Iw64Is8192Iy2_Dw64Ds8192Dy2_ITs4DTs4_Ldw64_Cdma_Ood_Hb1.v}
read_verilog {/home/karim/fpga/linux-on-litex-vexriscv/build/nexys4ddr/gateware/nexys4ddr.v}

# Add EDIFs


# Add IPs


# Add constraints

read_xdc nexys4ddr.xdc
set_property PROCESSING_ORDER EARLY [get_files nexys4ddr.xdc]

# Add pre-synthesis commands


# Synthesis

synth_design -directive default -top nexys4ddr -part xc7a100tcsg324-1

# Synthesis report

report_timing_summary -file nexys4ddr_timing_synth.rpt
report_utilization -hierarchical -file nexys4ddr_utilization_hierarchical_synth.rpt
report_utilization -file nexys4ddr_utilization_synth.rpt
write_checkpoint -force nexys4ddr_synth.dcp

# Add pre-optimize commands


# Optimize design

opt_design -directive default

# Add pre-placement commands


# Placement

place_design -directive default

# Placement report

report_utilization -hierarchical -file nexys4ddr_utilization_hierarchical_place.rpt
report_utilization -file nexys4ddr_utilization_place.rpt
report_io -file nexys4ddr_io.rpt
report_control_sets -verbose -file nexys4ddr_control_sets.rpt
report_clock_utilization -file nexys4ddr_clock_utilization.rpt
write_checkpoint -force nexys4ddr_place.dcp

# Add pre-routing commands


# Routing

route_design -directive default
phys_opt_design -directive default
write_checkpoint -force nexys4ddr_route.dcp

# Routing report

report_timing_summary -no_header -no_detailed_paths
report_route_status -file nexys4ddr_route_status.rpt
report_drc -file nexys4ddr_drc.rpt
report_timing_summary -datasheet -max_paths 10 -file nexys4ddr_timing.rpt
report_power -file nexys4ddr_power.rpt

# Bitstream generation

write_bitstream -force nexys4ddr.bit 

# End

quit