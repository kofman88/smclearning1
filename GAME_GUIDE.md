# CHM Smart Money Academy — Полный гайд по игровой логике

> Стек: FastAPI (бэкенд) + Vanilla JS (фронтенд, без React)
> Файлы: `backend/frontend/app.js`, `backend/frontend/index.html`, `backend/frontend/style.css`

---

## 1. АРХИТЕКТУРА И ИНИЦИАЛИЗАЦИЯ

### `state` — глобальное состояние (app.js ~87)
```js
const state = {
  userId,          // Telegram user ID (или DEV_UID в разработке)
  sessionToken,    // Токен сессии, выдаётся /api/user/init, отправляется в write-запросах
  userState,       // Последний ответ от /api/user/state — все данные юзера
  quizData,        // Текущий активный квест/вопрос
  currentQuestId,  // ID открытого квеста
  lessonsMetaCache,// Кэш метаданных уроков { moduleIndex: data }
  quizStreak,      // Текущий стрик правильных ответов в квизе
  countdownInterval,// ID setInterval для дедлайн-таймера
  deadlineInfo,    // Данные о дедлайне текущего модуля
  _catalystInterval,// Guard против двойного setInterval при повторном init()
  _actionsInterval, // Guard против двойного setInterval при повторном init()
}
```

### `SMC_LEVELS` — 7 уровней трейдера (app.js ~102)
| Level | XP needed | Название | Цвет кольца |
|-------|-----------|----------|-------------|
| 1 | 0 | Наблюдатель рынка | Серый |
| 2 | 300 | Охотник за ликвидностью | Голубой |
| 3 | 700 | Снайпер ордер-блоков | Фиолетовый |
| 4 | 1300 | SMC Практик | Зелёный |
| 5 | 2100 | Smart Money Инсайдер | Жёлтый |
| 6 | 3200 | Институциональный призрак | Золотой |
| 7 | 5000 | Архитектор рынка | Красный |

### `getLevelInfo(xp)` — (app.js ~123)
Возвращает объект уровня `{ xp, level, name, color, glow }` по текущему XP. Используется для окраски кольца аватара и других UI-элементов.

### `getRankSVG(rankName)` — (app.js ~133)
Генерирует уникальный SVG-аватар для каждого ранга. У каждого уровня своя геометрия и цветовая схема. Уникальные gradient ID предотвращают конфликты при нескольких SVG на странице.

---

## 2. ONBOARDING РИТУАЛ

### Функции `_runRitualPhase1..6` и `onRitualComplete` (app.js ~202–325)
Показывается один раз при первом запуске (если `localStorage.smc_ritual_done` не установлен).

**Поток:**
1. **Phase 1** → тайпрайтер: «Ты пришёл учиться у рынка.»
2. **Phase 2** → тайпрайтер: «Рынок не прощает. Мы тоже.»
3. **Phase 3** → колба появляется, ждёт тап (авто-тап через 10 сек)
4. **Phase 4** → анимация синтеза + вспышка
5. **Phase 5** → гомункул рождается, анимируется счётчик +50 душ
6. **Phase 6** → подсказки по UI (2 тултипа)
7. **`onRitualComplete`** → вызывает `POST /api/onboarding/complete` → +50 душ на сервере

---

## 3. ЗВУКОВОЙ ДВИЖОК

### `_sfx` и `SOUNDS` (app.js ~15–70)
Все звуки генерируются **программно через Web Audio API** — никаких файлов.

| ID | Когда играет |
|----|-------------|
| `tap` | Любой тап/клик |
| `combo10/50/100` | Стрик 10/50/100 правильных ответов подряд |
| `xp` | Получение XP |
| `levelup` | Повышение уровня |
| `questdone` | Квест завершён |
| `soulsgain` | Получение душ |
| `soulslost` | Потеря душ |
| `hit` | Удар по боссу |
| `catalyst_on` | Катализатор активирован |
| `neutralized` | Катализатор нейтрализован |
| `evolution` | Эволюция гомункула |
| `bosswin` | Победа над боссом |
| `buy` | Покупка в магазине |
| `bonus` | Бонус/реферал |

### `toggleSound()` (app.js ~77)
Вкл/выкл звук. Состояние хранится в `localStorage.chm_sfx`.

---

## 4. ХЕДЕР И HUD

### `renderHeader(s)` (app.js ~612)
Принимает объект `userState` с сервера. Обновляет:
- SVG-аватар через `getRankSVG(s.rank)`
- Кольцо уровня через `getLevelInfo(s.xp).color`
- Имя пользователя (макс 14 символов)
- Название ранга
- HUD-пилли: Souls, XP, Level
- XP полоску под хедером через `_updateXPStrip(s.xp)`
- Эстус-колбы через `updateEstusHUD()`

