.section .rodata
.balign 64
.global weights
.type weights, %object
weights:
.incbin "C:/00_workplace/fpga/cnn_accelerator/camera/int8/weights.bin"
.size weights, .-weights
.balign 64
.global metadata
.type metadata, %object
metadata:
.incbin "C:/00_workplace/fpga/cnn_accelerator/camera/int8/metadata.bin"
.size metadata, .-metadata
.section .note.GNU-stack,"",%progbits
