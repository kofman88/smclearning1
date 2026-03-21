"""
boss.py — Souls-like Boss Fight System for SMC Quest Academy.

"Рынок не прощает. Мы тоже."

Each module ends with a Boss encounter — a timed, high-stakes challenge
on a live trading scenario. Fail → drop all module souls. Win → retrieve them.
"""

import random
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter

router = APIRouter(prefix="/api/boss", tags=["boss"])

# ══════════════════════════════════════════════════════════════════════════════
# ── BOSS DEFINITIONS ─────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

BOSS_CONFIG: Dict[int, Dict[str, Any]] = {
    0: {
        "name":        "Structure Breaker",
        "module_name": "Структура рынка",
        "type":        "structure_quiz",
        "timer_secs":  120,
        "description": "5 графических паттернов. Определи BOS и CHoCH. Ошибка = рестарт.",
        "lore":        "Структура рынка — первое, что нужно понять. Structure Breaker проверяет, умеешь ли ты отличать BOS от CHoCH, и не путаешь ли ты паттерны.",
        "required_score": 0.8,
        "souls_reward":   50,
        "questions": [
            {
                "q": "На графике EURUSD H4 цена сделала Higher High, затем Lower Low, затем Lower High. Это:",
                "opts": ["BOS — смена структуры нисходящего тренда", "CHoCH — изменение характера движения", "Продолжение бычьего тренда", "Нет смены структуры"],
                "ans": 1,
                "explanation": "CHoCH (Change of Character) — первый признак смены тренда. Цена ещё не подтвердила разворот BOS."
            },
            {
                "q": "Цена нарушила предыдущий Higher High в восходящем тренде и вернулась ниже него. Это:",
                "opts": ["Confirmed BOS bullish", "False BOS — ложный прорыв", "CHoCH — начало разворота", "Продолжение тренда"],
                "ans": 1,
                "explanation": "Если цена нарушила HH и вернулась — это ложный пробой (False BOS). Для подтверждения нужно закрытие свечи."
            },
            {
                "q": "Для подтверждения BOS на понижение (bearish BOS) необходимо:",
                "opts": ["Закрытие свечи НИЖЕ предыдущего структурного минимума", "Тень свечи ниже минимума достаточно", "Объём торгов выше среднего", "Дивергенция на RSI"],
                "ans": 0,
                "explanation": "BOS подтверждается только закрытием тела/фитиля свечи ниже структурного минимума — не тенью."
            },
            {
                "q": "На M15 цена делает LL, LH, LL, LH. На H4 при этом формируется Higher High. Что важнее для торговли?",
                "opts": ["M15 структура — торгуем по LTF тренду вниз", "H4 структура — HTF главнее, ищем лонги на M15", "Они одинаково важны", "Нужен ещё D1 для ответа"],
                "ans": 1,
                "explanation": "Высший таймфрейм (HTF) доминирует. H4 показывает бычий тренд → M15 нисходящие движения — это откаты для поиска входов на лонг."
            },
            {
                "q": "После CHoCH на понижение цена сделала Higher Low. Что это значит?",
                "opts": ["BOS на повышение подтверждён", "CHoCH был ложным — структура восстановилась", "Нужно ждать следующего LL", "Это не имеет значения"],
                "ans": 1,
                "explanation": "Higher Low после CHoCH говорит о том, что медведи не смогли удержать давление. CHoCH мог быть ложным — структура тренда восстанавливается."
            },
        ]
    },
    1: {
        "name":        "Liquidity Hunter",
        "module_name": "Ликвидность",
        "type":        "liquidity_quiz",
        "timer_secs":  120,
        "description": "Определи, где стоит ликвидность. Рынок доигрывается — проверка.",
        "lore":        "Ликвидность — это то, чего хотят Smart Money. Liquidity Hunter проверяет, видишь ли ты Equal Highs/Lows, Stops и куда рынок пойдёт за ликвидностью.",
        "required_score": 0.8,
        "souls_reward":   55,
        "questions": [
            {
                "q": "На графике 5 равных максимумов (Equal Highs) на H4. Где стоит ликвидность?",
                "opts": ["Под равными минимумами — там больше стопов", "Над равными максимумами — BSL (Buy-Side Liquidity)", "Нет ликвидности в этом паттерне", "Ликвидность равномерно распределена"],
                "ans": 1,
                "explanation": "Equal Highs = магнит для цены. Над ними скоплены стопы лонг-трейдеров и ордера шорт-продавцов → Buy-Side Liquidity (BSL)."
            },
            {
                "q": "Что происходит после Liquidity Sweep (sweep равных максимумов)?",
                "opts": ["Цена продолжает рост — прорыв состоялся", "Smart Money собрали ликвидность и разворачивают рынок вниз", "Необходимо ждать подтверждения на LTF", "Ничего особенного — обычное движение"],
                "ans": 1,
                "explanation": "После sweep SM собрали ликвидность (выбили стопы) и теперь разворачивают позицию. Ищи разворотный паттерн на LTF (M5/M15)."
            },
            {
                "q": "Inducement на графике — это:",
                "opts": ["Ложный пробой структуры для сбора ликвидности", "Подтверждение тренда объёмом", "Дивергенция на MACD", "Сильный уровень поддержки"],
                "ans": 0,
                "explanation": "Inducement — приманка. Рынок делает ложное движение, чтобы выбить стопы ретейл-трейдеров и набрать позицию по лучшей цене."
            },
            {
                "q": "На каком уровне Smart Money чаще всего разворачивают цену после sweep?",
                "opts": ["На уровне 50% свечи-sweeper", "На Order Block, который спровоцировал sweep", "На уровне дневного pivot point", "На круглом числе (1.2000, 1.2500)"],
                "ans": 1,
                "explanation": "Свеча-sweeper сама по себе часто является Order Block или внутри неё находится OB/FVG — именно оттуда SM разворачивают цену."
            },
            {
                "q": "Что такое Sellside Liquidity (SSL)?",
                "opts": ["Зона продаж институциональных игроков", "Скопление стопов под минимумами (стопы лонговых позиций)", "Уровень поддержки на H1", "Область с высоким объёмом продаж"],
                "ans": 1,
                "explanation": "SSL — Buy-side liquidity снизу: стопы трейдеров, державших лонги. SM спускаются туда, чтобы выбить стопы и набрать лонг-позицию."
            },
        ]
    },
    2: {
        "name":        "OB Guardian",
        "module_name": "Ордер-блоки",
        "type":        "ob_quiz",
        "timer_secs":  120,
        "description": "Найди 3 валидных OB среди 7 зон. Тап неверной зоны = смерть.",
        "lore":        "OB Guardian охраняет знание об ордер-блоках. Он знает: не каждая консолидация — OB. Докажи, что умеешь отличать валидный блок от ловушки.",
        "required_score": 0.8,
        "souls_reward":   60,
        "questions": [
            {
                "q": "Валидный Bullish Order Block — это:",
                "opts": ["Последняя медвежья свеча перед импульсным бычьим движением", "Первая бычья свеча в тренде", "Зона высокого объёма на графике", "Свеча с минимальным телом (doji)"],
                "ans": 0,
                "explanation": "Bullish OB = последняя медвежья свеча перед сильным бычьим импульсом. SM накапливали позицию именно там."
            },
            {
                "q": "OB становится невалидным (mitigation), если:",
                "opts": ["Цена вернулась к нему и торговалась внутри него", "Прошло более 24 часов с момента формирования", "Рынок закрылся в другой сессии", "Объём торгов снизился"],
                "ans": 0,
                "explanation": "После того как цена посетила OB и SM закрыли там свои позиции — блок использован (mitigated) и теряет силу."
            },
            {
                "q": "Чем отличается Breaker Block от Order Block?",
                "opts": ["Breaker — это провальный OB, который стал уровнем на другой стороне", "Breaker более сильный и надёжный OB", "Breaker на LTF, OB на HTF", "Нет разницы — это синонимы"],
                "ans": 0,
                "explanation": "Breaker Block — это OB, который не удержал цену (цена пробила его). Теперь он работает в обратном направлении как зона сопротивления/поддержки."
            },
            {
                "q": "На каком таймфрейме лучше всего искать OB для входа?",
                "opts": ["LTF (M5, M15) — точный вход после подтверждения на HTF", "HTF (D1, W1) — только крупные блоки имеют значение", "Всегда H1 — золотой стандарт SMC", "Любой таймфрейм одинаково подходит"],
                "ans": 0,
                "explanation": "HTF (H4, D1) даёт направление и зону, LTF (M15, M5) — точный вход в OB. Top-Down анализ — основа SMC торговли."
            },
            {
                "q": "Что такое FVG внутри OB?",
                "opts": ["Дополнительное подтверждение силы блока", "Признак невалидности блока", "Случайный дисбаланс без значения", "Технический артефакт платформы"],
                "ans": 0,
                "explanation": "FVG внутри OB — High Probability зона. Дисбаланс внутри блока говорит о том, что SM действовали агрессивно. Это совпадение двух подтверждений."
            },
        ]
    },
    3: {
        "name":        "FVG Phantom",
        "module_name": "Fair Value Gap",
        "type":        "fvg_quiz",
        "timer_secs":  100,
        "description": "График мелькает 5 секунд → исчезает → разметь по памяти.",
        "lore":        "FVG Phantom прячется в дисбалансах. Он проверяет, умеешь ли ты видеть то, что другие пропускают — Fair Value Gap в реальном времени.",
        "required_score": 0.8,
        "souls_reward":   65,
        "questions": [
            {
                "q": "Fair Value Gap формируется, когда:",
                "opts": ["Есть разрыв между High свечи 1 и Low свечи 3 (нет перекрытия)", "Объём третьей свечи выше среднего", "Цена движется без коррекции 10+ свечей", "Спред между Bid и Ask увеличивается"],
                "ans": 0,
                "explanation": "FVG = 3-свечная структура: High[1] < Low[3]. Разрыв говорит о дисбалансе спроса/предложения — SM действовали агрессивно."
            },
            {
                "q": "Bullish FVG более надёжен, если находится:",
                "opts": ["В зоне дисконта (ниже 50% последнего движения)", "Выше 50% последнего движения (зона премиум)", "На уровне дневного открытия", "Рядом с круглыми числами"],
                "ans": 0,
                "explanation": "Discount zone (< 50% = Premium/Discount уровень) — область, где SM охотнее покупают. Bullish FVG там имеет больше шансов на отработку."
            },
            {
                "q": "Что происходит, когда цена возвращается в FVG?",
                "opts": ["SM закрывают дисбаланс и потенциально меняют направление", "FVG автоматически становится OB", "Гарантированный разворот тренда", "Цена обязательно пройдёт сквозь FVG"],
                "ans": 0,
                "explanation": "Цена возвращается в FVG, чтобы 'закрыть' дисбаланс. Но не всегда — FVG может полностью заполниться или отработать частично."
            },
            {
                "q": "Inversion FVG (iFVG) — это:",
                "opts": ["FVG, который был пробит и теперь работает в обратном направлении", "FVG на инвертированном (перевёрнутом) графике", "Второй по размеру FVG в серии", "FVG на форекс парах с инверсией"],
                "ans": 0,
                "explanation": "iFVG = Bullish FVG стал Bearish после пробоя, и наоборот. Это говорит о смене контроля между быками и медведями."
            },
            {
                "q": "Какой размер FVG считается 'значимым' для торговли?",
                "opts": ["Нет универсального правила — контекст важнее размера", "Минимум 20 пунктов на Forex", "Не менее 0.5% от цены актива", "Больше среднего ATR за последние 14 свечей"],
                "ans": 0,
                "explanation": "Размер FVG зависит от актива, таймфрейма и волатильности. Важнее контекст: HTF направление, OB рядом, структура рынка."
            },
        ]
    },
}