### `_updateXPStrip(xp)` (app.js ~648)
Рассчитывает % прогресса к следующему уровню и анимирует полоску `.xp-strip-fill`. Переход плавный (CSS `transition: width 0.8s`).

**Тап на аватар** → открывает Scholar Journal (`openScholarJournal()`).

---

## 5. НАВИГАЦИЯ ВКЛАДОК

### `switchTab(name)` (app.js ~576)
Переключает между 4 вкладками: `lessons`, `quests`, `leaderboard`, `homunculus`.

**При каждом переключении:**
- Убирает `.active` со всех `.tn-tab` и `.tab-content`
- Добавляет `.active` на нужные
- Загружает данные для вкладки
- При открытии Рейтинга/Алхимии — **очищает бейджи** (`_clearTabBadge`)

### `_showTabBadge(tabName, color)` / `_clearTabBadge(tabName)` (app.js ~613)
Управляют точками уведомлений на иконках вкладок.

| Бейдж | Цвет | Когда показывается |
|-------|------|-------------------|
| `tnBadgeLeaderboard` | 🟡 amber | Есть незабранные Battle Pass награды |
| `tnBadgeLeaderboard` | 🔴 red | Активный рейд, пользователь ещё не атаковал |
| `tnBadgeAlchemy` | 🔴 red | Катализатор активен |

---

## 6. ДЕДЛАЙН-СИСТЕМА (72 часа)

### `startCountdown(deadlineISO)` (app.js ~418)
Запускает таймер обратного отсчёта. Каждую секунду обновляет UI и применяет CSS-классы срочности:

| Времени осталось | CSS-класс | Визуал |
|-----------------|-----------|--------|
| > 24 часов | `urgency-normal` | Белый |
| ≤ 24 часов | `urgency-warning` | Жёлтый |
| ≤ 6 часов | `urgency-danger` | Оранжевый |
| ≤ 1 часа | `urgency-critical` | Красный, мигает |
| 0 | `urgency-expired` | Показывает `showDeadlineExpiredScreen()` |

### `showDeadlineExpiredScreen()` (app.js ~470)
Показывает оверлей с двумя опциями:
1. **Оплатить штраф** (`POST /api/deadline/penalty`, `payment_type: "penalty"`) — продление на 48 часов
2. **Перекупить доступ** (`POST /api/deadline/penalty`, `payment_type: "repurchase"`) — полное продление на 72 часа (если расширения исчерпаны)

---

## 7. УРОКИ

### `loadLessons()` / `renderLessons(data)`
Загружает список модулей и уроков с сервера `GET /api/modules`. Отображает в `#modulesList`.

### `setProgress(completed, total)` (app.js ~644)
Обновляет прогресс-бар в хедере: `#progressBar`, `#progressLabel`, `#progressPct`.

---

## 8. КВЕСТЫ И КВИЗ

### `loadQuests()` → `renderQuests(data)`
Загружает квесты текущего модуля с `GET /api/quests/{userId}`. Каждый квест — это урок с вопросами.

### `openQuest(questId)` → `loadQuizQuestion(questId)`
Открывает квест, загружает первый вопрос через `GET /api/quiz/question/{questId}/{userId}`.

### `submitAnswer(answerId)` — основная игровая петля
1. Отправляет `POST /api/quiz/answer`
2. Получает `{correct, xp_gained, souls_change, streak, level_up, new_rank, quest_complete, boss_available}`
3. Если правильно: анимация успеха, звуки, обновление HUD
4. Если неправильно: анимация ошибки, потеря душ
5. Комбо-эффекты при стриках 10/50/100
6. Если `level_up = true` → показывает `showLevelUp()`
7. Если `quest_complete = true` → показывает экран завершения / переходит к боссу

---

## 9. БОИ С БОССАМИ

### `_showBossVictory(data)` (app.js ~3130)
Показывает экран победы после успешного боя с боссом. Отображает:
- Имя босса
- Статистику: точность, правильные/всего, заработанные души
- Частицы победы (`_spawnVictoryParticles`)
- Кнопку **«Поделиться победой»** (`_addShareToBossVictory`)

### `_addShareToBossVictory(bossName, souls, accuracy)` (app.js ~3168)
Добавляет кнопку шеринга прямо над кнопкой «Продолжить». Текст шеринга:
```
⚔️ Я победил [BOSS] в CHM Academy!
[accuracy]% точности · [souls] душ заработано
Присоединяйся → t.me/CHM_smcbot
```

### `shareBossVictory(text)` (app.js ~3185)
- В Telegram: открывает `t.me/share/url` с текстом
- Вне Telegram: копирует в буфер обмена

### `afterBossVictory()` (app.js ~3168)
Закрывает экран победы, показывает Bonfre screen (`showBonfire()`).

---

## 10. СИСТЕМА ДУШ (SOULS)

