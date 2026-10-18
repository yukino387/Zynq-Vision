#include "udp_output.h"
#include "int8/model_store.h"
#include "firmware_ota.h"
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
    if (packet && packet->tot_len >= 20 && packet->tot_len <= 1420) {
        uint8_t bytes[1420];
        pbuf_copy_partial(packet,bytes,packet->tot_len,0);
        uint32_t header[5];std::memcpy(header,bytes,20);
        // BEGIN carries the total image size in the size field with no payload;
        // every other operation's size field equals the payload length.
        if(header[0]==FW_REQ_MAGIC && (header[4]==packet->tot_len-20 ||
            (header[2]==FW_OP_BEGIN && packet->tot_len==20))) {
            const bool owner=peer_port==port && ip_addr_cmp(&peer,address);
            FirmwareReply reply={};
            if(header[2]==FW_OP_INFO || header[2]==FW_OP_LIST || owner)
                reply=firmware_request(header[1],header[2],header[3],bytes+20,header[4]);
            else {
                reply.magic=FW_REPLY_MAGIC;reply.request=header[1];
                reply.result=FW_RESULT_BUSY;reply.max_attempts=FW_MAX_ATTEMPTS;
                reply.crc32=fw_crc32(&reply,offsetof(FirmwareReply,crc32));
            }
            pbuf* response=pbuf_alloc(PBUF_TRANSPORT,sizeof(reply),PBUF_RAM);
            if(response){std::memcpy(response->payload,&reply,sizeof(reply));udp_sendto(socket,response,address,port);pbuf_free(response);}
        } else if(header[0]==0x314c444d && header[4]==packet->tot_len-20) {
            const bool owner=peer_port==port && ip_addr_cmp(&peer,address);
            ModelReply reply={};
            if(header[2]==0 || owner)reply=model_request(header[1],header[2],header[3],bytes+20,header[4]);
            else {reply.magic=0x3152444d;reply.request=header[1];reply.result=2;}
            pbuf* response=pbuf_alloc(PBUF_TRANSPORT,sizeof(reply),PBUF_RAM);
            if(response){std::memcpy(response->payload,&reply,sizeof(reply));udp_sendto(socket,response,address,port);pbuf_free(response);}
        }
    } else if (packet && packet->tot_len == 1) {
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
                if (command[2] == 2 && !firmware_busy()) running = command[3] != 0;
                if (command[2] == 3 && !firmware_busy()) camera_only = command[3] != 0;
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
void udp_pause() { running=false; }
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
        // Five little-endian uint32 values followed by tensor or RGB565 bytes.
        const uint32_t header[] = {0x314f4c59, frame, type, bytes, offset};
        std::memcpy(packet->payload, header, sizeof(header));
        std::memcpy(static_cast<uint8_t*>(packet->payload) + sizeof(header), source + offset, count);
        err_t result = udp_sendto(socket, packet, &peer, peer_port);
        if (result == ERR_MEM) {
            XTime begin, now;
            XTime_GetTime(&begin);
            do {
                udp_poll();
                result = udp_sendto(socket, packet, &peer, peer_port);
                XTime_GetTime(&now);
            } while (result == ERR_MEM && now - begin < (COUNTS_PER_SECOND) / 200);
        }
        pbuf_free(packet);
        if (result != ERR_OK) return false;
        udp_poll();
    }
    return true;
}
