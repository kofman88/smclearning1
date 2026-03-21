"""
catalyst.py — Механика «Нестабильный Изотоп / Катализатор Распада»

Психологическая модель (почему это работает):
- Потеря душ от дренажа = немедленная причина зайти в приложение
- Статус Катализатора = социальный статус, виден всем
- Попытки атаки = дефицитный ресурс, восполняется ежедневно
- Нестабильный Изотоп = эксклюзивная награда за обучение (нельзя купить)
- Буфер под риском = потенциальная потеря → покупка страховки = монетизация

Дренаж: 0.01 душ/ЧАС (не в минуту!) с онлайн-пользователей.
Попытки: восстанавливаются в 00:00 UTC. Количество = уровень игрока.
Продолжительность: 24 часа. Выживание → буфер × 1.5.
"""

from __future__ import annotations
import json, logging, os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional
from fastapi import APIRouter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/catalyst", tags=["catalyst"])

_data_dir = Path(os.getenv("DATA_DIR", "."))
CATALYST_FILE = _data_dir / "catalyst_state.json"

_S: Dict[str, Any] = {
    "active": False,
    "user_id": None,
    "username": "",
    "level": 1,
    "started_at": None,
    "expires_at": None,
    "hp": 0,
    "max_hp": 0,
    "drained_secure": 0.0,   # 10%: уже у катализатора, не теряется
    "drained_buffer": 0.0,   # 90%: под риском, теряется при свержении
    "last_drain_at": None,
    "records": [],            # топ-10 по duration_minutes
    "consecutive_wins": 0,    # серия побед → прогрессивный бонус
}

