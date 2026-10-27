#include "h3/bridge.hpp"
#include <fstream>
#include <iostream>

int main(int argc, char ** argv)
{
    if(argc != 3 && argc != 4) return 2;
    try
    {
        std::ifstream stream(argv[2]);
        nlohmann::json observation;
        stream >> observation;
        if(argc == 4 && std::string(argv[3]) == "observe")
        {
            h3::send_observation(observation, static_cast<std::uint16_t>(std::stoi(argv[1])), 2);
            std::cout << "published\n";
            return 0;
        }
        std::cout << h3::request_action(observation, static_cast<std::uint16_t>(std::stoi(argv[1])), 2).dump() << '\n';
        return 0;
    }
    catch(const std::exception & error)
    {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
