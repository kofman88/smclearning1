# SMC Quest — Telegram Mini App

Курс по Smart Money Concepts: 8 модулей, 20 уроков, квизы, задания, лидерборд.

## Структура

```
smc_quest/
├── main.py           # FastAPI сервер (исправлен circular import)
├── bot.py            # Telegram бот (без localhost вызовов)
├── progress.py       # Хранение прогресса (с atomic write)
├── lessons.py        # Контент уроков
├── quests.py         # Квесты и квизы
├── charts.py         # Генерация графиков
├── requirements.txt
├── render.yaml
├── .env.example
└── frontend/
    ├── index.html    # Полный UI (все модалки)
    ├── style.css     # Dark crypto тема
    └── app.js        # Полная логика (квиз + задания)
```

## Что исправлено

- ❌ Circular import `main.py → bot.py → main.py` → ✅ разделены
- ❌ Квиз и задания — только `alert()` → ✅ полная реализация
- ❌ Progress bar всегда 0% → ✅ считается по квестам
- ❌ Markdown в статьях не рендерился (`*bold*` как текст) → ✅ парсинг
- ❌ Bot вызывал `localhost:8000` → ✅ прямые вызовы progress.py
- ❌ `fronend` (опечатка) → ✅ `frontend`
- ✅ Atomic write для JSON (tmp → replace)
- ✅ Configurable DATA_DIR

## Deploy на Render

1. Создай новый Web Service
2. Укажи Build Command: `pip install -r requirements.txt`
3. Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Environment Variables:
   - `BOT_TOKEN` = токен от @BotFather
   - `WEBHOOK_URL` = `https://smc-quest-miniapp.onrender.com`
   - `ADMIN_ID` = твой Telegram ID
   - `DATA_DIR` = `/tmp` (или `/data` если есть Render Disk)

## ⚠️ Важно: прогресс на Render Free

На бесплатном плане Render контейнер перезапускается, файлы в `/tmp` теряются.
Для постоянного хранения добавь Render Disk и установи `DATA_DIR=/data`.

## Локальный запуск

```bash
cp .env.example .env
# заполни .env
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
# открой http://localhost:8000/static/index.html
```

## Бот: команды

- `/start` — открыть Mini App
- `/stats` — статистика
- `/top` — лидерборд

### Админ команды
- `/approve user_id quest_id` — принять задание
- `/reject user_id quest_id [комментарий]` — отклонить
- `/extend user_id дни` — продлить дедлайн
