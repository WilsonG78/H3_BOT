// SPDX-License-Identifier: GPL-2.0-or-later
#include "ExternalBattle.hpp"
#include "h3/bridge.hpp"
#include "lib/battle/BattleInfo.h"
#include "lib/battle/BattleAction.h"
#include "lib/battle/CObstacleInstance.h"
#include "lib/CCreatureHandler.h"
#include <atomic>
#include <chrono>
#include <condition_variable>
#include <cstdlib>
#include <deque>
#include <iostream>
#include <map>
#include <thread>

namespace h3
{
using Json = nlohmann::json;
namespace
{
std::string mode()
{
    const char * value = std::getenv("H3_BOT_MODE");
    return value ? value : "off";
}
std::uint16_t port()
{
    const char * value = std::getenv("H3_BOT_PORT");
    const std::string text = value ? value : "8765";
    std::size_t used = 0;
    auto number = std::stoul(text, &used);
    if(used != text.size() || number < 1 || number > 65535)
        throw std::runtime_error("H3_BOT_PORT must be in range 1..65535");
    return static_cast<std::uint16_t>(number);
}

// Never perform network I/O or wait for Python on the manual-game callback.
// Copy engine data before enqueueing: the worker owns no VCMI pointers.
class Publisher
{
    std::mutex mutex;
    std::condition_variable ready;
    std::deque<Json> pending;
    bool stopping = false;
    std::thread worker;
public:
    Publisher() : worker([this] { run(); }) {}
    ~Publisher()
    {
        { std::lock_guard<std::mutex> lock(mutex); stopping = true; pending.clear(); }
        ready.notify_all();
        worker.join();
    }
    void enqueue(Json observation)
    {
        { std::lock_guard<std::mutex> lock(mutex);
          if(pending.size() == 64)
          {
              pending.pop_front();
              std::cerr << "H3 observer: queue full; oldest snapshot dropped\n";
          }
          pending.push_back(std::move(observation)); }
        ready.notify_one();
    }
    void run()
    {
        while(true)
        {
            Json observation;
            {
                std::unique_lock<std::mutex> lock(mutex);
                ready.wait(lock, [this] { return stopping || !pending.empty(); });
                if(stopping) return;
                observation = std::move(pending.front());
                pending.pop_front();
            }
            try { send_observation(observation, port()); }
            catch(const std::exception & error)
            { std::cerr << "H3 observer transport error: " << error.what() << '\n'; }
        }
    }
};
Publisher & publisher() { static Publisher instance; return instance; }

Json snapshot(CBattleCallback & callback, const BattleID & battle_id,
              const CStack * active, const std::string & event, int winner = -1)
{
    auto info = callback.getBattle(battle_id);
    if(!info || !info->getBattle()) throw std::runtime_error("Battle state is unavailable");
        static std::atomic<std::uint64_t> sequence{0};
        static const auto session = std::to_string(std::chrono::system_clock::now().time_since_epoch().count());
        const auto revision = ++sequence;
        auto * state = dynamic_cast<const BattleInfo *>(info->getBattle());
        Json observation = {
            {"type", "observation"}, {"schema_version", 2},
            {"battle_id", session + ":" + std::to_string(battle_id.getNum())},
            {"revision", revision}, {"decision_id", std::to_string(revision)},
            {"round", state ? Json(state->round) : Json(nullptr)},
            {"viewer_side", static_cast<int>(info->battleGetMySide())},
            {"active_stack_id", active ? Json(active->unitId()) : Json(nullptr)},
            {"engine", "VCMI 1.6.5"},
            {"mode", mode()}, {"event", event},
            {"status", event == "battle_ended" ? "terminated" : "running"},
            {"winner_side", winner >= 0 ? Json(winner) : Json(nullptr)}, {"error", nullptr},
            {"capabilities", {"open_field", "basic_stack_actions"}},
            {"stacks", Json::array()}, {"legal_actions", Json::array()},
            {"battlefield", {{"width", GameConstants::BFIELD_WIDTH},
                             {"height", GameConstants::BFIELD_HEIGHT},
                             {"hex_encoding", "vcmi_row_major"}, {"obstacles", Json::array()}}}
        };
        for(const auto * unit : info->battleGetUnitsIf([](const battle::Unit *) { return true; }))
        {
            Json occupied = Json::array();
            for(const auto & hex : unit->getHexes()) occupied.push_back(hex.toInt());
            const auto * stack = dynamic_cast<const CStack *>(unit);
            Json entry = {
                {"id", unit->unitId()}, {"creature_id", unit->unitType()->getJsonKey()},
                {"side_id", static_cast<int>(unit->unitSide())},
                {"owner", info->battleGetOwner(unit).getNum()},
                {"alive", unit->alive()}, {"ghost", unit->isGhost()},
                {"count", unit->getCount()}, {"top_unit_hp", unit->getFirstHPleft()},
                {"max_unit_hp", unit->getMaxHealth()}, {"total_hp", unit->getAvailableHealth()},
                {"position", unit->getPosition().toInt()}, {"occupied_hexes", occupied},
                {"stats", {{"attack_melee", unit->getAttack(false)}, {"attack_ranged", unit->getAttack(true)},
                    {"defense_melee", unit->getDefense(false)}, {"defense_ranged", unit->getDefense(true)},
                    {"damage_min_melee", unit->getMinDamage(false)}, {"damage_max_melee", unit->getMaxDamage(false)},
                    {"damage_min_ranged", unit->getMinDamage(true)}, {"damage_max_ranged", unit->getMaxDamage(true)},
                    {"movement_range", unit->getMovementRange()}}},
                {"turn_status", {{"waited", unit->waited()}, {"moved", unit->moved()}, {"defended", unit->defended()}}},
                {"shots", stack ? Json(stack->shots.available()) : Json(nullptr)}
            };
            observation["stacks"].push_back(entry);
        }
        for(const auto & obstacle : info->battleGetAllObstacles(info->battleGetMySide()))
        {
            Json blocked = Json::array();
            for(const auto & hex : obstacle->getBlockedTiles()) blocked.push_back(hex.toInt());
            observation["battlefield"]["obstacles"].push_back({{"id", obstacle->uniqueID}, {"blocked_hexes", blocked}});
        }
        return observation;
}
}

bool ExternalBattleController::enabled()
{
    return mode() == "observe" || mode() == "control";
}
bool ExternalBattleController::controls()
{
    return mode() == "control";
}
void ExternalBattleController::observe(CBattleCallback & callback, const BattleID & battle_id,
                                      const char * event, int winner)
{
    if(!enabled()) return;
    try
    {
        auto info = callback.getBattle(battle_id);
        const auto * active = info ? dynamic_cast<const CStack *>(info->battleActiveUnit()) : nullptr;
        publisher().enqueue(snapshot(callback, battle_id, active, event, winner));
    }
    catch(const std::exception & error)
    { std::cerr << "H3 observer extraction error: " << error.what() << '\n'; }
}

bool ExternalBattleController::decide(CBattleCallback & callback, const BattleID & battle_id, const CStack * active)
{
    if(!controls()) return false;
    Json observation;
    try
    {
        observation = snapshot(callback, battle_id, active, "decision");
        auto info = callback.getBattle(battle_id);
        if(!active || info->battleTacticDist() || info->battleGetDefendedTown() || active->isTurret() ||
           active->hasBonusOfType(BonusType::SIEGE_WEAPON))
            throw std::runtime_error("Unsupported control scenario; no action submitted");
        std::map<std::string, BattleAction> actions;
        auto offer = [&](Json description, const BattleAction & action)
        {
            auto id = std::to_string(actions.size());
            description["id"] = id;
            description["actor_stack_id"] = active->unitId();
            actions.emplace(id, action);
            observation["legal_actions"].push_back(description);
        };
        offer({{"type", "defend"}}, BattleAction::makeDefend(active));
        if(!active->waited()) offer({{"type", "wait"}}, BattleAction::makeWait(active));
        const auto destinations = info->battleGetAvailableHexes(active, true);
        for(const auto & destination : destinations)
            if(destination != active->getPosition())
                offer({{"type", "move"}, {"destination_hex", destination.toInt()}}, BattleAction::makeMove(active, destination));
        for(const auto * target : info->battleAliveUnits())
        {
            if(!info->battleMatchOwner(active, target, false)) continue;
            if(info->battleCanShoot(active, target->getPosition()))
                offer({{"type", "shoot"}, {"target_stack_id", target->unitId()}}, BattleAction::makeShotAttack(active, target));
            for(const auto & destination : destinations)
                if(info->battleCanAttack(active, target, destination))
                    for(const auto & target_hex : target->getHexes())
                        if(active->getSurroundingHexes(destination).contains(target_hex))
                            offer({{"type", "melee_attack"}, {"target_stack_id", target->unitId()},
                                   {"target_hex", target_hex.toInt()}, {"destination_hex", destination.toInt()}},
                                  BattleAction::makeMeleeAttack(active, target_hex, destination));
        }
        const auto selected = request_action(observation, port());
        callback.battleMakeUnitAction(battle_id, actions.at(selected.at("id").get<std::string>()));
    }
    catch(const std::exception & error)
    {
        // Fail closed. Never invent a move, invoke a built-in policy, or defend.
        std::cerr << "H3 control environment error: " << error.what() << "; NO action submitted; episode halted\n";
        if(!observation.is_null())
        {
            observation["event"] = "environment_error";
            observation["status"] = "error";
            observation["error"] = error.what();
            observation["legal_actions"] = Json::array();
            publisher().enqueue(observation);
        }
    }
    return true;
}
}
