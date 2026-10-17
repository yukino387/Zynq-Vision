#ifndef CAMERA_UDP_OUTPUT_H
#define CAMERA_UDP_OUTPUT_H
#include <cstdint>
bool camera_udp_init();
void udp_poll();
bool udp_client_ready();
bool udp_preview_enabled();
bool udp_send_frame(uint32_t frame, uint32_t type, const void* data, uint32_t bytes);
struct CameraStatus {
    uint32_t magic, request, device, flags, frame;
    uint32_t capture_us, conversion_us, inference_us, transfer_us, cycle_us, errors;
    int32_t brightness;
};
bool udp_running();
void udp_pause();
bool udp_camera_only();
int udp_brightness();
void udp_send_status(const CameraStatus& status);
#endif
