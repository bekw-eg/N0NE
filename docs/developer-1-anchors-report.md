# VibeRoute — Geo Anchors & Walking Accessibility

Роль: Developer №1 — Data & Geo Engineer. Ветка: `feature/data-geo-anchors`.
База: `origin/main`, `793e5ad`. Авторство взято из существующего Git config.

Результат: четыре обоснованных ориентира Астаны, реальные проверки HeiGIT
`foot-walking`, отдельные captures и воспроизводимое offline demo. Основной
POI dataset, FastAPI/RAG, Web UI, H3, Open-Meteo и исторические ORS captures
не изменены. Merge в `main` не выполняется.

## Ориентиры и источники

Координаты ниже записаны как **latitude, longitude**. В GeoJSON и ORS порядок
обратный: **longitude, latitude**. Исходные ответы официального OSM API получены
19 октября 2026 года; точные `retrieved_at`, `osm_updated_at`, версии объектов,
теги и принадлежность узлов контурам сохранены в `data/geo/anchors/sources/`.

| ID | Зона / выбранная точка | Latitude | Longitude | Тип / вход |
|---|---|---:|---:|---|
| `mega_silk_way` | Mega Silk Way, вход E | 51.0887669 | 71.4107868 | `mapped_entrance` / `osm_mapped` |
| `botanical_garden` | Ботанический сад | 51.1061652 | 71.4165705 | `bounding_box_center` / `unknown` |
| `expo_nur_alem` | EXPO / Nur Alem, в OSM — Alem.ai | 51.0892520 | 71.4161925 | `bounding_box_center` / `unknown` |
| `nurzhol_boulevard` | Нуржол, указатель Нуржол–Керуен | 51.1291028 | 71.4252821 | `osm_node` / `unknown` |

