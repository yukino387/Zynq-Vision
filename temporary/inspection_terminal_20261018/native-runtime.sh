#!/bin/sh
set -eu
task=/workspace/temporary/inspection_terminal_20261018
native=/workspace/camera/terminal
arm-linux-gnueabihf-g++ -std=c++17 -O2 -D_FILE_OFFSET_BITS=64 -I"$native" -I"$native/build/deps/json/single_include" -I"$native/build/deps/httplib" "$native/engine.cpp" "$native/core.cpp" "$task/hardware_fixture.cpp" -pthread -o "$task/vision-engine-fixture"
python3 "$task/engine-runtime.py"
sh "$task/panel-runtime.sh"
