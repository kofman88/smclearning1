import io
from typing import Optional
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyArrowPatch, Rectangle
import matplotlib.gridspec as gridspec

CHART_STYLE = {
    "bg": "#0d1117",
    "panel": "#161b22",
    "grid": "#21262d",
    "bull": "#26a641",
    "bear": "#f85149",
    "accent": "#58a6ff",
    "gold": "#e3b341",
    "purple": "#bc8cff",
    "text": "#c9d1d9",
    "muted": "#8b949e",
}


def set_dark_style(fig, ax_list=None):
    fig.patch.set_facecolor(CHART_STYLE["bg"])
    if ax_list is None:
        ax_list = fig.get_axes()
    for ax in ax_list:
        ax.set_facecolor(CHART_STYLE["panel"])
        ax.tick_params(colors=CHART_STYLE["text"], labelsize=8)
        ax.xaxis.label.set_color(CHART_STYLE["text"])
        ax.yaxis.label.set_color(CHART_STYLE["text"])
        ax.title.set_color(CHART_STYLE["text"])
        for spine in ax.spines.values():
            spine.set_edgecolor(CHART_STYLE["grid"])
        ax.grid(True, color=CHART_STYLE["grid"], linewidth=0.5, alpha=0.7)


def fig_to_bytes(fig) -> io.BytesIO:
    buf = io.BytesIO()
    fig.savefig(
        buf,
        format="png",
        dpi=130,
        bbox_inches="tight",
        facecolor=CHART_STYLE["bg"],
    )
    buf.seek(0)
    plt.close(fig)
    return buf


def chart_what_is_smc() -> io.BytesIO:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 5))
    set_dark_style(fig, [ax1, ax2])

    fig.suptitle(
        "Smart Money vs Розничные трейдеры",
        color=CHART_STYLE["text"],
        fontsize=13,
    )

    labels = ["Банки\n(~40%)", "Хедж-фонды\n(~25%)", "Маркет-мейкеры\n(~20%)", "Розничные\nтрейдеры\n(~15%)"]
    sizes = [40, 25, 20, 15]
    colors = [
        CHART_STYLE["accent"],
        CHART_STYLE["bull"],
        CHART_STYLE["purple"],
        CHART_STYLE["bear"],
    ]
    wedges, texts, autotexts = ax1.pie(
        sizes,
        labels=labels,
        colors=colors,
        autopct="%1.0f%%",
        startangle=90,
        textprops={"color": CHART_STYLE["text"]},
    )
    for at in autotexts:
        at.set_color(CHART_STYLE["bg"])
        at.set_fontweight("bold")
    ax1.set_title("Участники рынка", color=CHART_STYLE["text"])

    categories = ["Банки", "Хедж-фонды", "Маркет-мейкеры", "Розничные"]
    influence = [40, 25, 20, 15]
    clrs = [
        CHART_STYLE["accent"],
        CHART_STYLE["bull"],
        CHART_STYLE["purple"],
        CHART_STYLE["bear"],
    ]
    bars = ax2.barh(categories, influence, color=clrs, height=0.55, edgecolor="none")
    for bar, val in zip(bars, influence):
        ax2.text(
            val + 0.5,
            bar.get_y() + bar.get_height() / 2,
            f"{val}%",
            va="center",
            color=CHART_STYLE["text"],
            fontsize=9,
            fontweight="bold",
        )
    ax2.set_xlim(0, 50)
    ax2.set_xlabel("Доля влияния на рынок (%)")
    ax2.set_title("Влияние на движение цены", color=CHART_STYLE["text"])
    ax2.invert_yaxis()

    plt.tight_layout()
    return fig_to_bytes(fig)


def chart_timeframes() -> io.BytesIO:
    fig, ax = plt.subplots(figsize=(10, 6))
    set_dark_style(fig, [ax])

    fig.suptitle(
        "Top-Down Анализ: Иерархия таймфреймов",
        color=CHART_STYLE["text"],
        fontsize=13,
    )

    tfs = [
        "W1/MN — Глобальный тренд",
        "D1 — Основное направление",
        "H4 — Swing-структура",
        "H1 — Рабочая структура",
        "M15 — Сетапы и зоны",
        "M5/M1 — Точка входа",
    ]
    purposes = [
        "Где мы находимся глобально?",
        "Покупки или продажи?",
        "HTF зоны & Order Blocks",
        "BOS, CHoCH, Inducement",
        "OB, FVG, OTE",
        "Триггер, SL, TP",
    ]
    colors = [
        CHART_STYLE["purple"],
        CHART_STYLE["accent"],
        CHART_STYLE["bull"],
        CHART_STYLE["gold"],
        "#ff8c69",
        CHART_STYLE["bear"],
    ]
    widths = [0.9, 0.78, 0.65, 0.52, 0.38, 0.25]

    ax.set_xlim(0, 1)
    ax.set_ylim(0, len(tfs) + 0.5)
    ax.axis("off")

    for i, (tf, purpose, color, w) in enumerate(
        zip(reversed(tfs), reversed(purposes), reversed(colors), reversed(widths))
    ):
        y = i + 0.3
        x = (1 - w) / 2
        rect = Rectangle((x, y), w, 0.65, linewidth=0, facecolor=color, alpha=0.85)
        ax.add_patch(rect)
        ax.text(
            0.5,
            y + 0.33,
            tf,
            ha="center",
            va="center",
            color="white",
            fontsize=9,
            fontweight="bold",
        )
        ax.text(
            0.5,
            y + 0.08,
            purpose,
            ha="center",
            va="center",
            color=CHART_STYLE["bg"],
            fontsize=7.5,
            alpha=0.9,
        )

    ax.annotate(
        "",
        xy=(0.5, 0.0),
        xytext=(0.5, len(tfs) + 0.2),
        arrowprops=dict(arrowstyle="-|>", color=CHART_STYLE["muted"], lw=1.5),
    )
    ax.text(
        0.5,
        -0.3,
        "Сверху вниз: от Макро к Микро",
        ha="center",
        color=CHART_STYLE["muted"],
        fontsize=9,
        style="italic",
    )
    return fig_to_bytes(fig)