- Mega E: [OSM node 13404024647](https://www.openstreetmap.org/node/13404024647),
  версия 1, `entrance=main`, `ref=E`. Узел входит в контур
  [way 499328514](https://www.openstreetmap.org/way/499328514), версия 16.
  Дополнительный вход F:
  [node 5761275928](https://www.openstreetmap.org/node/5761275928), версия 5,
  `entrance=main`, `ref=F`; latitude 51.0896974, longitude 71.4084803,
  ID `mega_silk_way_entrance_f`. Принадлежность обоих узлов зданию проверяется
  тестами по полному ответу `sources/mega.json`.
- Ботанический сад:
  [way 1196402246](https://www.openstreetmap.org/way/1196402246), версия 15.
  Центр вычислен из min/max координат узлов контура и совпадает с прежним
  ориентиром. Входы среди полученных узлов контура не размечены. Это ограниченная
  проверка: она не исключает входы вне контура, рядом с ним или вне OSM.
- EXPO / Nur Alem:
  [way 454857501](https://www.openstreetmap.org/way/454857501), версия 15.
  Центр ограничивающего прямоугольника текущего OSM-контура, не вход и не центроид
  полигона. В текущем OSM название `Alem.ai`. Связь нового центра с Nur Alem
  описана в [публикации профильного министерства](https://www.gov.kz/memleket/entities/maidd/press/news/details/901676).
  Историческое имя зоны сохранено; работа прежнего музея из него не выводится.
- Нуржол:
  [node 13503066248](https://www.openstreetmap.org/node/13503066248), версия 2,
  `tourism=information`, `information=guidepost`, `operator=Astana Tourism`,
  описание «Указатель Нуржол - Керуен». Это конкретный ориентир на бульваре,
  не центр всего бульвара и не вход в ближайшее здание.

Источники получены через `https://api.openstreetmap.org/api/0.6/`: `way/.../full.json`
для трёх контуров и `node/...json` для указателя. Discovery-запрос Overpass
вернул HTTP 406, зеркало Kumi завершилось по timeout; для итоговых координат
использованы успешные ответы официального OSM API. Ошибки Overpass не подменены
искусственными данными. OSM attribution и [лицензия](https://www.openstreetmap.org/copyright)
сохранены в каждом source envelope.

## Что именно подтверждено

У всех четырёх точек `verification_status=source_verified`: координаты и metadata
сверены с сохранённым OSM-объектом. Это не независимое обследование на месте.
У Mega E/F подтверждены **OSM-разметка входа и принадлежность контуру здания**.
Не подтверждены право прохода, фактическое открытие дверей и безбарьерный доступ.
У остальных трёх ориентиров вход явно `unknown`.

У всех точек `opening_status=unknown`, `accessibility_status=unknown`.
Расписание здания Mega сохранено в исходных OSM-тегах, но не интерпретируется
как подтверждение текущего открытия. `stroller=yes` не используется как
доказательство доступности для пользователей колясок. Семантика входов следует
[документации OSM entrance](https://wiki.openstreetmap.org/wiki/Key:entrance).

Каталог `0.2.0` сохраняет существующие ID. У `mega_silk_way` основная координата
заменена с центра здания на вход E; исходный контур и его metadata сохранены в
source snapshot, прежние координаты — в неизменённом историческом demo.
Реальные старые каталоги `0.1.0` загружаются с консервативными `unknown` defaults.
Положительные утверждения о mapped entrance требуют согласованных статусов,
OSM node URL, тега входа и ссылки на родительский объект. Дополнительные входы
должны ссылаться на тот же объект. Совместимость импортов `cli.Anchor`,
`cli.AnchorCatalog` сохранена; модели также экспортируются из `viberoute_geo`.
API методов `GeoAdapter` и существующие request/result contracts не изменены.

## Реальные результаты ORS / HeiGIT

Endpoint: `https://api.heigit.org/openrouteservice`, профиль `foot-walking`.
Сохранены **19 успешных запросов** за 19 октября 2026 года,
**16:17:27–16:17:33 UTC / 21:17:27–21:17:33 Asia/Qyzylorda**:

- 12 направленных Directions-запросов между всеми четырьмя зонами;
- четыре Isochrones-запроса, каждый с диапазонами 600/900 секунд;
- одна Matrix 4×4 с duration в секундах и distance в метрах;
- два Directions-запроса между входами E и F у Mega.

Все запросы прошли текущую валидацию GeoAdapter. Таблица направленных результатов
Directions приведена в `demo/manifest.json`; пары в этом конкретном snapshot
оказались симметричными. Код и тесты симметрию не предполагают.

| Directions | Расстояние, м | Время, с | Время, мин |
|---|---:|---:|---:|
| Mega E → Ботанический сад | 2173.5 | 1564.9 | 26.08 |
| Mega E → EXPO | 435.0 | 313.2 | 5.22 |
| Mega E → Нуржол | 5030.4 | 3621.8 | 60.36 |
| Ботанический сад → EXPO | 2211.8 | 1592.5 | 26.54 |
| Ботанический сад → Нуржол | 3061.9 | 2204.5 | 36.74 |
| EXPO → Нуржол | 4986.6 | 3590.3 | 59.84 |
| Mega E → Mega F | 332.5 | 239.4 | 3.99 |

Матрица ниже содержит исходные Matrix-значения **метры / секунды**.
Порядок строк и столбцов: Mega, сад, EXPO, Нуржол. Небольшие отличия от таблицы
Directions связаны с точностью возвращаемых provider-значений.

| Откуда / куда | Mega E | Сад | EXPO | Нуржол |
|---|---:|---:|---:|---:|
| Mega E | 0 / 0 | 2173.55 / 1564.93 | 434.97 / 313.16 | 5030.44 / 3621.84 |
| Сад | 2173.55 / 1564.93 | 0 / 0 | 2211.79 / 1592.46 | 3061.91 / 2204.53 |
| EXPO | 434.97 / 313.16 | 2211.79 / 1592.46 | 0 / 0 | 4986.56 / 3590.25 |
| Нуржол | 5030.44 / 3621.84 | 3061.91 / 2204.53 | 4986.56 / 3590.25 | 0 / 0 |

Provider snapping distances из Matrix: Mega E **31.54 м**, сад **8.26 м**,
EXPO **45.34 м**, Нуржол **3.63 м**. Для Directions отдельно рассчитаны
great-circle offsets от запрошенных координат до концов возвращённой геометрии:
31.55 / 8.30 / 45.34 / 3.61 м соответственно; у Mega F — 10.51 м.
Эти вычисления служат только измерением смещения. Они не создают пешеходный
маршрут и не добавляются к его длине или времени. Для Directions задан радиус
snapping 100 м; Matrix хранит собственные provider snapping results.

Graph date ORS: `2026-09-20T06:31:34Z`; underlying OSM date:
`2026-09-13T23:59:59Z`. Это более ранний граф, чем текущие OSM API snapshots.
Все metadata, исходные timestamps и attribution
**openrouteservice.org | OpenStreetMap contributors** сохранены.

## Offline demo и использование Developer №2 / №3

Из корня репозитория:

```powershell
uv run --project packages/geo python scripts/geo_smoke.py --all-anchors --mode recorded --output-dir data/tmp/anchors-replayed
```

Команда выполнена успешно без ключа и без сетевых запросов. Полученные геометрия,
метрики и source metadata совпадают с реальными captures; режим становится
`recorded`, исходное время получения остаётся прежним. Default age limit —
86400 секунд. Для более позднего намеренного исторического demo необходимо
явно указать `--max-recording-age-seconds`, сохраняя label и timestamps.

Свежий live capture в отдельный каталог:

```powershell
uv run --project packages/geo --env-file .env python scripts/geo_smoke.py --all-anchors --mode live --recordings-dir data/tmp/anchors-live/recordings --output-dir data/tmp/anchors-live/demo
```

Developer №2: загружать `AnchorCatalog` из `shared/anchors.json`, выбирать точки
по ID и передавать `anchor.location` существующему GeoAdapter. Не кешировать
координату только по стабильному ID без учёта обновления каталога. Сохранять
`GeoError`, paired nulls в Matrix, режим, timestamp и attribution. Исторические
recordings совпадают только с исходными координатами; прежний центр Mega нельзя
заменить входом E в уже записанном запросе. Legacy-тесты используют сохранённые
исходные anchors и продолжают проверять endpoint, возраст и целостность.

Developer №3: читать `demo/manifest.json` и `anchor_ids` для порядка матрицы.
Использовать только файлы успешных checks; при ошибке check содержит
`status=error`, `result=null` и sanitized error, а путь к геометрии отсутствует.
Независимые операции продолжаются; CLI возвращает exit code 2 при любой ошибке.
Отображать `live`/`recorded`, дату и attribution. На карте различать OSM-mapped
вход, bounding-box center и обычный OSM node. Не показывать центры как входы
и не включать бейджи текущего открытия или доступности по этим данным.

`--all-anchors` хранит новые captures в `data/geo/anchors/recordings/`.
Обычный двухточечный smoke по умолчанию пишет в `data/tmp/geo-smoke/`, чтобы
обновлённый каталог не перезаписал исторический demo. Явные пути поддерживаются.
Исторический двухточечный offline demo также проверен; инструкция экспорта его
исходного каталога находится в `data/geo/README.md`.

## Проверки

- **137 geo/integration tests passed**: исходные 78 и 59 новых случаев.
- **39 POI pipeline tests passed**. Всего **176 passed**.
- Geo Ruff lint и Ruff format check: passed, включая новые тесты и smoke script.
- Strict mypy: passed, девять файлов geo/source + smoke + существующий API facade.
- Дополнительно POI format check и mypy: passed. Более широкая проверка Ruff
  неизменённых POI tests обнаружила три существующих `I001` в `conftest.py`,
  `test_normalize.py`, `test_overpass.py`; эти файлы идентичны `origin/main` и
  в рамках geo-задачи не изменялись. Это не ошибка затронутого geo-кода.
- POI validation с независимым replay raw capture и сравнением полного GeoJSON:
  `valid=true`, `pois=497`, `source_replayed=true`.
- Новые реальные captures: exact-request/profile/endpoint/hash/age replay,
  полное совпадение экспортов и provenance, запрет сети в offline tests.
- SHA-256 всех трёх исторических captures и четырёх historical demo-файлов
  совпадают с исходными значениями. Рабочее дерево этих файлов не изменено.
- Shapely QA: 18 GeoJSON-файлов, 22 геометрии, все valid и nonempty.
  Shapely использован отдельно через `uv --with`, без изменения зависимостей.
- Моки проверяют недоступные маршруты, malformed Matrix 4×4, асимметрию,
  paired nulls, частичный сбой сценария и отсутствие подставной геометрии.
- Выполнено на CPython 3.14; отдельный прогон CPython 3.11 не выполнялся.

Основные команды проверок:

```powershell
uv run --project packages/geo python -m pytest packages/geo/tests tests/integration -q
uv run --project packages/data_pipeline python -m pytest packages/data_pipeline/tests -q
uv run --project packages/geo ruff check --config packages/geo/pyproject.toml packages/geo tests/integration scripts/geo_smoke.py
uv run --project packages/geo ruff format --check --config packages/geo/pyproject.toml packages/geo tests/integration scripts/geo_smoke.py
uv run --project packages/geo mypy --config-file packages/geo/pyproject.toml packages/geo/src scripts/geo_smoke.py apps/api/app/integrations/geo_adapter.py
uv run --project packages/data_pipeline python scripts/validate_data.py data/astana/pois.json --raw data/astana/overpass.capture.json --geojson data/astana/pois.geojson
```

## Изменённые файлы и ограничения

- `shared/anchors.json` — четыре ориентира, источник, тип, степень проверки,
  явные unknown-статусы, дополнительный вход и ограничения.
- `packages/geo/src/viberoute_geo/anchors.py`, `exports.py`, `scenario.py` —
  модели, общий JSON exporter и независимые проверки сценария.
- `packages/geo/src/viberoute_geo/cli.py`, `__init__.py` — CLI и публичные импорты.
- `packages/geo/tests/test_anchors.py`, `test_scenario.py`,
  `tests/integration/test_geo_anchors.py`, `test_geo.py` — новые проверки и
  сохранение исходных координат исторических запросов.
- `data/geo/anchors/` — README, четыре OSM source responses, 19 ORS captures,
  21 demo-файл, включая manifest и snapshot каталога.
- `README.md`, `packages/geo/README.md`, `data/geo/README.md` и этот отчёт.

Полевое обследование не выполнялось. Не подтверждены входы EXPO, сада и бульвара,
текущие открытия/закрытия, доступ для маломобильных пользователей, непрерывный
крытый проход и пешеходное соединение от исходной координаты до точки snapping.
Другие OSM-входы Mega сохранены в raw source, но live маршруты проверялись только
для выбранных E/F. Межзональные маршруты к другим неподтверждённым входам
не придумывались. Реальных unreachable-пар в этом snapshot не оказалось;
обработка таких случаев проверена моками. Время ORS — оценка пути по графу,
не гарантия фактического времени прогулки или доступа на объект.
