cmake_minimum_required(VERSION 3.22)
project(elz_native VERSION 1.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_library(log-lib log)

# ---- VoiceProcessor shared library ----------------------------
add_library(voice_processor SHARED voice_processor.cpp)
target_link_libraries(voice_processor ${log-lib})
target_compile_options(voice_processor PRIVATE -O2 -ffast-math)

# ---- SystemController shared library -------------------------
add_library(system_controller SHARED system_controller.cpp)
target_link_libraries(system_controller ${log-lib})
target_compile_options(system_controller PRIVATE -O2)