def chart_market_structure() -> io.BytesIO:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    set_dark_style(fig, [ax1, ax2])

    fig.suptitle(
        "Market Structure: BOS & CHoCH",
        color=CHART_STYLE["text"],
        fontsize=13,
    )

    t = np.linspace(0, 10, 200)
    bull = 1.5 * np.sin(0.7 * t) + 0.25 * t + 10 + 0.15 * np.random.randn(200)
    ax1.plot(t, bull, color=CHART_STYLE["bull"], lw=1.5)
    pts = [
        (0.5, 9.8),
        (2.0, 11.2),
        (3.2, 10.3),
        (4.8, 12.1),
        (6.1, 11.2),
        (7.7, 13.4),
        (9.2, 12.5),
    ]
    for i, (x, y) in enumerate(pts):
        color = CHART_STYLE["bull"] if i % 2 == 1 else CHART_STYLE["bear"]
        lbl = "HH" if i % 2 == 1 and i > 0 else ("HL" if i % 2 == 0 and i > 0 else "SL")
        ax1.annotate(
            lbl,
            (x, y),
            textcoords="offset points",
            xytext=(0, 8 if i % 2 == 1 else -10),
            color=color,
            fontsize=8,
            fontweight="bold",
            ha="center",
        )
        ax1.plot(x, y, "o", color=color, ms=5, zorder=5)
    ax1.axhline(12.1, color=CHART_STYLE["gold"], lw=1, ls="--", alpha=0.7)
    ax1.text(9.5, 12.2, "BOS →", color=CHART_STYLE["gold"], fontsize=8)
    ax1.set_title("Бычий тренд: HH / HL", color=CHART_STYLE["text"])
    ax1.set_xlabel("Время")
    ax1.set_ylabel("Цена")

    t2 = np.linspace(0, 10, 200)
    bear_wave = -1.2 * np.sin(0.65 * t2 - 0.5) + 12 - 0.2 * t2 + 0.1 * np.random.randn(200)
    ax2.plot(t2, bear_wave, color=CHART_STYLE["bear"], lw=1.5)
    choch_pts = [
        (0.5, 12.2),
        (2.0, 13.1),
        (3.5, 11.5),
        (5.0, 12.2),
        (6.5, 10.8),
        (8.0, 11.2),
        (9.2, 9.8),
    ]
    labels = ["HL", "HH", "LL", "LH", "LL", "CHoCH", "LL"]
    for (x, y), lbl in zip(choch_pts, labels):
        c = CHART_STYLE["bear"] if "L" in lbl else CHART_STYLE["bull"]
        if lbl == "CHoCH":
            c = CHART_STYLE["accent"]
        ax2.annotate(
            lbl,
            (x, y),
            textcoords="offset points",
            xytext=(0, 10 if y > 11.3 else -12),
            color=c,
            fontsize=8,
            fontweight="bold",
            ha="center",
        )
        ax2.plot(x, y, "o", color=c, ms=5, zorder=5)
    ax2.axhline(11.5, color=CHART_STYLE["accent"], lw=1.2, ls="--", alpha=0.8)
    ax2.text(0.2, 11.3, "CHoCH — разворот!", color=CHART_STYLE["accent"], fontsize=8)
    ax2.set_title("CHoCH — Смена характера структуры", color=CHART_STYLE["text"])
    ax2.set_xlabel("Время")

    plt.tight_layout()
    return fig_to_bytes(fig)


def chart_inducement() -> io.BytesIO:
    fig, ax = plt.subplots(figsize=(10, 6))
    set_dark_style(fig, [ax])

    fig.suptitle(
        "Inducement (Ловушка для толпы)",
        color=CHART_STYLE["text"],
        fontsize=13,
    )

    t = np.linspace(0, 12, 300)
    price = (
        10
        + 0.5 * np.sin(t)
        + 0.1 * t
        + np.where(t < 5, 0, np.where(t < 6, 1.2 * (t - 5), 1.2))
        + np.where(t > 8, -2 * (t - 8), 0)
        + 0.05 * np.random.randn(300)
    )
    price = np.clip(price, 8, 14)
    ax.plot(t, price, color=CHART_STYLE["accent"], lw=1.8)

    ax.axhline(11.8, color=CHART_STYLE["gold"], lw=1.2, ls="--", alpha=0.85)
    ax.text(
        0.2,
        11.9,
        "Inducement Level (видимый уровень)",
        color=CHART_STYLE["gold"],
        fontsize=8.5,
    )

    ax.annotate(
        "Толпа\nпродаёт/покупает",
        xy=(5.5, 11.95),
        xytext=(3.5, 13.0),
        arrowprops=dict(arrowstyle="->", color=CHART_STYLE["bear"], lw=1.5),
        color=CHART_STYLE["bear"],
        fontsize=8.5,
        fontweight="bold",
        ha="center",
    )
    ax.annotate(
        "Sweep!\nТолпа выбита",
        xy=(6.5, 12.55),
        xytext=(8.0, 13.3),
        arrowprops=dict(arrowstyle="->", color=CHART_STYLE["bear"], lw=1.5),
        color=CHART_STYLE["bear"],
        fontsize=8.5,
        fontweight="bold",
        ha="center",
    )
    ax.annotate(
        "SM разворачивает\nнастоящее движение",
        xy=(9.0, 11.0),
        xytext=(10.0, 12.8),
        arrowprops=dict(arrowstyle="->", color=CHART_STYLE["bull"], lw=1.5),
        color=CHART_STYLE["bull"],
        fontsize=8.5,
        fontweight="bold",
        ha="center",
    )

    ax.fill_between(
        t,
        11.6,
        12.0,
        where=(t >= 4.5) & (t <= 7.0),
        alpha=0.15,
        color=CHART_STYLE["gold"],
        label="Зона Inducement",
    )

    ax.set_xlabel("Время")
    ax.set_ylabel("Цена")
    ax.legend(
        facecolor=CHART_STYLE["panel"],
        edgecolor=CHART_STYLE["grid"],
        labelcolor=CHART_STYLE["text"],
        fontsize=8,
    )
    return fig_to_bytes(fig)


def chart_liquidity() -> io.BytesIO:
    fig, ax = plt.subplots(figsize=(10, 6))
    set_dark_style(fig, [ax])

    fig.suptitle(
        "Ликвидность: BSL & SSL",
        color=CHART_STYLE["text"],
        fontsize=13,
    )

    np.random.seed(42)
    t = np.arange(0, 100)
    price = 100 + np.cumsum(np.random.randn(100) * 0.6)
    ax.plot(t, price, color=CHART_STYLE["accent"], lw=1.5, zorder=3)

    bsl_levels = [105.5, 108.2, 112.0]
    for lvl in bsl_levels:
        ax.axhline(lvl, color=CHART_STYLE["bull"], lw=1.2, ls="--", alpha=0.7)
        ax.text(
            1,
            lvl + 0.3,
            f"BSL {lvl:.1f}",
            color=CHART_STYLE["bull"],
            fontsize=7.5,
            fontweight="bold",
        )

    ssl_levels = [94.8, 97.3, 99.0]
    for lvl in ssl_levels:
        ax.axhline(lvl, color=CHART_STYLE["bear"], lw=1.2, ls="--", alpha=0.7)
        ax.text(
            1,
            lvl - 1.0,
            f"SSL {lvl:.1f}",
            color=CHART_STYLE["bear"],
            fontsize=7.5,
            fontweight="bold",
        )

    ax.annotate(
        "Equal Highs\n(видимая ликвидность)",
        xy=(70, 108.2),
        xytext=(50, 111.0),
        arrowprops=dict(arrowstyle="->", color=CHART_STYLE["gold"]),
        color=CHART_STYLE["gold"],
        fontsize=8,
        ha="center",
    )

    ax.scatter(
        [72, 85],
        [108.5, 94.5],
        s=120,
        color=CHART_STYLE["gold"],
        zorder=6,
        marker="*",
        label="Sweep (сбор ликвидности)",
    )

    bsl_patch = mpatches.Patch(
        color=CHART_STYLE["bull"],
        label="BSL — над максимумами (стопы покупателей)",
    )
    ssl_patch = mpatches.Patch(
        color=CHART_STYLE["bear"],
        label="SSL — под минимумами (стопы продавцов)",
    )
    ax.legend(
        handles=[bsl_patch, ssl_patch],
        facecolor=CHART_STYLE["panel"],
        edgecolor=CHART_STYLE["grid"],
        labelcolor=CHART_STYLE["text"],
        fontsize=8,
        loc="upper left",
    )

    ax.set_xlabel("Время (бары)")
    ax.set_ylabel("Цена")
    return fig_to_bytes(fig)


