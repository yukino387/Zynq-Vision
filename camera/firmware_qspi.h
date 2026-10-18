#pragma once
#include <stdint.h>

bool firmware_qspi_init();
bool firmware_qspi_read(uint32_t offset, void* destination, uint32_t size);
bool firmware_qspi_erase_4k(uint32_t offset);
bool firmware_qspi_erase_64k(uint32_t offset);
bool firmware_qspi_program(uint32_t offset, const void* source, uint32_t size);
bool firmware_qspi_verify(uint32_t offset, const void* source, uint32_t size);
