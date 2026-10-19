# Final Frontend Integration — VibeRoute

Проверено 19 октября 2026. Ветка `feature/frontend-map`, существующий PR #11.
Из `origin/main` подтянуты уже готовые Weather/H3 API. PR в main не слит.

## Исправления

- Клиент в development всегда вызывает `/api/v1/...` через Vite proxy.
  Удалён fallback на жёсткий localhost backend URL.
- Production поддерживает HTTPS backend origin в `VITE_API_BASE_URL`, также с `/api`.
  Вариант без переменной использует same-origin `/api`. Небезопасный HTTP origin
  отклоняется сборкой. Описана точная настройка `CORS_ORIGINS` FastAPI.
- Подключён настоящий `POST /api/v1/routes/plan`. Карта получает `route_geojson`
  непосредственно из ответа, карточки и таймлайн — реальные stops;
  сводка — distance/walking/visiting/total из backend. Показаны warnings и `no_route`.
- Найден и исправлен дополнительный дефект MapLibre 6 ESM: Vite перемещал entry,
  а относительный worker URL переставал работать. До исправления маркеры могли
  быть видны без ORS-линии. Worker теперь отдельный asset через `setWorkerUrl`.
  Это проверено и в dev, и в production bundle.
- Нет автоматического демо при загрузке или сбое API. Только явная кнопка
  «Показать демо», с заметной пометкой «Демонстрационные данные» в интерфейсе и на карте.
  Реальный запрос удаляет прежний маршрут, демо и изохрону до отправки.
- Удалена клиентская ORS-переменная из `.env.example`; ключ остаётся только backend.
- Удалён фиксированный H3, выдававшийся за местоположение пользователя.
- Погода подключена по выбранному `start_anchor_id`: температура, ветер и warnings.
  `unknown`/`null` показываются как отсутствие данных, ноль отображается как ноль.
  Устаревшие запросы погоды отменяются при смене старта; сбои не блокируют planner.
- По добровольному нажатию и разрешению браузера `h3-js` преобразует GPS в resolution 8.
  В FastAPI отправляется только H3 в JSON body. Используется возвращённый anchor.
  При отказе, ошибке или отсутствии близкого anchor остаётся ручной выбор.
  Ручной выбор отменяет применение запоздавшего результата геолокации.
- GPS/H3 не записываются в localStorage/sessionStorage, URL или аналитику;
  H3 живёт только в состоянии страницы и очищается пользователем/ручным выбором/перезагрузкой.
- Сохранены существующие компоненты и оформление. Добавлены мобильный `dvh`,
  доступные названия полей и экранирование внешних OSM-строк в popup карты.

## Реальный маршрут EXPO, 60 минут

Запрос из браузера: EXPO / Nur Alem, «Хочу спокойную прогулку возле EXPO»,
`duration_minutes=60`, `round_trip=true`, `language=ru`.

Цепочка проверена: Chrome → Vite :5173 `/api` → FastAPI :8000 → live ORS
→ ответ → карточки, сводка и MapLibre.

| Поле | Реальный результат |
| --- | --- |
| HTTP/status | `200 / success` |
| Provenance Directions | `openrouteservice`, `foot-walking`, `mode=live` |
| Остановки | 3 |
| ORS GeoJSON | LineString, 56 координат |
| Расстояние | 858,6 м |
| Пешее время | 10,3017 мин |
| Плановые посещения | 40 мин |
| Суммарное время | 50,3017 мин, в пределах 60 мин |
| POI | `osm:node:13408473356`, `osm:way:1452597370`, `osm:node:11993865901` |

У второго POI нет имени в OSM — интерфейс показывает отсутствие имени.
Warnings о непроверенных входах, доступности, пожеланиях и плановых визитах сохранены.
Геометрия и все четыре маркера визуально проверены на desktop и 390×844.
После исправления worker в live-сценарии нет console errors или page errors.

Live Weather через тот же proxy: `200 / available`, 10,0 °C, ветер 20,7 км/ч,
`weather_model_estimate_not_station_observation`. Значения актуальны только для момента запроса.