def chart_liquidity_pools() -> io.BytesIO:
    fig, ax = plt.subplots(figsize=(10, 6))
    set_dark_style(fig, [ax])

    fig.suptitle(
        "Пулы Ликвидности — Маршрут цены",
        color=CHART_STYLE["text"],
        fontsize=13,
    )

    np.random.seed(7)
    t = np.linspace(0, 20, 400)
    price = (
        100
        + 3 * np.sin(0.5 * t)
        + 2 * np.sin(1.2 * t + 1)
        + 0.5 * np.cumsum(np.random.randn(400) * 0.05)
    )
    ax.plot(t, price, color=CHART_STYLE["accent"], lw=1.5, zorder=3)

    pools = [
        (102.8, "Asia High Pool", CHART_STYLE["gold"]),
        (108.5, "Weekly High Pool", CHART_STYLE["bull"]),
        (97.2, "Asia Low Pool", CHART_STYLE["bear"]),
        (93.5, "Weekly Low Pool", CHART_STYLE["purple"]),
    ]
    for lvl, name, c in pools:
        ax.axhline(lvl, color=c, lw=1.5, ls=(0, (5, 3)), alpha=0.85)
        ax.text(20.1, lvl, name, color=c, fontsize=7.5, va="center", fontweight="bold")
        ax.fill_between(t, lvl - 0.4, lvl + 0.4, alpha=0.12, color=c)

    arrows = [(3, 102.2, 6, 108.0), (6, 107.8, 10, 97.5), (10, 97.3, 15, 102.5)]
    for x1, y1, x2, y2 in arrows:
        ax.annotate(
            "",
            xy=(x2, y2),
            xytext=(x1, y1),
            arrowprops=dict(
                arrowstyle="-|>",
                color=CHART_STYLE["muted"],
                lw=1.2,
                alpha=0.9,
            ),
        )

    ax.text(
        0.5,
        110,
        "Цена движется от пула к пулу",
        color=CHART_STYLE["muted"],
        fontsize=9,
        fontweight="bold",
    )

    ax.set_xlabel("Время")
    ax.set_ylabel("Цена")
    ax.set_xlim(0, 22)
    return fig_to_bytes(fig)


def _draw_candles(ax, data, bull_c, bear_c):
    for i, (o, h, l, c) in enumerate(data):
        color = bull_c if c >= o else bear_c
        ax.plot([i, i], [l, h], color=color, lw=1.2, zorder=3)
        rect = Rectangle(
            (i - 0.3, min(o, c)),
            0.6,
            abs(c - o),
            facecolor=color,
            edgecolor=color,
            lw=0.5,
            zorder=4,
        )
        ax.add_patch(rect)
    ax.set_xlim(-0.8, len(data) - 0.2)


def chart_order_blocks() -> io.BytesIO:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    set_dark_style(fig, [ax1, ax2])

    fig.suptitle(
        "Order Blocks: бычий и медвежий",
        color=CHART_STYLE["text"],
        fontsize=13,
    )

    bull_candles = [
        (10.0, 10.5, 9.8, 10.2),
        (10.2, 10.4, 9.9, 10.1),
        (10.1, 10.3, 9.7, 9.9),
        (9.9, 10.0, 9.6, 9.7),
        (9.7, 11.0, 9.6, 10.8),
        (10.8, 11.5, 10.7, 11.4),
        (11.4, 12.0, 11.2, 11.9),
        (11.9, 12.3, 11.7, 12.1),
    ]
    _draw_candles(ax1, bull_candles, CHART_STYLE["bull"], CHART_STYLE["bear"])
    ob_rect = Rectangle(
        (2.7, 9.6),
        0.6,
        0.4,
        facecolor=CHART_STYLE["bull"],
        edgecolor=CHART_STYLE["bull"],
        alpha=0.25,
        lw=1.5,
        linestyle="--",
        zorder=2,
    )
    ax1.add_patch(ob_rect)
    ax1.axhspan(9.6, 10.0, alpha=0.08, color=CHART_STYLE["bull"])
    ax1.text(
        3,
        9.3,
        "Бычий OB\n(последняя медвежья свеча)",
        color=CHART_STYLE["bull"],
        fontsize=8,
        ha="center",
        fontweight="bold",
    )
    ax1.annotate(
        "Импульс вверх (BOS)",
        xy=(4, 10.9),
        xytext=(1.5, 12.0),
        arrowprops=dict(arrowstyle="->", color=CHART_STYLE["bull"]),
        color=CHART_STYLE["bull"],
        fontsize=8,
        ha="center",
    )
    ax1.set_title("Бычий Order Block", color=CHART_STYLE["text"])
    ax1.set_ylabel("Цена")

    bear_candles = [
        (12.0, 12.4, 11.9, 12.3),
        (12.3, 12.5, 12.1, 12.4),
        (12.4, 12.7, 12.2, 12.6),
        (12.6, 13.0, 12.4, 12.9),
        (12.9, 13.1, 11.5, 11.7),
        (11.7, 11.9, 11.0, 11.1),
        (11.1, 11.3, 10.5, 10.6),
        (10.6, 10.8, 10.2, 10.4),
    ]
    _draw_candles(ax2, bear_candles, CHART_STYLE["bull"], CHART_STYLE["bear"])
    ob_rect2 = Rectangle(
        (2.7, 12.4),
        0.6,
        0.7,
        facecolor=CHART_STYLE["bear"],
        edgecolor=CHART_STYLE["bear"],
        alpha=0.25,
        lw=1.5,
        linestyle="--",
        zorder=2,
    )
    ax2.add_patch(ob_rect2)
    ax2.axhspan(12.4, 13.1, alpha=0.08, color=CHART_STYLE["bear"])
    ax2.text(
        3,
        13.3,
        "Медвежий OB\n(последняя бычья свеча)",
        color=CHART_STYLE["bear"],
        fontsize=8,
        ha="center",
        fontweight="bold",
    )
    ax2.annotate(
        "Импульс вниз (BOS)",
        xy=(4, 11.6),
        xytext=(1.5, 10.3),
        arrowprops=dict(arrowstyle="->", color=CHART_STYLE["bear"]),
        color=CHART_STYLE["bear"],
        fontsize=8,
        ha="center",
    )
    for ax in [ax1, ax2]:
        ax.set_xticks([])

    plt.tight_layout()
    return fig_to_bytes(fig)