def get_boss_for_module(module_id: int) -> Optional[Dict[str, Any]]:
    """Return boss config for a module, or None if no boss defined."""
    return BOSS_CONFIG.get(module_id)


def get_all_bosses() -> List[Dict[str, Any]]:
    """Return list of all boss configs with their module IDs."""
    return [{"module_id": mid, **cfg} for mid, cfg in BOSS_CONFIG.items()]


# ══════════════════════════════════════════════════════════════════════════════
# ── BOSS ATTEMPTS STORAGE (in user state JSON) ───────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

def _get_boss_attempts(user_id: int) -> List[Dict[str, Any]]:
    from progress import get_user_state
    state = get_user_state(user_id)
    return state.setdefault("boss_attempts", [])


def record_boss_attempt(user_id: int, module_id: int, result: str,
                        accuracy: float, time_spent: int,
                        souls_at_stake: int) -> Dict[str, Any]:
    """Persist a boss attempt and return it."""
    from progress import get_user_state, save_progress
    state    = get_user_state(user_id)
    attempts = state.setdefault("boss_attempts", [])
    attempt  = {
        "module_id":    module_id,
        "boss_type":    BOSS_CONFIG.get(module_id, {}).get("type", "unknown"),
        "result":       result,       # "victory" | "death"
        "accuracy":     round(accuracy, 3),
        "time_spent":   time_spent,
        "souls_at_stake": souls_at_stake,
        "ts":           datetime.utcnow().isoformat(),
    }
    attempts.append(attempt)
    # Keep last 100 attempts per user (prevent bloat)
    state["boss_attempts"] = attempts[-100:]
    save_progress()
    return attempt


