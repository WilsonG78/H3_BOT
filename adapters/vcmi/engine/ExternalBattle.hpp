// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include "Global.h"
#include "CCallback.h"
#include "lib/CStack.h"

VCMI_LIB_USING_NAMESPACE

namespace h3
{
// Adapter-only controller. It never evaluates or chooses an action.
class ExternalBattleController
{
public:
    static bool enabled();
    static bool controls();
    static void observe(CBattleCallback & callback, const BattleID & battle_id,
                        const char * event, int winner = -1);
    // True means the external controller owns this decision, even on error.
    static bool decide(CBattleCallback & callback, const BattleID & battle_id, const CStack * active);
};
}