def chart_fvg() -> io.BytesIO:
    fig, ax = plt.subplots(figsize=(10, 6))
    set_dark_style(fig, [ax])

    fig.suptitle(
        "Fair Value Gap (FVG) — Имбаланс",
        color=CHART_STYLE["text"],
        fontsize=13,
    )

    candles = [
        (10.0, 10.3, 9.9, 10.2),
        (10.2, 10.4, 10.1, 10.3),
        (10.3, 10.5, 10.2, 10.4),
        (10.4, 11.8, 10.3, 11.6),
        (11.6, 12.5, 11.3, 12.4),
        (12.4, 12.7, 12.2, 12.6),
        (12.6, 12.8, 12.3, 12.5),
        (12.5, 12.7, 11.9, 12.0),
        (12.0, 12.1, 11.7, 11.85),
        (11.85, 12.4, 11.8, 12.3),
        (12.3, 12.6, 12.2, 12.5),
        (12.5, 12.9, 12.4, 12.8),
    ]
    _draw_candles(ax, candles, CHART_STYLE["bull"], CHART_STYLE["bear"])

    ax.fill_between([-0.8, 11.8], 11.8, 12.2, alpha=0.22, color=CHART_STYLE["gold"])
    ax.axhline(11.8, color=CHART_STYLE["gold"], lw=1, ls="--", alpha=0.8)
    ax.axhline(12.2, color=CHART_STYLE["gold"], lw=1, ls="--", alpha=0.8)

    ax.text(
        1.5,
        12.0,
        "FVG зона (Имбаланс)",
        color=CHART_STYLE["gold"],
        fontsize=9,
        va="center",
    )
    ax.annotate(
        "Цена заполняет FVG\nперед продолжением",
        xy=(9.5, 11.9),
        xytext=(6.5, 11.3),
        arrowprops=dict(arrowstyle="->", color=CHART_STYLE["accent"]),
        color=CHART_STYLE["accent"],
        fontsize=8.5,
        ha="center",
    )
    ax.annotate(
        "Импульс создаёт FVG",
        xy=(4.5, 12.0),
        xytext=(3.0, 13.0),
        arrowprops=dict(arrowstyle="->", color=CHART_STYLE["bull"]),
        color=CHART_STYLE["bull"],
        fontsize=8.5,
        ha="center",
    )

    ax.set_xticks([])
    ax.set_ylabel("Цена")
    ax.set_ylim(9.5, 13.5)
    return fig_to_bytes(fig)


def chart_breaker_blocks() -> io.BytesIO:
    fig, ax = plt.subplots(figsize=(10, 6))
    set_dark_style(fig, [ax])

    fig.suptitle(
        "Breaker Block — Эволюция Order Block",
        color=CHART_STYLE["text"],
        fontsize=13,
    )

    candles = [
        (12.0, 12.5, 11.9, 12.4),
        (12.4, 12.6, 12.2, 12.5),
        (12.5, 12.9, 12.3, 12.8),
        (12.8, 13.2, 12.6, 12.7),
        (12.7, 12.8, 11.4, 11.5),
        (11.5, 11.7, 11.0, 11.1),
        (11.1, 11.3, 10.8, 11.0),
        (11.0, 11.2, 10.9, 11.1),
        (11.1, 12.6, 11.0, 12.5),
        (12.5, 12.7, 12.0, 12.3),
        (12.3, 12.1, 11.5, 11.6),
        (11.6, 11.8, 11.2, 11.3),
    ]
    _draw_candles(ax, candles, CHART_STYLE["bull"], CHART_STYLE["bear"])

    ax.fill_between([-0.5, 3.7], 12.6, 13.2, alpha=0.15, color=CHART_STYLE["gold"])
    ax.text(
        1.5,
        13.25,
        "Исходный бычий OB",
        color=CHART_STYLE["gold"],
        fontsize=8,
        ha="center",
    )

    ax.fill_between([7.5, 11.8], 12.3, 12.8, alpha=0.25, color=CHART_STYLE["bear"])
    ax.text(
        9.5,
        12.88,
        "Breaker Block (медвежий)",
        color=CHART_STYLE["bear"],
        fontsize=8.5,
        ha="center",
    )

    ax.annotate(
        "BOS — пробой OB вниз",
        xy=(4.5, 12.0),
        xytext=(2.5, 11.0),
        arrowprops=dict(arrowstyle="->", color=CHART_STYLE["bear"]),
        color=CHART_STYLE["bear"],
        fontsize=8,
        ha="center",
    )
    ax.annotate(
        "Ретест Breaker → продажи",
        xy=(8.5, 12.4),
        xytext=(6.5, 13.5),
        arrowprops=dict(arrowstyle="->", color=CHART_STYLE["bear"]),
        color=CHART_STYLE["bear"],
        fontsize=8.5,
        ha="center",
    )

    ax.set_xticks([])
    ax.set_ylabel("Цена")
    return fig_to_bytes(fig)


def chart_mitigation_blocks() -> io.BytesIO:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    set_dark_style(fig, [ax1, ax2])

    fig.suptitle(
        "Mitigation Block vs Breaker Block",
        color=CHART_STYLE["text"],
        fontsize=13,
    )

    mit_c = [
        (10.0, 10.4, 9.9, 10.3),
        (10.3, 10.6, 10.2, 10.5),
        (10.5, 10.8, 10.3, 10.4),
        (10.4, 11.2, 10.3, 11.1),
        (11.1, 11.5, 11.0, 11.4),
        (11.4, 11.6, 11.1, 11.2),
        (11.2, 11.3, 10.7, 10.8),
        (10.8, 10.95, 10.6, 10.7),
        (10.7, 11.8, 10.6, 11.7),
        (11.7, 12.0, 11.5, 11.9),
    ]
    _draw_candles(ax1, mit_c, CHART_STYLE["bull"], CHART_STYLE["bear"])
    ax1.fill_between([-0.5, 9.5], 10.3, 10.8, alpha=0.2, color=CHART_STYLE["accent"])
    ax1.text(
        4.5,
        10.15,
        "Mitigation Block (OB удержан)",
        color=CHART_STYLE["accent"],
        fontsize=8,
        ha="center",
    )
    ax1.annotate(
        "Цена митигирует OB\n(не пробивает)",
        xy=(6.5, 10.75),
        xytext=(4.5, 12.0),
        arrowprops=dict(arrowstyle="->", color=CHART_STYLE["accent"]),
        color=CHART_STYLE["accent"],
        fontsize=8,
        ha="center",
    )
    ax1.set_title("Mitigation Block", color=CHART_STYLE["text"])
    ax1.set_ylabel("Цена")

    br_c = [
        (12.0, 12.5, 11.9, 12.4),
        (12.4, 12.7, 12.3, 12.6),
        (12.6, 13.0, 12.4, 12.7),
        (12.7, 12.8, 11.0, 11.1),
        (11.1, 11.3, 10.8, 11.0),
        (11.0, 12.8, 10.9, 12.7),
        (12.7, 12.9, 12.3, 12.4),
        (12.4, 12.2, 11.5, 11.6),
    ]
    _draw_candles(ax2, br_c, CHART_STYLE["bull"], CHART_STYLE["bear"])
    ax2.fill_between([-0.5, 7.5], 12.4, 13.0, alpha=0.22, color=CHART_STYLE["bear"])
    ax2.text(
        3.5,
        13.15,
        "Breaker Block (пробит, сменил роль)",
        color=CHART_STYLE["bear"],
        fontsize=8,
        ha="center",
    )
    ax2.annotate(
        "Пробой OB = он\nстановится Breaker",
        xy=(3, 12.2),
        xytext=(1.5, 11.2),
        arrowprops=dict(arrowstyle="->", color=CHART_STYLE["bear"]),
        color=CHART_STYLE["bear"],
        fontsize=8,
        ha="center",
    )
    ax2.set_title("Breaker Block", color=CHART_STYLE["text"])

    for ax in [ax1, ax2]:
        ax.set_xticks([])

    plt.tight_layout()
    return fig_to_bytes(fig)


