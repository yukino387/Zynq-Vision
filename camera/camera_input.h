#ifndef CAMERA_INPUT_H
#define CAMERA_INPUT_H
#include <cstdint>
#include "basic_op.h"
constexpr unsigned CAMERA_PIXELS = 416 * 416;
constexpr unsigned CAMERA_BYTES = CAMERA_PIXELS * 2;
bool camera_init();
bool camera_capture(uint16_t* pixels);
bool camera_begin(uint16_t* pixels);
bool camera_finish(uint16_t* pixels);
bool camera_ready();
bool camera_set_brightness(int level);
void camera_to_input(const uint16_t* pixels, data_t* input);
#endif