def get_bloodstains(module_id: int) -> Dict[str, Any]:
    """
    Aggregate death statistics across ALL users for a given module boss.
    Returns death_rate, avg_accuracy, total_attempts.
    """
    from progress import user_progress
    total     = 0
    deaths    = 0
    acc_total = 0.0
    acc_count = 0

    for uid, st in user_progress.items():
        for a in st.get("boss_attempts", []):
            if a.get("module_id") == module_id:
                total += 1
                if a.get("result") == "death":
                    deaths += 1
                if a.get("accuracy") is not None:
                    acc_total += a["accuracy"]
                    acc_count += 1

    death_rate   = round(deaths / total, 3) if total > 0 else None
    avg_accuracy = round(acc_total / acc_count, 3) if acc_count > 0 else None
    boss         = BOSS_CONFIG.get(module_id, {})
    return {
        "module_id":     module_id,
        "boss_name":     boss.get("name", "Unknown Boss"),
        "total_attempts": total,
        "death_rate":    death_rate,
        "death_pct":     round(death_rate * 100) if death_rate is not None else None,
        "avg_accuracy":  avg_accuracy,
        "avg_accuracy_pct": round(avg_accuracy * 100) if avg_accuracy is not None else None,
    }


# ══════════════════════════════════════════════════════════════════════════════
# ── API ENDPOINTS ─────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

