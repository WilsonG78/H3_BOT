if(POLICY CMP0135)
    cmake_policy(SET CMP0135 NEW)
endif()
include(FetchContent)
FetchContent_Declare(json
    URL https://github.com/nlohmann/json/releases/download/v3.11.3/json.tar.xz
    URL_HASH SHA256=d6c65aca6b1ed68e7a182f4757257b107ae403032760ed6ef121c9d55e81757d
)
FetchContent_MakeAvailable(json)
find_package(Threads REQUIRED)
add_library(h3_bridge STATIC src/bridge.cpp)
target_include_directories(h3_bridge PUBLIC include)
target_link_libraries(h3_bridge PUBLIC nlohmann_json::nlohmann_json Threads::Threads)
target_compile_features(h3_bridge PUBLIC cxx_std_17)
set_target_properties(h3_bridge PROPERTIES POSITION_INDEPENDENT_CODE ON)
if(WIN32)
    target_link_libraries(h3_bridge PRIVATE ws2_32)
endif()

option(H3_BUILD_TEST_TOOLS "Build the standalone bridge integration probe" OFF)
if(H3_BUILD_TEST_TOOLS)
    add_executable(h3_bridge_probe ../../tests/native/bridge_probe.cpp)
    target_link_libraries(h3_bridge_probe PRIVATE h3_bridge)
endif()
