#pragma once
#include <stdint.h>
#include "firmware_layout.h"

FirmwareReply firmware_request(uint32_t request, uint32_t operation,
                               uint32_t offset, const uint8_t* data,
                               uint32_t size);
void firmware_init();
void firmware_service();
void firmware_watchdog_kick();
bool firmware_busy();
bool firmware_trial_pending();
void firmware_confirm_ok();
void firmware_confirm_fail();
const char* firmware_version();
uint32_t firmware_running_slot();