from pydantic import BaseModel


class BossStartRequest(BaseModel):
    user_id: int


class BossSubmitRequest(BaseModel):
    user_id: int
    correct: int
    total:   int
    time_spent_seconds: int


@router.get("/{module_id}/config")
async def boss_config(module_id: int):
    """Return boss configuration for a module (without correct answers)."""
    boss = get_boss_for_module(module_id)
    if not boss:
        return {"ok": False, "reason": "no_boss_for_module"}

    # Strip correct answers — send questions with shuffled options
    questions = []
    for q in boss.get("questions", []):
        opts   = list(enumerate(q["opts"]))
        random.shuffle(opts)
        orig_to_new = {orig: new for new, (orig, _) in enumerate(opts)}
        questions.append({
            "question":      q["q"],
            "options":       [o for _, o in opts],
            "correct_index": orig_to_new[q["ans"]],
            "explanation":   q.get("explanation", ""),
        })

    return {
        "ok":          True,
        "module_id":   module_id,
        "name":        boss["name"],
        "module_name": boss["module_name"],
        "type":        boss["type"],
        "timer_secs":  boss["timer_secs"],
        "description": boss["description"],
        "lore":        boss["lore"],
        "required_score": boss["required_score"],
        "souls_reward":   boss["souls_reward"],
        "questions":   questions,
    }


