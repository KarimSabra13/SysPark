PACKAGES=libc libcompiler_rt libbase libfatfs liblitespi liblitedram libliteeth liblitesdcard liblitesata bios
PACKAGE_DIRS=/home/karim/fpga/litex/litex/soc/software/libc /home/karim/fpga/litex/litex/soc/software/libcompiler_rt /home/karim/fpga/litex/litex/soc/software/libbase /home/karim/fpga/litex/litex/soc/software/libfatfs /home/karim/fpga/litex/litex/soc/software/liblitespi /home/karim/fpga/litex/litex/soc/software/liblitedram /home/karim/fpga/litex/litex/soc/software/libliteeth /home/karim/fpga/litex/litex/soc/software/liblitesdcard /home/karim/fpga/litex/litex/soc/software/liblitesata /home/karim/fpga/litex/litex/soc/software/bios
LIBS=libc libcompiler_rt libbase libfatfs liblitespi liblitedram libliteeth liblitesdcard liblitesata
TRIPLE=riscv64-unknown-elf
CPU=vexriscv
CPUFAMILY=riscv
CPUFLAGS= -march=rv32i2p0_ma -mabi=ilp32 -D__vexriscv_smp__ -D__riscv_plic__
CPUENDIANNESS=little
CLANG=0
CPU_DIRECTORY=/home/karim/fpga/litex/litex/soc/cores/cpu/vexriscv_smp
SOC_DIRECTORY=/home/karim/fpga/litex/litex/soc
PICOLIBC_DIRECTORY=/home/karim/fpga/pythondata-software-picolibc/pythondata_software_picolibc/data
PICOLIBC_FORMAT=integer
COMPILER_RT_DIRECTORY=/home/karim/fpga/pythondata-software-compiler_rt/pythondata_software_compiler_rt/data
export BUILDINC_DIRECTORY
BUILDINC_DIRECTORY=/home/karim/fpga/linux-on-litex-vexriscv/build/nexys4ddr/software/include
LIBC_DIRECTORY=/home/karim/fpga/litex/litex/soc/software/libc
LIBCOMPILER_RT_DIRECTORY=/home/karim/fpga/litex/litex/soc/software/libcompiler_rt
LIBBASE_DIRECTORY=/home/karim/fpga/litex/litex/soc/software/libbase
LIBFATFS_DIRECTORY=/home/karim/fpga/litex/litex/soc/software/libfatfs
LIBLITESPI_DIRECTORY=/home/karim/fpga/litex/litex/soc/software/liblitespi
LIBLITEDRAM_DIRECTORY=/home/karim/fpga/litex/litex/soc/software/liblitedram
LIBLITEETH_DIRECTORY=/home/karim/fpga/litex/litex/soc/software/libliteeth
LIBLITESDCARD_DIRECTORY=/home/karim/fpga/litex/litex/soc/software/liblitesdcard
LIBLITESATA_DIRECTORY=/home/karim/fpga/litex/litex/soc/software/liblitesata
BIOS_DIRECTORY=/home/karim/fpga/litex/litex/soc/software/bios
LTO=0
BIOS_CONSOLE_LITE=1