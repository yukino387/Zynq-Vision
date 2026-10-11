#pragma once
#include <cstddef>
#include <cstdint>
#include <cassert>
#define Xil_AssertVoid(condition) assert(condition)
typedef std::intptr_t INTPTR;
typedef std::uintptr_t UINTPTR;
void Xil_DCacheFlushRange(INTPTR address, std::size_t bytes);
void Xil_DCacheInvalidateRange(INTPTR address, std::size_t bytes);