@router.post("/{module_id}/start")
async def boss_start(module_id: int, req: BossStartRequest):
    """
    Start a boss fight. Returns boss config with questions.
    Records that the fight has begun (for tracking incomplete attempts).
    """
    from progress import get_user_state, save_progress, get_souls_state
    boss = get_boss_for_module(module_id)
    if not boss:
        return {"ok": False, "reason": "no_boss_for_module"}

    state       = get_user_state(req.user_id)
    souls_state = get_souls_state(req.user_id)

    # Shuffle questions for this attempt
    questions = []
    for q in boss.get("questions", []):
        opts = list(enumerate(q["opts"]))
        random.shuffle(opts)
        orig_to_new = {orig: new for new, (orig, _) in enumerate(opts)}
        questions.append({
            "question":      q["q"],
            "options":       [o for _, o in opts],
            "correct_index": orig_to_new[q["ans"]],
            "explanation":   q.get("explanation", ""),
        })

    return {
        "ok":            True,
        "module_id":     module_id,
        "name":          boss["name"],
        "lore":          boss["lore"],
        "timer_secs":    boss["timer_secs"],
        "required_score": boss["required_score"],
        "souls_at_stake": souls_state.get("souls_module_earned", 0),
        "questions":     questions,
    }


@router.post("/{module_id}/submit")
async def boss_submit(module_id: int, req: BossSubmitRequest):
    """
    Submit boss fight result (correct answers out of total).
    Handles souls drop on death or souls reward on victory.
    """
    from progress import (
        get_user_state, save_progress, award_badge,
        add_souls, drop_souls, retrieve_souls, get_souls_state,
    )

    boss = get_boss_for_module(module_id)
    if not boss:
        return {"ok": False, "reason": "no_boss_for_module"}

    accuracy = req.correct / req.total if req.total > 0 else 0
    passed   = accuracy >= boss["required_score"]
    result   = "victory" if passed else "death"

    state    = get_user_state(req.user_id)
    souls_st = get_souls_state(req.user_id)

    attempt = record_boss_attempt(
        user_id       = req.user_id,
        module_id     = module_id,
        result        = result,
        accuracy      = accuracy,
        time_spent    = req.time_spent_seconds,
        souls_at_stake= souls_st.get("souls", 0),
    )

    response: Dict[str, Any] = {
        "ok":         True,
        "result":     result,
        "accuracy":   round(accuracy * 100),
        "correct":    req.correct,
        "total":      req.total,
        "module_id":  module_id,
        "boss_name":  boss["name"],
    }

    if passed:
        # Victory → award boss souls + retrieve dropped souls if any
        reward = add_souls(req.user_id, boss["souls_reward"], source="boss_victory")
        retrieved = retrieve_souls(req.user_id)  # recover dropped souls if any

        # Award badge for beating boss
        badge_id = f"boss_{module_id}_clear"
        award_badge(req.user_id, badge_id)

        # Check flawless (no deaths in this module)
        deaths_this_module = sum(
            1 for a in state.get("boss_attempts", [])
            if a.get("module_id") == module_id and a.get("result") == "death"
        )
        if deaths_this_module == 0:
            award_badge(req.user_id, f"boss_{module_id}_flawless")

        response.update({
            "souls_earned":   reward["delta"],
            "total_souls":    reward["total"],
            "souls_retrieved": retrieved.get("recovered", 0) if retrieved.get("ok") else 0,
            "message":        f"Босс {boss['name']} повержен! +{reward['delta']} ⚡",
        })
    else:
        # Death → drop all module souls
        dropped = drop_souls(req.user_id)
        # Enrage homunculus on boss death (x2 tap mult for 10 min)
        try:
            from progress import homunculus_enrage
            homunculus_enrage(req.user_id)
        except Exception as _he:
            pass
        response.update({
            "dropped_souls":  dropped["dropped"],
            "can_retrieve":   dropped["can_retrieve"],
            "message":        f"Ликвидирован {boss['name']}. Рынок забрал {dropped['dropped']} ⚡.",
            "homunculus_enraged": True,
        })

    return response


@router.get("/{module_id}/bloodstains")
async def boss_bloodstains(module_id: int):
    """Return aggregate death statistics for a module boss."""
    data = get_bloodstains(module_id)
    return {"ok": True, **data}


@router.get("/all/configs")
async def all_boss_configs():
    """Return all boss configurations (no answers)."""
    result = []
    for module_id, boss in BOSS_CONFIG.items():
        result.append({
            "module_id":   module_id,
            "name":        boss["name"],
            "module_name": boss["module_name"],
            "type":        boss["type"],
            "timer_secs":  boss["timer_secs"],
            "description": boss["description"],
            "souls_reward": boss["souls_reward"],
        })
    return {"ok": True, "bosses": result}