def chart_premium_discount() -> io.BytesIO:
    fig, ax = plt.subplots(figsize=(10, 7))
    set_dark_style(fig, [ax])

    fig.suptitle(
        "Premium & Discount Zones",
        color=CHART_STYLE["text"],
        fontsize=13,
    )

    np.random.seed(3)
    t = np.arange(0, 80)
    price = 100 + np.cumsum(np.random.randn(80) * 0.7)

    swing_low = 93.0
    swing_high = 113.0
    mid = (swing_low + swing_high) / 2
    ote_low = swing_low + 0.62 * (swing_high - swing_low)
    ote_high = swing_low + 0.79 * (swing_high - swing_low)

    ax.plot(t, price, color=CHART_STYLE["accent"], lw=1.5, zorder=4)

    ax.fill_between(
        t,
        swing_high,
        120,
        alpha=0.12,
        color=CHART_STYLE["bear"],
        label="Premium (дорого)",
    )
    ax.fill_between(
        t,
        swing_low,
        mid,
        alpha=0.12,
        color=CHART_STYLE["bull"],
        label="Discount (дёшево)",
    )
    ax.fill_between(
        t,
        ote_low,
        ote_high,
        alpha=0.18,
        color=CHART_STYLE["gold"],
        label="OTE (62–79%)",
    )

    ax.axhline(swing_high, color=CHART_STYLE["bear"], lw=1.5, ls="--")
    ax.axhline(swing_low, color=CHART_STYLE["bull"], lw=1.5, ls="--")
    ax.axhline(mid, color=CHART_STYLE["muted"], lw=1.5, ls="-")
    ax.axhline(ote_low, color=CHART_STYLE["gold"], lw=1, ls=":")
    ax.axhline(ote_high, color=CHART_STYLE["gold"], lw=1, ls=":")

    ax.text(
        81,
        swing_high,
        "Swing High",
        color=CHART_STYLE["bear"],
        fontsize=8,
        va="center",
        fontweight="bold",
    )
    ax.text(
        81,
        swing_low,
        "Swing Low",
        color=CHART_STYLE["bull"],
        fontsize=8,
        va="center",
        fontweight="bold",
    )
    ax.text(
        81,
        mid,
        "50% EQ",
        color=CHART_STYLE["muted"],
        fontsize=8,
        va="center",
    )
    ax.text(
        81,
        (ote_low + ote_high) / 2,
        "OTE\n62-79%",
        color=CHART_STYLE["gold"],
        fontsize=8,
        va="center",
        fontweight="bold",
    )
    ax.text(
        35,
        117,
        "PREMIUM — Smart Money продают",
        color=CHART_STYLE["bear"],
        fontsize=9,
        ha="center",
        fontweight="bold",
    )
    ax.text(
        35,
        96,
        "DISCOUNT — Smart Money покупают",
        color=CHART_STYLE["bull"],
        fontsize=9,
        ha="center",
        fontweight="bold",
    )

    ax.legend(
        facecolor=CHART_STYLE["panel"],
        edgecolor=CHART_STYLE["grid"],
        labelcolor=CHART_STYLE["text"],
        fontsize=8,
        loc="lower right",
    )
    ax.set_ylabel("Цена")
    ax.set_xlabel("Время (бары)")
    ax.set_xlim(0, 95)

    return fig_to_bytes(fig)


def chart_killzones() -> io.BytesIO:
    fig, ax = plt.subplots(figsize=(12, 5))
    set_dark_style(fig, [ax])

    fig.suptitle(
        "Kill Zones — Торговые Сессии (UTC+3)",
        color=CHART_STYLE["text"],
        fontsize=13,
    )

    sessions = [
        ("Азия", 2, 6, CHART_STYLE["purple"], "Формирование диапазона\n(Asia Range)"),
        ("Лондон", 10, 14, CHART_STYLE["accent"], "Sweep Asia High/Low\n→ Kill Zone"),
        ("Нью-Йорк", 15, 19, CHART_STYLE["gold"], "Основное движение\n→ Kill Zone"),
        ("Ночь", 0, 2, CHART_STYLE["muted"], "Низкий объём"),
        ("Пост-NY", 19, 24, CHART_STYLE["muted"], "Низкий объём"),
    ]

    ax.set_xlim(0, 24)
    ax.set_ylim(0, 1)
    ax.set_yticks([])
    ax.set_xticks(range(0, 25, 2))
    ax.set_xticklabels([f"{h}:00" for h in range(0, 25, 2)], fontsize=8)
    ax.set_xlabel("Время (UTC+3)", color=CHART_STYLE["text"])

    for name, start, end, color, desc in sessions:
        alpha = 0.75 if color != CHART_STYLE["muted"] else 0.3
        rect = Rectangle(
            (start, 0.2), end - start, 0.6, facecolor=color, alpha=alpha, edgecolor="none"
        )
        ax.add_patch(rect)
        mid = (start + end) / 2
        ax.text(
            mid,
            0.62,
            name,
            ha="center",
            va="center",
            color="white",
            fontsize=9,
            fontweight="bold",
        )
        ax.text(
            mid,
            0.35,
            desc,
            ha="center",
            va="center",
            color=CHART_STYLE["bg"],
            fontsize=7.5,
        )

    ax.annotate(
        "",
        xy=(10, 0.9),
        xytext=(4, 0.9),
        arrowprops=dict(arrowstyle="-|>", color=CHART_STYLE["accent"], lw=1.5),
    )
    ax.text(7, 0.93, "Sweep", ha="center", color=CHART_STYLE["accent"], fontsize=8)

    ax.annotate(
        "",
        xy=(15.5, 0.9),
        xytext=(12.5, 0.9),
        arrowprops=dict(arrowstyle="-|>", color=CHART_STYLE["gold"], lw=1.5),
    )
    ax.text(14.0, 0.93, "NY движение", ha="center", color=CHART_STYLE["gold"], fontsize=8)

    return fig_to_bytes(fig)


