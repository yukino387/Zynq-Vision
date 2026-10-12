#include "udp_output.h"
extern "C" {
#include "lwip/init.h"
#include "lwip/udp.h"
#include "netif/etharp.h"
#include "netif/xadapter.h"
#include "xil_exception.h"
#include "xparameters.h"
#include "xiltimer.h"
#include "sleep.h"
}
#include <cstring>

static netif ethernet;
static udp_pcb* socket;
static ip_addr_t peer;
static uint16_t peer_port;
static bool preview;
static XTime arp_time;
static bool running = true;
static bool camera_only;
static int brightness;
static CameraStatus latest_status = {0x31545343, 0, 0x7020, 0, 0, 0, 0, 0, 0, 0, 0, 0};

static void send_status(const ip_addr_t* address, u16_t port, uint32_t request) {
    CameraStatus status = latest_status;
    status.request = request;
    status.flags = (running ? 1U : 0U) | (camera_only ? 2U : 0U) | (preview ? 4U : 0U);
    pbuf* packet = pbuf_alloc(PBUF_TRANSPORT, sizeof(status), PBUF_RAM);
    if (!packet) return;
    std::memcpy(packet->payload, &status, sizeof(status));
    udp_sendto(socket, packet, address, port);
    pbuf_free(packet);
}

static void receive(void*, udp_pcb*, pbuf* packet, const ip_addr_t* address, u16_t port) {
    uint8_t request = 0;
    if (packet && packet->tot_len == 1) {
        pbuf_copy_partial(packet, &request, 1, 0);
        if (request <= 1) {
            peer = *address;
            peer_port = port;
            preview = request == 1;
        }
    } else if (packet && packet->tot_len == 16) {
        uint32_t command[4];
        pbuf_copy_partial(packet, command, sizeof(command), 0);
        if (command[0] == 0x31434e43 && command[2] <= 4) {
            const bool owner = peer_port == port && ip_addr_cmp(&peer, address);
            if (command[2] == 1) {
                peer = *address;
                peer_port = port;
                preview = true;
                running = true;
            } else if (owner) {
                if (command[2] == 2) running = command[3] != 0;
                if (command[2] == 3) camera_only = command[3] != 0;
                if (command[2] == 4 && static_cast<int32_t>(command[3]) >= -4 &&
                    static_cast<int32_t>(command[3]) <= 4) brightness = static_cast<int32_t>(command[3]);
            }
            send_status(address, port, command[1]);
        }
    }
    if (packet) pbuf_free(packet);
}

bool camera_udp_init() {
    ip_addr_t address, mask, gateway;
    IP4_ADDR(&address, 169, 254, 140, 110);
    IP4_ADDR(&mask, 255, 255, 0, 0);
    IP4_ADDR(&gateway, 0, 0, 0, 0);
    unsigned char mac[] = {0x02, 0x00, 0x00, 0x00, 0x70, 0x20};
    lwip_init();
    if (!xemac_add(&ethernet, &address, &mask, &gateway, mac, XPAR_XEMACPS_0_BASEADDR)) return false;
    netif_set_default(&ethernet);
    netif_set_up(&ethernet);
    Xil_ExceptionEnable();
    socket = udp_new();
    if (!socket || udp_bind(socket, IP_ADDR_ANY, 5001) != ERR_OK) return false;
    udp_recv(socket, receive, nullptr);
    XTime_GetTime(&arp_time);
    return true;
}

void udp_poll() {
    xemacif_input(&ethernet);
    XTime now;
    XTime_GetTime(&now);
    if (now - arp_time >= 5ULL * COUNTS_PER_SECOND) {
        etharp_tmr();
        arp_time = now;
    }
}
bool udp_client_ready() { return peer_port != 0; }
bool udp_preview_enabled() { return preview; }
bool udp_running() { return running; }
bool udp_camera_only() { return camera_only; }
int udp_brightness() { return brightness; }
void udp_send_status(const CameraStatus& status) {
    latest_status = status;
    if (peer_port) send_status(&peer, peer_port, 0);
}

bool udp_send_frame(uint32_t frame, uint32_t type, const void* data, uint32_t bytes) {
    const uint8_t* source = static_cast<const uint8_t*>(data);
    for (uint32_t offset = 0; offset < bytes; offset += 1400) {
        const uint32_t count = bytes - offset < 1400 ? bytes - offset : 1400;
        pbuf* packet = pbuf_alloc(PBUF_TRANSPORT, 20 + count, PBUF_RAM);
        if (!packet) return false;
        // Five little-endian uint32 values; payload is little-endian int16/RGB565.
        const uint32_t header[] = {0x314f4c59, frame, type, bytes, offset};
        std::memcpy(packet->payload, header, sizeof(header));
        std::memcpy(static_cast<uint8_t*>(packet->payload) + sizeof(header), source + offset, count);
        const err_t result = udp_sendto(socket, packet, &peer, peer_port);
        pbuf_free(packet);
        if (result != ERR_OK) return false;
        udp_poll();
    }
    return true;
}
