#pragma once

#include <cstdint>
#include <string>
#include <nlohmann/json.hpp>

namespace h3
{
// One loopback connection per decision. All messages are bounded NDJSON frames.
// The Python service must return an action offered in the observation.
nlohmann::json request_action(const nlohmann::json & observation,
                              std::uint16_t port, int timeout_seconds = 30);
// Publish without waiting for a policy or submitting any action.
void send_observation(const nlohmann::json & observation,
                      std::uint16_t port, int timeout_seconds = 1);
}
