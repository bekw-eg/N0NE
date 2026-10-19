# VibeRoute frontend

React, Vite, Tailwind и MapLibre. Сохранены три панели, карточки, таймлайн и мобильные вкладки.

## Локальный запуск

Из `apps/api` запустите настоящий FastAPI. ORS-ключ задаётся только серверу:

```sh
uv sync --locked --group dev
uv run python -m uvicorn app.main:app --env-file ../../.env --host 127.0.0.1 --port 8000 --no-access-log
```

Корневой `.env` должен содержать `ORS_API_KEY` и при необходимости `ORS_BASE_URL`.
Для Windows с не-ASCII путём сначала задайте настройки из [backend README](../api/README.md).

В другом терминале, из `apps/web`:

```sh
npm ci
npm run dev
```

Откройте `http://localhost:5173`. В development все запросы идут на `/api/v1/...`
через [Vite proxy](https://vite.dev/config/server-options.html#server-proxy) к `127.0.0.1:8000`.
`VITE_API_BASE_URL` в development не используется. Порт занят — Vite завершится,
а не переключится на другой порт незаметно.

## Production и CORS

При сборке задайте `VITE_API_BASE_URL=https://your-backend.example`.
Также поддерживается завершающий `/api`. `/api/v1` указывать не нужно.
HTTP URL, URL с credentials, query, fragment или посторонним путём отклоняются сборкой.
Пустое значение или `/api` означает same-origin API: настройте HTTPS reverse proxy
хостинга на FastAPI, сохраняя путь `/api/v1/...`. Vite dev proxy не входит в production build.

На FastAPI задайте `CORS_ORIGINS=["https://your-frontend.example"]` — точный origin
опубликованного frontend без пути и завершающего `/`. Middleware уже поддерживает
GET/POST и Content-Type preflight, без credentials и wildcard.
Для разных доменов оба сервиса должны быть доступны по HTTPS.
См. [FastAPI CORS](https://fastapi.tiangolo.com/tutorial/cors/).

В переменные `VITE_*` нельзя помещать ключи: они публичны в браузерной сборке.
ORS вызывается только backend. Пример frontend-конфигурации — [.env.example](.env.example).

## Поведение

- Начальное состояние пустое. «Построить маршрут» вызывает `POST /api/v1/routes/plan`.
- Успех: настоящая ORS GeoJSON-линия, остановки, расстояние, пешее время,
  плановые визиты, общий бюджет и warnings из ответа API.
- «Прогулка возле парка с кофе»: обязательные этапы кофейня → парк/сад.
  Явное «сначала парк, потом кофе» меняет порядок. Если целая последовательность
  недоступна или не помещается в бюджет, возвращается `no_route` без подмены мест.
- `no_route`: объяснение, reason, warnings; геометрия и старые остановки удаляются.
- Причины и ограничения в UI показываются понятными фразами. При нехватке времени
  доступна кнопка «Изменить параметры»; длительность не увеличивается автоматически.
  Исходный парк может завершать прогулку после кофе, если это тот же OSM-объект.
- Ошибка сети/HTTP: видимое сообщение, повторная отправка доступна.
- Только «Показать демо» включает пример с пометкой «Демонстрационные данные».
  Новый запрос всегда обращается к API и сбрасывает демо. Демо-изохрона отсутствует в live-режиме.
- MapLibre ESM worker явно публикуется Vite как отдельный asset через
  [setWorkerUrl](https://maplibre.org/maplibre-gl-js/docs/API/functions/setWorkerUrl/),
  чтобы линия и векторные тайлы загружались в dev и production.
- Погода запрашивается через `GET /api/v1/weather?start_anchor_id=...` при смене старта.
  `unknown`, `null`, нулевые значения, предупреждения и ошибки обрабатываются отдельно.
  Отказ погоды не блокирует планирование.
- Геолокация запрашивается только кнопкой и разрешением браузера. `h3-js`
  преобразует GPS в [H3 resolution 8](https://h3geo.org/docs/api/indexing/) на устройстве.
  `POST /api/v1/privacy/resolve-h3` получает только `{ "h3_cell": "…" }`;
  используется возвращённый `start_anchor_id`. При отказе/ошибке/неподдерживаемой области
  остаётся ручной выбор. H3 — приблизительная область, не гарантия анонимности.
- GPS/H3 не записываются в localStorage, sessionStorage, URL или аналитику.
  H3 хранится в React state до очистки, ручного выбора или перезагрузки страницы.

## Проверки

```sh
npm run lint
npm run build
npx playwright install chromium
npm run test:e2e
```

Перед E2E должны работать Vite :5173 и FastAPI :8000. Тестовые FastAPI :8001/:8002
запускаются Playwright автоматически: реальные routers/planner/adapter используют
симулированные upstream ORS/Open-Meteo отказы. Эти серверы не входят в приложение.
Нужны Python/uv и зависимости backend.

Live ORS проверка явно включается `RUN_LIVE_ORS=1` (ключ остаётся в backend).
PowerShell: `$env:RUN_LIVE_ORS='1'; npm run test:e2e`.
Для установленного Chrome вместо скачанного Chromium: `PLAYWRIGHT_CHANNEL=chrome`.
Без opt-in live-тест пропускается; остальные сценарии проверяют сбои, ручное демо,
погоду и геолокацию с синтетическими GPS-координатами.

Результаты и границы выполненной проверки: [frontend integration report](../../docs/frontend-integration-report.md).
