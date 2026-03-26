import os
from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class TokenConfig:
    name: str
    symbol: str
    emoji: str
    decimals: int
    total_supply: int
    launch_network: str
    dex_pair: str



def get_token_config() -> TokenConfig:
    cfg = {
        "name": os.getenv("APP_TOKEN_NAME", "CHM"),
        "symbol": os.getenv("APP_TOKEN_SYMBOL", "CHM"),
        "emoji": os.getenv("APP_TOKEN_EMOJI", "⚡"),
        "decimals": int(os.getenv("APP_TOKEN_DECIMALS", "9")),
        "total_supply": int(os.getenv("APP_TOKEN_TOTAL_SUPPLY", "1000000000")),
        "launch_network": os.getenv("APP_TOKEN_NETWORK", "TON"),
        "dex_pair": os.getenv("APP_TOKEN_DEX_PAIR", "TON/USDT"),
    }
    return TokenConfig(**cfg)



def get_token_labels() -> Dict[str, str]:
    cfg = get_token_config()
    return {
        "name": cfg.name,
        "symbol": cfg.symbol,
        "emoji": cfg.emoji,
    }



def build_launch_plan(*, holders: int, active_users_30d: int, liquidity_usd: float, volume_7d_usd: float) -> Dict[str, Any]:
    """Return readiness checklist for DEX->CEX rollout."""
    dex_ready = (
        holders >= 500
        and active_users_30d >= 300
        and liquidity_usd >= 25000
    )
    cex_ready = (
        holders >= 5000
        and active_users_30d >= 2500
        and liquidity_usd >= 250000
        and volume_7d_usd >= 1000000
    )

    return {
        "dex": {
            "ready": dex_ready,
            "requirements": {
                "min_holders": 500,
                "min_active_users_30d": 300,
                "min_liquidity_usd": 25000,
            },
        },
        "cex": {
            "ready": cex_ready,
            "requirements": {
                "min_holders": 5000,
                "min_active_users_30d": 2500,
                "min_liquidity_usd": 250000,
                "min_volume_7d_usd": 1000000,
            },
        },
        "phases": [
            "Phase 0: closed beta + anti-sybil + testnet airdrop",
            "Phase 1: DEX listing with deep LP and 6-12 months vesting",
            "Phase 2: market-maker + risk desk + compliance pack",
            "Phase 3: CEX listing only after stable retention and organic volume",
        ],
    }



def estimate_daily_emission_cap(*, active_users_24h: int, burn_24h: float) -> Dict[str, Any]:
    """Adaptive emission cap to reduce inflation risk."""
    base_cap = max(1000.0, active_users_24h * 12.0)
    burn_factor = 1.0 + min(0.5, burn_24h / max(base_cap, 1.0))
    cap = round(base_cap * burn_factor, 2)
    return {
        "emission_cap": cap,
        "formula": "max(1000, active_users_24h*12) * (1 + min(0.5, burn_24h/base_cap))",
        "note": "If minted > cap, reduce rewards or increase sinks for the next epoch.",
    }