def chart_ote() -> io.BytesIO:
    fig, ax = plt.subplots(figsize=(10, 7))
    set_dark_style(fig, [ax])

    fig.suptitle(
        "OTE — Optimal Trade Entry (62–79% по Фибо)",
        color=CHART_STYLE["text"],
        fontsize=13,
    )

    low = 100.0
    high = 115.0
    levels = {
        "100%": low,
        "78.6%": low + 0.214 * (high - low),
        "70.5%": low + 0.295 * (high - low),
        "61.8%": low + 0.382 * (high - low),
        "50%": low + 0.5 * (high - low),
        "38.2%": low + 0.618 * (high - low),
        "23.6%": low + 0.764 * (high - low),
        "0%": high,
    }

    t = list(range(13))
    price = [100, 101, 103, 106, 110, 115, 113, 111, 109, 107.5, 108, 110, 113]
    ax.plot(t, price, color=CHART_STYLE["accent"], lw=2, zorder=5, label="Цена")

    colors_fib = {
        "0%": CHART_STYLE["bull"],
        "23.6%": CHART_STYLE["bull"],
        "38.2%": CHART_STYLE["muted"],
        "50%": CHART_STYLE["muted"],
        "61.8%": CHART_STYLE["gold"],
        "70.5%": CHART_STYLE["gold"],
        "78.6%": CHART_STYLE["gold"],
        "100%": CHART_STYLE["bear"],
    }

    for label, val in levels.items():
        c = colors_fib.get(label, CHART_STYLE["muted"])
        ax.axhline(val, color=c, lw=0.8, ls="--", alpha=0.7)
        ax.text(12.2, val, f"{label} — {val:.1f}", color=c, fontsize=7.5, va="center")

    ote_low = low + 0.214 * (high - low)
    ote_high = low + 0.382 * (high - low)
    ax.fill_between([0, 12], ote_low, ote_high, alpha=0.18, color=CHART_STYLE["gold"])
    ax.text(
        6,
        (ote_low + ote_high) / 2,
        "OTE ZONE (62–79%)",
        ha="center",
        va="center",
        color=CHART_STYLE["gold"],
        fontsize=10,
        fontweight="bold",
    )

    ax.scatter(
        [9],
        [107.5],
        color=CHART_STYLE["gold"],
        s=150,
        zorder=8,
        marker="*",
        label="Вход в OTE",
    )
    ax.annotate(
        "Вход в OTE\n(OB + FVG + Kill Zone)",
        xy=(9, 107.5),
        xytext=(7, 103.5),
        arrowprops=dict(arrowstyle="->", color=CHART_STYLE["gold"]),
        color=CHART_STYLE["gold"],
        fontsize=8.5,
        ha="center",
        fontweight="bold",
    )

    ax.set_ylabel("Цена")
    ax.set_xlabel("Время")
    ax.set_xlim(0, 14.5)
    ax.legend(
        facecolor=CHART_STYLE["panel"],
        edgecolor=CHART_STYLE["grid"],
        labelcolor=CHART_STYLE["text"],
        fontsize=8,
    )
    return fig_to_bytes(fig)


def chart_amd_model() -> io.BytesIO:
    fig, ax = plt.subplots(figsize=(12, 6))
    set_dark_style(fig, [ax])

    fig.suptitle(
        "AMD Model: Accumulation → Manipulation → Distribution",
        color=CHART_STYLE["text"],
        fontsize=13,
    )

    t = np.linspace(0, 15, 400)
    acc = np.where(t <= 5, 100 + 0.3 * np.sin(3 * t) + 0.05 * np.random.randn(400), 0)
    man = np.where(
        (t > 5) & (t <= 8),
        100 + 0.3 * np.sin(3 * t) - 1.5 * (t - 5) + 0.05 * np.random.randn(400),
        0,
    )
    dist_base = np.where(
        t > 8,
        95.5 + 3.0 * (t - 8) + 0.1 * np.sin(1.5 * t) + 0.05 * np.random.randn(400),
        0,
    )
    price = acc + man + dist_base
    price = np.where(price == 0, np.nan, price)

    ax.plot(t, price, color=CHART_STYLE["accent"], lw=2, zorder=4)

    ax.axvline(5, color=CHART_STYLE["muted"], lw=1, ls="--", alpha=0.6)
    ax.axvline(8, color=CHART_STYLE["muted"], lw=1, ls="--", alpha=0.6)

    ax.fill_between(
        t, 97, 103, where=(t <= 5), alpha=0.12, color=CHART_STYLE["purple"]
    )
    ax.fill_between(
        t, 92, 103, where=(t > 5) & (t <= 8), alpha=0.12, color=CHART_STYLE["bear"]
    )
    ax.fill_between(
        t, 92, 120, where=(t > 8), alpha=0.10, color=CHART_STYLE["bull"]
    )

    ax.text(
        2.5,
        96.5,
        "ACCUMULATION\nАзия — накопление",
        ha="center",
        color=CHART_STYLE["purple"],
        fontsize=9,
        fontweight="bold",
    )
    ax.text(
        6.5,
        93.5,
        "MANIPULATION\nЛондон — Judas Swing",
        ha="center",
        color=CHART_STYLE["bear"],
        fontsize=9,
        fontweight="bold",
    )
    ax.text(
        11.5,
        96.5,
        "DISTRIBUTION\nNY — настоящее движение",
        ha="center",
        color=CHART_STYLE["bull"],
        fontsize=9,
        fontweight="bold",
    )

    ax.annotate(
        "Sweep SSL\n(ложный пробой)",
        xy=(7.5, 93.8),
        xytext=(6.8, 101.5),
        arrowprops=dict(arrowstyle="->", color=CHART_STYLE["bear"]),
        color=CHART_STYLE["bear"],
        fontsize=8,
        ha="center",
    )

    ax.set_xlabel("Время")
    ax.set_ylabel("Цена")
    ax.set_ylim(90, 125)
    return fig_to_bytes(fig)


def chart_power_of_three() -> io.BytesIO:
    fig, ax = plt.subplots(figsize=(10, 6))
    set_dark_style(fig, [ax])

    fig.suptitle(
        "Power of Three (Po3) — Дневной цикл",
        color=CHART_STYLE["text"],
        fontsize=13,
    )

    t = np.linspace(0, 24, 500)
    np.random.seed(123)

    asia = np.where(
        t <= 6,
        100 + 0.4 * np.sin(2 * t) + 0.03 * np.random.randn(500),
        np.nan,
    )
    london_sw = np.where(
        (t > 6) & (t <= 9),
        100
        + 0.4 * np.sin(2 * 6)
        - 1.5 * (t - 6)
        + 0.03 * np.random.randn(500),
        np.nan,
    )
    ny = np.where(
        t > 9,
        97.5 + 2.0 * (t - 9) + 0.1 * np.sin(t) + 0.05 * np.random.randn(500),
        np.nan,
    )

    ax.plot(t, asia, color=CHART_STYLE["purple"], lw=2.5, label="Азия — диапазон")
    ax.plot(
        t, london_sw, color=CHART_STYLE["bear"], lw=2.5, label="Лондон — Judas Swing"
    )
    ax.plot(
        t, ny, color=CHART_STYLE["bull"], lw=2.5, label="NY — настоящее движение"
    )

    ax.axvline(6, color=CHART_STYLE["muted"], lw=1, ls="--")
    ax.axvline(9, color=CHART_STYLE["muted"], lw=1, ls="--")

    ax.fill_between(
        t, 99, 101, where=(t <= 6), alpha=0.1, color=CHART_STYLE["purple"]
    )
    ax.text(
        3,
        98.5,
        "Asia Range",
        ha="center",
        color=CHART_STYLE["purple"],
        fontsize=8.5,
    )

    ax.annotate(
        "Judas Swing\n(ложный пробой SSL)",
        xy=(7.5, 97.4),
        xytext=(5.5, 95.5),
        arrowprops=dict(arrowstyle="->", color=CHART_STYLE["bear"]),
        color=CHART_STYLE["bear"],
        fontsize=8,
        ha="center",
    )
    ax.annotate(
        "Po3 — настоящий\nдневной тренд вверх",
        xy=(16, 112.5),
        xytext=(12, 117),
        arrowprops=dict(arrowstyle="->", color=CHART_STYLE["bull"]),
        color=CHART_STYLE["bull"],
        fontsize=8,
        ha="center",
    )

    ax.set_xlim(0, 24)
    ax.set_xticks([0, 3, 6, 9, 12, 15, 18, 21, 24])
    ax.set_xticklabels(
        ["00:00", "03:00", "06:00", "09:00", "12:00", "15:00", "18:00", "21:00", "24:00"]
    )
    ax.set_xlabel("Время суток (UTC+3)")
    ax.set_ylabel("Цена")
    ax.legend(
        facecolor=CHART_STYLE["panel"],
        edgecolor=CHART_STYLE["grid"],
        labelcolor=CHART_STYLE["text"],
        fontsize=8,
    )
    return fig_to_bytes(fig)


