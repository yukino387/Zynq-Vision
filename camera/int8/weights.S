.section .rodata
.balign 64
.global commands
.type commands, %object
commands:
.incbin "C:/00_workplace/fpga/cnn_accelerator/camera/int8/metadata.bin", 0, 1320
.size commands, .-commands
.section .note.GNU-stack,"",%progbits
