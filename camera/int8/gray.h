#pragma once
#include <stdint.h>
void gray_input(const uint16_t* pixels,int8_t* input);
void gray_input_rows(const uint16_t* pixels,int8_t* input,unsigned first,unsigned count);