def chart_market_maker_model() -> io.BytesIO:
    fig, ax = plt.subplots(figsize=(12, 7))
    set_dark_style(fig, [ax])

    fig.suptitle(
        "Market Maker Model — Полный Цикл",
        color=CHART_STYLE["text"],
        fontsize=13,
    )

    stages = {
        "1. Accumulation\n(Набор позиции)": (
            0,
            3,
            99,
            101,
            CHART_STYLE["purple"],
        ),
        "2. Manipulation\n(Sweep BSL)": (3, 5, 99, 103.5, CHART_STYLE["gold"]),
        "3. Smart Money Reversal\n(CHoCH)": (5, 7, 97, 103.5, CHART_STYLE["accent"]),
        "4. Distribution\n(Движение к цели)": (7, 12, 95, 115, CHART_STYLE["bull"]),
    }

    np.random.seed(99)
    t = np.linspace(0, 12, 300)
    p = (
        100
        + np.where(t < 3, 0.3 * np.sin(5 * t), 0)
        + np.where((t >= 3) & (t < 5), 0.3 * np.sin(5 * t) + 1.5 * (t - 3), 0)
        + np.where((t >= 5) & (t < 7), 3.0 - 2.5 * (t - 5), 0)
        + np.where(t >= 7, -2.0 + 3.5 * (t - 7), 0)
        + 0.08 * np.random.randn(300)
    )
    ax.plot(t, p, color=CHART_STYLE["accent"], lw=1.8, zorder=5)

    for label, (x1, x2, y1, y2, c) in stages.items():
        ax.fill_between([x1, x2], y1, y2, alpha=0.1, color=c)
        ax.axvline(x1, color=c, lw=0.8, ls=":", alpha=0.5)
        ax.text(
            (x1 + x2) / 2,
            y1 - 1.5,
            label,
            ha="center",
            color=c,
            fontsize=8,
            fontweight="bold",
        )

    ax.annotate(
        "Sweep BSL\n(ловушка покупателей)",
        xy=(4.5, 103.2),
        xytext=(3.5, 107),
        arrowprops=dict(arrowstyle="->", color=CHART_STYLE["gold"]),
        color=CHART_STYLE["gold"],
        fontsize=8,
        ha="center",
    )
    ax.annotate(
        "CHoCH — разворот",
        xy=(6, 99.5),
        xytext=(5.5, 95),
        arrowprops=dict(arrowstyle="->", color=CHART_STYLE["accent"]),
        color=CHART_STYLE["accent"],
        fontsize=8,
        ha="center",
    )
    ax.annotate(
        "Цель — следующий пул\nликвидности",
        xy=(11, 114.5),
        xytext=(9, 110),
        arrowprops=dict(arrowstyle="->", color=CHART_STYLE["bull"]),
        color=CHART_STYLE["bull"],
        fontsize=8,
        ha="center",
    )

    ax.set_xlabel("Время")
    ax.set_ylabel("Цена")
    ax.set_ylim(91, 120)
    return fig_to_bytes(fig)


def chart_ict_2022_model() -> io.BytesIO:
    fig, ax = plt.subplots(figsize=(12, 7))
    set_dark_style(fig, [ax])

    fig.suptitle(
        "ICT 2022 Mentorship Model — Алгоритм Long",
        color=CHART_STYLE["text"],
        fontsize=13,
    )

    ax.axis("off")

    steps = [
        ("1. HTF тренд\n(D1/H4)", CHART_STYLE["purple"], "Бычий тренд — ищем покупки"),
        ("2. Kill Zone\n(Лондон / NY)", CHART_STYLE["accent"], "Вход только в активные сессии"),
        ("3. Sweep SSL\n(Ложный пробой)", CHART_STYLE["gold"], "Цена выбивает минимумы (стопы)"),
        ("4. CHoCH / MSS\n(Слом структуры)", CHART_STYLE["bull"], "Смена структуры вверх на M5/M15"),
        ("5. FVG или OB\n(Зона для входа)", CHART_STYLE["bull"], "Находим POI на откате"),
        ("6. Вход + SL + TP\n(Исполнение)", CHART_STYLE["gold"], "SL под SSL, TP к BSL (1:3+)"),
    ]
    n = len(steps)

    for i, (title, color, desc) in enumerate(steps):
        x = 0.12 + (i % 3) * 0.28
        y = 0.72 if i < 3 else 0.28
        rect = Rectangle(
            (x - 0.11, y - 0.16),
            0.22,
            0.32,
            facecolor=color,
            edgecolor="white",
            linewidth=1.2,
            alpha=0.85,
            transform=ax.transAxes,
        )
        ax.add_patch(rect)
        ax.text(
            x,
            y + 0.08,
            title,
            ha="center",
            va="center",
            transform=ax.transAxes,
            color="white",
            fontsize=9,
            fontweight="bold",
        )
        ax.text(
            x,
            y - 0.06,
            desc,
            ha="center",
            va="center",
            transform=ax.transAxes,
            color=CHART_STYLE["bg"],
            fontsize=7.5,
            alpha=0.9,
        )
        ax.text(
            x - 0.10,
            y + 0.14,
            f"Step {i+1}",
            transform=ax.transAxes,
            color=CHART_STYLE["bg"],
            fontsize=7,
            fontweight="bold",
        )

    for i in range(n - 1):
        x1 = 0.12 + (i % 3) * 0.28 + 0.11
        x2 = 0.12 + ((i + 1) % 3) * 0.28 - 0.11
        if i == 2:
            ax.annotate(
                "",
                xy=(0.12 - 0.11, 0.28 + 0.16),
                xytext=(0.12 + 2 * 0.28 + 0.11, 0.72 - 0.16),
                arrowprops=dict(arrowstyle="-|>", color=CHART_STYLE["muted"], lw=1.5),
                xycoords="axes fraction",
                textcoords="axes fraction",
            )
        else:
            y = 0.72 if i < 2 else 0.28
            ax.annotate(
                "",
                xy=(x2, y),
                xytext=(x1, y),
                arrowprops=dict(arrowstyle="-|>", color=CHART_STYLE["muted"], lw=1.5),
                xycoords="axes fraction",
                textcoords="axes fraction",
            )

    ax.text(
        0.5,
        0.04,
        "Результат: высоковероятная сделка с R:R ≥ 1:3",
        ha="center",
        transform=ax.transAxes,
        color=CHART_STYLE["gold"],
        fontsize=10,
        fontweight="bold",
    )
    return fig_to_bytes(fig)