### Механика
- **Души** (⚡) — основная валюта, аналог HP в Dark Souls
- Зарабатываются: правильные ответы, победы над боссами, квесты, стрики
- Теряются: неправильные ответы (штраф), дедлайны
- При смерти (0 душ) часть теряется на «земле»

### `spawnSoulParticle(text, isGain)`
Анимированная частица с числом душ, всплывает над экраном.

### `_updateSoulsDisplay(souls)`
Обновляет отображение душ в HUD.

---

## 11. ЭСТУС-КОЛБЫ (ESTUS FLASKS)

### `updateEstusHUD(current, max)` (app.js ~386)
Отображает колбы Эстуса в хедере — "жизни" в стиле Dark Souls. Восполняются при отдыхе у Костра (Bonfire).

---

## 12. ДЕЙСТВИЯ (ACTIONS POOL)

### `renderActionsHUD(d)` (app.js ~1606)
Отображает карточку в **вкладке Алхимия** (переехала из хедера).

**Логика:**
- `d.left` — действий осталось сегодня
- `d.daily_total` — всего действий в день
- `d.catalyst_chance_pct` — шанс стать Катализатором (растёт с каждым действием)
- Кружочки: 🟢 = доступно, ⚪ = потрачено
- При 0 действий показывает время до полуночи UTC (сброс)

---

## 13. КАТАЛИЗАТОР РАСПАДА

### Механика
Один игрок становится **Катализатором** — активным «вызовом» для всего сообщества. Получает изотопы, другие игроки атакуют его вопросами.

### `loadCatalyst()` (app.js ~1630)
Загружает статус: `GET /api/catalyst/status` + `GET /api/catalyst/my/{userId}`.

### `renderCatalyst(cat, my)` (app.js ~1643)
- Если нет активного катализатора: показывает карточку с шансом (`catalyst_chance_pct`) и кнопкой активации (если есть изотопы)
- Если катализатор активен: показывает босс-карточку, HP, атаки
- Если текущий юзер — катализатор: особый режим с защитой

### Бейдж
`_showTabBadge("Alchemy", "red")` — красная точка на вкладке Алхимия при активном катализаторе.

---

## 14. РЕЙТИНГ И ЛИЧНАЯ ТАБЛИЦА

### `loadLeaderboard()` / `loadPersonalLeaderboard()`
- `GET /api/leaderboard` → топ-игроков
- `GET /api/leaderboard/personal/{userId}` → позиция текущего юзера и соседи по рейтингу

### Отображение
Подиум для топ-3, список для остальных. Личная позиция подсвечена отдельно.

---

## 15. BATTLE PASS (Сезонный пропуск)

### `loadBattlePass()` (app.js ~4680)
Загружает прогресс сезона: `GET /api/season/progress/{userId}`.

### `_renderBattlePass(d)` (app.js ~4659)
Показывает:
- Название сезона и дней осталось
- XP-бар к следующему уровню
- Список незабранных наград (`claimable`) с кнопками «Забрать»
- Трек всех 30 уровней сезона

### `claimBP(level)` (app.js ~4709)
`POST /api/season/claim` → получает награду уровня.

### Бейдж
При `claimable_count > 0` → `_showTabBadge("Leaderboard", "amber")` — жёлтая точка на вкладке Рейтинг.

---

## 16. КЛАНОВЫЙ РЕЙД

### Механика
Раз в неделю (в понедельник 10:00 UTC) открывается **групповой босс**. Все игроки атакуют отвечая на вопрос. Каждый ответ снимает HP с босса.

### `loadRaid()` (app.js ~4940)
`GET /api/raid/status` → статус рейда, HP босса, участники.

### `_renderRaid(d)` (app.js ~4947)
- Если рейд неактивен: плашка «Следующий рейд — в понедельник»
- Если активен: HP-бар босса, вопрос для атаки
- Если уже атаковал: показывает результат

### Бейдж
При активном рейде и `!myAnswered` → `_showTabBadge("Leaderboard", "red")`.

---

## 17. АЛХИМИЯ (ГОМУНКУЛ)

### `loadHomunculus()` / `renderHomunculus(data)`
Показывает существо, которое «эволюционирует» вместе с прогрессом. Уровень гомункула = уровень игрока.

---

## 18. МАГАЗИН

### `loadShop()` / `_renderShop(data)` (app.js ~...)
`GET /api/shop/items` → список товаров. Покупка через `POST /api/shop/buy`.

**Типы товаров:**
- Эстус-колбы (восполнение жизней)
- Изотопы (для активации Катализатора)
- Другие расходники

---

## 19. РЕФЕРАЛЬНАЯ СИСТЕМА

### `loadReferral()` / `_renderReferral(d)` (app.js ~4731)
`GET /api/referral/{userId}` → реферальная ссылка, статистика.