## Выполненные проверки

| Проверка | Результат / границы |
| --- | --- |
| `npm ci` | PASS, включая повтор после изменения lockfile; 0 известных vulnerabilities по npm audit |
| `npm run lint` | PASS |
| `npm run build` | PASS, TypeScript + Vite; worker emitted как отдельный `.mjs` |
| Backend `python -m pytest -q` | 315 passed; 2 upstream deprecation warnings |
| Playwright, live opt-in | 9 passed, Chrome; live ORS-тест не пропущен |
| HTTP backend URL в production | Сборка отклонена ожидаемой ошибкой |
| HTTPS backend URL с `/api/` | Сборка успешна, URL присутствует в emitted bundle |
| FastAPI CORS preflight | Настроенный `https://viberoute.example`: HTTP 200 с точным allow-origin; посторонний origin: HTTP 400 без allow-origin |
| Production bundle в preview :4173 | Hashed worker HTTP 200, live backend success, 3 stops, 0 browser errors; линия проверена визуально |
| ORS-ключ в bundle | Значение настоящего backend-ключа не найдено ни в одном файле dist; значение не выводилось |
| Удалённые client-конфигурация/данные | В dist нет клиентского имени ORS-переменной, `127.0.0.1:8000` и прежнего фиксированного H3 |

Сценарии Playwright:

1. Начальная загрузка без маршрута, демо, H3 и demo-изохроны.
2. Настоящий EXPO 60 минут через FastAPI/ORS, сводка, stops/warnings, worker, desktop/mobile.
3. `no_route / unreachable` из реального FastAPI при симулированном upstream ORS error 2010;
   geometry null, stops пустые, предыдущий демомаршрут удалён.
4. `no_route / ors_unavailable` из реального FastAPI при симулированном ORS HTTP 403;
   без демо и старой геометрии.
5. Отказ соединения frontend → API: видимое сообщение; демо только после явного выбора.
6. Отказ Open-Meteo в тестовом HTTP-транспорте: настоящий FastAPI возвращает `unknown/null`.
7. Симулированный частичный погодный ответ: null, нулевой ветер, предупреждение;
   отдельно ошибка соединения frontend → Weather API.
8. Отказ браузерного разрешения геолокации: H3-запрос не отправляется, ручной выбор работает.
9. Синтетический GPS в браузере с разрешением → валидный H3 res 8 → настоящий Privacy API
   → возвращённый anchor. Body содержит только `h3_cell`, query пустая.
   Проверено отсутствие H3/GPS в browser storage и URL, очистка и сброс после reload.

## Воспроизведение и ограничения

Инструкции: [apps/web/README.md](../apps/web/README.md).
E2E находятся в `apps/web/e2e`, тестовые fault-серверы запускаются автоматически.
Для live-проверки задайте `RUN_LIVE_ORS=1`; в этой проверке использован
`PLAYWRIGHT_CHANNEL=chrome`. Скриншоты Playwright остаются локально в игнорируемом
`apps/web/test-results`; live API evidence и production screenshot — в игнорируемом
`data/tmp/frontend-verification`. Они не содержат ключей и не добавлены в Git.

Проверки отказов ORS/Open-Meteo детерминированно симулировали внешний сбой через
`httpx.MockTransport`, сохраняя настоящие FastAPI routers, adapter, planner и dataset.
Это не утверждение о наблюдавшемся live-отказе провайдера.
Геолокация проверена на тестовых координатах, не на физическом GPS пользователя.
Мобильная проверка выполнена в Chrome viewport 390×844, не на отдельном телефоне.

Опубликованный production deployment не проверялся. Для production smoke в preview
hosting `/api` reverse proxy был воспроизведён перехватом браузерного запроса с
переадресацией в настоящий локальный FastAPI. Отдельно проверены production HTTPS
configuration и серверный CORS; реальные домены и hosting proxy нужно настроить при выкладке.

Сборка сохраняет предупреждение Vite о JS chunk более 500 kB (MapLibre/H3).
Это не ошибка сборки; переписывание UI и отдельная оптимизация bundle в эту интеграцию не входили.