def chart_session_sweep_model() -> io.BytesIO:
    fig, ax = plt.subplots(figsize=(12, 6))
    set_dark_style(fig, [ax])

    fig.suptitle(
        "Session Sweep Model: Asia → London → NY",
        color=CHART_STYLE["text"],
        fontsize=13,
    )

    t = np.linspace(0, 24, 500)
    np.random.seed(55)

    asia_range_h = 101.5
    asia_range_l = 98.5
    p = np.where(
        t <= 8,
        100 + 0.6 * np.sin(1.5 * t) + 0.05 * np.random.randn(500),
        0,
    )
    sweep_up = np.where(
        (t > 8) & (t <= 10),
        100 + 0.6 * np.sin(1.5 * 8) + 1.8 * (t - 8) + 0.05 * np.random.randn(500),
        0,
    )
    reversal = np.where(
        (t > 10) & (t <= 12),
        asia_range_h + 2.16 - 2.0 * (t - 10) + 0.05 * np.random.randn(500),
        0,
    )
    ny_move = np.where(
        t > 12,
        99.5 - 2.5 * (t - 12) + 0.05 * np.cumsum(np.random.randn(500)),
        0,
    )
    price = p + sweep_up + reversal + ny_move
    price = np.where(price == 0, np.nan, price)

    ax.plot(t, price, color=CHART_STYLE["accent"], lw=2, zorder=5)

    ax.axhline(
        asia_range_h,
        color=CHART_STYLE["bull"],
        lw=1.2,
        ls="--",
        alpha=0.8,
        label="Asia High",
    )
    ax.axhline(
        asia_range_l,
        color=CHART_STYLE["bear"],
        lw=1.2,
        ls="--",
        alpha=0.8,
        label="Asia Low",
    )

    ax.fill_between(
        t,
        asia_range_l,
        asia_range_h,
        where=(t <= 8),
        alpha=0.08,
        color=CHART_STYLE["purple"],
    )
    ax.fill_between(
        t,
        96,
        106,
        where=(t > 8) & (t <= 12),
        alpha=0.08,
        color=CHART_STYLE["accent"],
    )
    ax.fill_between(
        t,
        96,
        106,
        where=(t > 12),
        alpha=0.08,
        color=CHART_STYLE["bull"],
    )

    ax.text(
        4,
        97.0,
        "Азия\nДиапазон формируется",
        ha="center",
        color=CHART_STYLE["purple"],
        fontsize=8,
    )
    ax.annotate(
        "Sweep Asia High\n(ловушка для быков)",
        xy=(9.2, 103.5),
        xytext=(7, 106),
        arrowprops=dict(arrowstyle="->", color=CHART_STYLE["gold"]),
        color=CHART_STYLE["gold"],
        fontsize=8.5,
        ha="center",
    )
    ax.text(
        11,
        101.5,
        "Разворот",
        ha="center",
        color=CHART_STYLE["accent"],
        fontsize=8,
        fontweight="bold",
    )
    ax.text(
        18,
        97.5,
        "NY — движение\nв противоположную сторону",
        ha="center",
        color=CHART_STYLE["bull"],
        fontsize=8,
    )

    ax.set_xlim(0, 24)
    ax.set_xticks([0, 3, 6, 8, 10, 12, 15, 18, 21, 24])
    ax.set_xticklabels(
        ["00", "03", "06", "08\nАзия", "10\nЛондон", "12", "15\nNY", "18", "21", "24"]
    )
    ax.set_xlabel("Время (UTC+3)")
    ax.set_ylabel("Цена")
    ax.legend(
        facecolor=CHART_STYLE["panel"],
        edgecolor=CHART_STYLE["grid"],
        labelcolor=CHART_STYLE["text"],
        fontsize=8,
    )
    return fig_to_bytes(fig)


def chart_risk_management() -> io.BytesIO:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    set_dark_style(fig, [ax1, ax2])

    fig.suptitle(
        "Риск-менеджмент в SMC",
        color=CHART_STYLE["text"],
        fontsize=13,
    )

    rr_ratios = ["1:1", "1:2", "1:3 (цель)", "1:5"]
    win_rates_needed = [50, 34, 25, 17]
    colors = [
        CHART_STYLE["bear"],
        CHART_STYLE["gold"],
        CHART_STYLE["bull"],
        CHART_STYLE["accent"],
    ]
    bars = ax1.bar(rr_ratios, win_rates_needed, color=colors, width=0.5, edgecolor="none")
    for bar, val in zip(bars, win_rates_needed):
        ax1.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.5,
            f"{val}%",
            ha="center",
            color=CHART_STYLE["text"],
            fontsize=9,
            fontweight="bold",
        )

    ax1.axhline(33, color=CHART_STYLE["muted"], lw=1, ls="--", alpha=0.7)
    ax1.text(3.4, 34, "Рекомендуемый WR", color=CHART_STYLE["muted"], fontsize=8)
    ax1.set_ylabel("Минимальный Win Rate (%)")
    ax1.set_title("R:R vs минимальный Win Rate", color=CHART_STYLE["text"])

    sizes = [1, 2, 3, 5]
    labels = ["1R", "2R", "3R", "5R"]
    explode = (0, 0.05, 0.08, 0.1)
    ax2.pie(
        sizes,
        labels=labels,
        autopct="%1.1fx",
        startangle=140,
        colors=[
            CHART_STYLE["bear"],
            CHART_STYLE["accent"],
            CHART_STYLE["bull"],
            CHART_STYLE["gold"],
        ],
        explode=explode,
        textprops={"color": CHART_STYLE["text"], "fontsize": 8},
    )
    ax2.set_title("Множители прибыли (R)", color=CHART_STYLE["text"])

    plt.tight_layout()
    return fig_to_bytes(fig)


CHART_MAP = {
    "what_is_smc": chart_what_is_smc,
    "timeframes": chart_timeframes,
    "market_structure": chart_market_structure,
    "inducement": chart_inducement,
    "liquidity": chart_liquidity,
    "liquidity_pools": chart_liquidity_pools,
    "order_blocks": chart_order_blocks,
    "fvg": chart_fvg,
    "breaker_blocks": chart_breaker_blocks,
    "mitigation_blocks": chart_mitigation_blocks,
    "premium_discount": chart_premium_discount,
    "killzones": chart_killzones,
    "ote": chart_ote,
    "amd_model": chart_amd_model,
    "power_of_three": chart_power_of_three,
    "market_maker_model": chart_market_maker_model,
    "ict_2022_model": chart_ict_2022_model,
    "session_sweep_model": chart_session_sweep_model,
    "risk_management": chart_risk_management,
}


def generate_chart(lesson_key: str) -> Optional[io.BytesIO]:
    func = CHART_MAP.get(lesson_key)
    if not func:
        return None
    return func()