def _save():
    try:
        CATALYST_FILE.write_text(json.dumps(_S, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        logger.error("catalyst save: %r", e)

def _load():
    if CATALYST_FILE.exists():
        try:
            _S.update(json.loads(CATALYST_FILE.read_text(encoding="utf-8")))
            logger.info("Catalyst loaded: active=%s user=%s", _S["active"], _S.get("username"))
        except Exception as e:
            logger.error("catalyst load: %r", e)

_load()


def get_status() -> Dict[str, Any]:
    now = datetime.utcnow()
    out = dict(_S)
    if _S["active"] and _S.get("expires_at"):
        try:
            exp = datetime.fromisoformat(_S["expires_at"])
            secs = max(0, (exp - now).total_seconds())
            out["hours_left"] = round(secs / 3600, 1)
            out["minutes_left"] = int(secs / 60)
        except Exception:
            out["hours_left"] = 0.0
            out["minutes_left"] = 0
    else:
        out["hours_left"] = 0.0
        out["minutes_left"] = 0
    out["hp_pct"] = round(_S["hp"] / _S["max_hp"] * 100) if _S.get("max_hp", 0) > 0 else 0
    out["total_drained"] = round(_S.get("drained_secure", 0) + _S.get("drained_buffer", 0), 2)
    return out


def activate(user_id: int, username: str, level: int, up: dict) -> Dict[str, Any]:
    """Активировать статус Катализатора. Требует Нестабильный Изотоп."""
    if _S["active"]:
        return {"ok": False, "error": "already_active",
                "status": get_status(), "message": "Катализатор уже активен."}

    st = up.get(user_id, {})
    isotopes = st.get("unstable_isotopes", 0)
    if isotopes < 1:
        return {"ok": False, "error": "no_isotopes",
                "message": "Нужен Нестабильный Изотоп.\nПолучи за победу над Боссом или топ-3 Daily Challenge.",
                "isotopes": 0}

    st["unstable_isotopes"] = max(0, isotopes - 1)
    now = datetime.utcnow()
    max_hp = level * 50

    _S.update({
        "active": True, "user_id": user_id, "username": username, "level": level,
        "started_at": now.isoformat(),
        "expires_at": (now + timedelta(hours=24)).isoformat(),
        "hp": max_hp, "max_hp": max_hp,
        "drained_secure": 0.0, "drained_buffer": 0.0,
        "last_drain_at": now.isoformat(),
    })
    _save()
    return {
        "ok": True,
        "message": f"⚗️ ЦЕПНАЯ РЕАКЦИЯ НАЧАЛАСЬ!\nHP: {max_hp}. У тебя 24 часа.",
        "status": get_status(),
        "isotopes_left": st.get("unstable_isotopes", 0),
    }


def attack(attacker_id: int, attacker_name: str, attacker_level: int,
           up: dict) -> Dict[str, Any]:
    """Атака Катализатора. Тратит попытку."""
    if not _S["active"]:
        return {"ok": False, "error": "no_catalyst"}
    if _S["user_id"] == attacker_id:
        return {"ok": False, "error": "self", "message": "Нельзя атаковать себя."}

    # Попытки
    st = up.setdefault(attacker_id, {})
    today = datetime.utcnow().strftime("%Y-%m-%d")
    if st.get("atk_date") != today:
        st["atk_date"] = today
        st["atk_left"] = attacker_level
    if st.get("atk_left", 0) <= 0:
        return {"ok": False, "error": "no_attempts",
                "message": "Попытки на сегодня исчерпаны.\nВосстановятся в 00:00 UTC.",
                "attempts_left": 0}

    st["atk_left"] -= 1
    dmg = attacker_level
    _S["hp"] = max(0, _S["hp"] - dmg)

    res = {
        "ok": True, "damage": dmg,
        "hp_left": _S["hp"], "max_hp": _S["max_hp"],
        "hp_pct": round(_S["hp"] / _S["max_hp"] * 100) if _S["max_hp"] > 0 else 0,
        "attempts_left": st["atk_left"],
        "slain": False,
    }

    if _S["hp"] <= 0:
        # Свержение — нейтрализатор получает 30% буфера + Изотоп
        bonus = round(_S["drained_buffer"] * 0.30, 2)
        st["souls"] = round(st.get("souls", 0) + bonus, 2)
        st["unstable_isotopes"] = st.get("unstable_isotopes", 0) + 1
        st["neutralizations"] = st.get("neutralizations", 0) + 1

        res.update({
            "slain": True,
            "bonus_souls": bonus,
            "isotope_received": True,
            "message": f"💥 НЕЙТРАЛИЗОВАНО!\n+{bonus} душ и Изотоп тебе!",
        })
        _finish("neutralized", up, neutralizer_id=attacker_id, neutralizer_name=attacker_name)
    else:
        pct = round(_S["hp"] / _S["max_hp"] * 100)
        res["message"] = f"⚡ -{dmg} HP. Осталось {_S['hp']}/{_S['max_hp']} ({pct}%)"
        _save()

    return res


def drain_hourly(up: dict) -> Dict[str, Any]:
    """
    Дренаж раз в ЧАС (не в минуту!).
    0.01 душ с каждого онлайн-пользователя (активен < 30 минут).
    10% → secure (гарантировано, уже у катализатора).
    90% → buffer (рискованно, теряется при свержении).
    """
    if not _S["active"]:
        return {"drained": 0, "victims": 0}

    now = datetime.utcnow()

    # Проверка 24ч экспирации
    if _S.get("expires_at"):
        try:
            if now > datetime.fromisoformat(_S["expires_at"]):
                return _stabilize(up)
        except Exception:
            pass

    cat_id = _S["user_id"]
    total, victims = 0.0, 0
    DRAIN = 0.01

    for uid, st in up.items():
        if uid == cat_id:
            continue
        lo = st.get("last_online", "")
        if not lo:
            continue
        try:
            if (now - datetime.fromisoformat(lo)).total_seconds() <= 1800:
                # Проверяем щит
                shield_until = st.get("catalyst_shield_until", "")
                if shield_until:
                    try:
                        if datetime.fromisoformat(shield_until) > now:
                            continue  # защищён — пропускаем дренаж
                    except Exception:
                        pass
                souls = st.get("souls", 0)
                actual = min(float(souls), DRAIN)
                if actual > 0:
                    st["souls"] = round(souls - actual, 4)
                    total += actual
                    victims += 1
        except Exception:
            continue

    if total > 0:
        sec = round(total * 0.10, 4)
        buf = round(total * 0.90, 4)
        cat_st = up.get(cat_id)
        if cat_st is not None:
            cat_st["souls"] = round(cat_st.get("souls", 0) + sec, 4)
        _S["drained_secure"] = round(_S.get("drained_secure", 0) + sec, 4)
        _S["drained_buffer"] = round(_S.get("drained_buffer", 0) + buf, 4)
        _S["last_drain_at"] = now.isoformat()
        _save()

    return {"drained": round(total, 4), "victims": victims}


def _stabilize(up: dict) -> Dict[str, Any]:
    """24ч без свержения — реакция стабилизировалась. Буфер × 1.5."""
    cat_id = _S["user_id"]
    bonus_mult = 1.5 + (_S.get("consecutive_wins", 0) * 0.1)  # прогрессивный бонус за серию
    bonus = round(_S["drained_buffer"] * bonus_mult, 2)

    cat_st = up.get(cat_id)
    if cat_st:
        cat_st["souls"] = round(cat_st.get("souls", 0) + bonus, 2)
        cat_st["catalyst_wins"] = cat_st.get("catalyst_wins", 0) + 1
        cat_st.setdefault("badges", [])
        if "stable_isotope" not in cat_st["badges"]:
            cat_st["badges"].append("stable_isotope")

    _S["consecutive_wins"] = _S.get("consecutive_wins", 0) + 1
    _finish("stabilized", up)

    return {"stabilized": True, "bonus_souls": bonus,
            "message": f"Реакция стабилизировалась. Буфер × {bonus_mult}!"}


def _finish(reason: str, up: dict,
            neutralizer_id: int = None, neutralizer_name: str = ""):
    """Завершение — запись в рекорды, сброс состояния."""
    started = _S.get("started_at")
    now = datetime.utcnow()
    dur = 0
    if started:
        try:
            dur = int((now - datetime.fromisoformat(started)).total_seconds() / 60)
        except Exception:
            pass

    rec = {
        "user_id": _S["user_id"],
        "username": _S.get("username", ""),
        "duration_minutes": dur,
        "drained_total": round((_S.get("drained_secure", 0) + _S.get("drained_buffer", 0)), 2),
        "reason": reason,
        "neutralizer": neutralizer_name if reason == "neutralized" else None,
        "date": now.strftime("%Y-%m-%d"),
    }

    recs: List = _S.get("records", [])
    recs.append(rec)
    recs.sort(key=lambda r: r["duration_minutes"], reverse=True)
    _S["records"] = recs[:10]

    if reason == "neutralized":
        _S["consecutive_wins"] = 0

    _S.update({
        "active": False, "user_id": None, "username": "",
        "started_at": None, "expires_at": None, "level": 1,
        "hp": 0, "max_hp": 0, "drained_secure": 0.0, "drained_buffer": 0.0,
    })
    _save()
    logger.info("Catalyst finished: reason=%s dur=%dmin", reason, dur)


def award_isotope(user_id: int, up: dict, reason: str = "") -> int:
    """Выдать Нестабильный Изотоп. Возвращает новое количество."""
    st = up.setdefault(user_id, {})
    st["unstable_isotopes"] = st.get("unstable_isotopes", 0) + 1
    logger.info("Isotope → user %s (%s): total=%d", user_id, reason, st["unstable_isotopes"])
    return st["unstable_isotopes"]


def get_player_info(user_id: int, user_level: int, up: dict) -> Dict[str, Any]:
    """Личная информация игрока о системе Катализатора."""
    st = up.get(user_id, {})
    today = datetime.utcnow().strftime("%Y-%m-%d")
    if st.get("atk_date") != today:
        attempts_left = user_level
        max_attempts = user_level
    else:
        attempts_left = st.get("atk_left", user_level)
        max_attempts = user_level
    return {
        "isotopes": st.get("unstable_isotopes", 0),
        "attempts_left": attempts_left,
        "max_attempts": max_attempts,
        "neutralizations": st.get("neutralizations", 0),
        "catalyst_wins": st.get("catalyst_wins", 0),
        "is_catalyst": _S.get("active") and _S.get("user_id") == user_id,
    }