**Показывает:**
- Ссылка + кнопка «Скопировать»
- Кнопка «Поделиться» (открывает Telegram share)
- Статистика: кол-во приглашённых, душ заработано
- Вехи (milestones) с наградами

---

## 20. SCHOLAR JOURNAL (Журнал Учёного)

### `openScholarJournal()` (app.js ~...)
Открывается по **тапу на аватар** в хедере.

**Показывает:**
- SVG-аватар с рангом
- Статистику: уроков пройдено, стрик дней, общий XP, ранг
- Суммарные души
- Кнопку «Поделиться в Telegram»

---

## 21. LIVE SIGNAL

### `loadLiveSignal()` / `renderLiveSignal(d)`
Торговый сигнал от команды. Показывается как баннер поверх основного контента. Можно закрыть (dismissed ID сохраняется локально).

---

## 22. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ

### `showToast(text, type)`
Всплывающее уведомление (success / error / info). Автоматически исчезает через ~2 сек.

### `launchConfetti(count)` (app.js ~346)
Цветное конфетти при важных событиях (level up, квест завершён).

### `floatXP(amount, sourceEl)` (app.js ~368)
Всплывающий `+N XP` рядом с источником события.

### `showLevelUp(level, rankName)` (app.js ~383)
Оверлей при повышении уровня: новый ранг, цитата, частицы, конфетти.

### `refreshHeader()`
`GET /api/user/state/{userId}` → вызывает `renderHeader()`. Используется после любых действий меняющих данные юзера.

### `$('#id')`
Алиас для `document.getElementById()` (или querySelector).

---

## 23. ПОТОК ИНИЦИАЛИЗАЦИИ

```
init()
  ├── Определяем userId (из Telegram WebApp или DEV_UID)
  ├── POST /api/user/init → sessionToken
  ├── GET /api/user/state/{userId} → renderHeader()
  ├── loadLessons() → показать список модулей
  ├── startCountdown(deadlineISO) → если есть дедлайн
  ├── loadActions() → renderActionsHUD()
  ├── loadCatalyst() → первичная проверка катализатора
  ├── loadRaid() → проверка рейда
  ├── setInterval(loadCatalyst, 90s) → авто-обновление
  ├── setInterval(loadActions, 60s) → авто-обновление
  └── Показать onboarding ритуал (если первый запуск)
```

---

## 24. API ENDPOINTS (краткий справочник)

| Endpoint | Метод | Описание |
|----------|-------|----------|
| `/api/user/init` | POST | Инициализация, создание/получение юзера |
| `/api/user/state/{id}` | GET | Полное состояние юзера |
| `/api/modules` | GET | Список модулей и уроков |
| `/api/quests/{id}` | GET | Квесты модуля |
| `/api/quiz/question/{qid}/{uid}` | GET | Текущий вопрос квеста |
| `/api/quiz/answer` | POST | Ответ на вопрос |
| `/api/actions/{id}` | GET | Пул действий на сегодня |
| `/api/catalyst/status` | GET | Статус катализатора |
| `/api/catalyst/my/{id}` | GET | Данные катализатора юзера |
| `/api/leaderboard` | GET | Топ рейтинга |
| `/api/leaderboard/personal/{id}` | GET | Личная позиция в рейтинге |
| `/api/season/progress/{id}` | GET | Battle Pass прогресс |
| `/api/season/claim` | POST | Забрать Battle Pass награду |
| `/api/raid/status` | GET | Статус клан-рейда |
| `/api/shop/items` | GET | Товары магазина |
| `/api/shop/buy` | POST | Покупка товара |
| `/api/referral/{id}` | GET | Реферальные данные |
| `/api/deadline/penalty` | POST | Оплата штрафа/перекупка |
| `/api/onboarding/complete` | POST | Завершение онбординга (+50 душ) |

---

## 25. СТРУКТУРА CSS

| Файл/Блок | Отвечает за |
|-----------|-------------|
| `.app-header` | Хедер: аватар + HUD пилли |
| `.xp-strip-*` | XP полоска под хедером |
| `.avatar-level-ring` | Цветное кольцо вокруг аватара |
| `.tabs-nav` / `.tn-tab` | Новый таббар с иконками |
| `.tn-badge` | Точки уведомлений на вкладках |
| `.tab-content` | Контент каждой вкладки |
| `.actions-hud-card` | Карточка действий в Алхимии |
| `.boss-share-block` | Кнопка шеринга победы над боссом |
| `.bp-*` | Battle Pass трек и награды |
| `.raid-*` | Клановый рейд |
| `.cat-*` | Катализатор распада |
| `.hom-*` | Гомункул / Алхимия |
| `.deadline-countdown` | Таймер дедлайна |
| `#bossVictoryScreen` | Экран победы над боссом |
| `.ref-*` | Реферальная система |
