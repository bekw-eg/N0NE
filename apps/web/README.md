# VibeRoute Web Application (Frontend)

Фронтенд-приложение и интерактивная карта для VibeRoute — интеллектуального генератора персонализированных городских маршрутов по Астане.

Разработано в рамках роли **Developer №3A (Frontend UI & Interactive Map Engineer)**.

## Архитектура и зоны ответственности

- **Левая панель (Параметры и управление)**:
  - Выбор каталожного анкора старта (`shared/anchors.json`): Mega Silk Way, EXPO / Nur Alem, Ботанический сад, Бульвар Нуржол.
  - Ввод естественного запроса/пожеланий к маршруту.
  - Слайдер длительности прогулки (30–180 минут) и переключатель кольцевого маршрута.
  - Предоставлены готовые точки расширения для модулей **Developer №3B** (сценарии, фильтры прозрачности, выбор языка `ru|kk|en`).
- **Центральная панель (Рекомендации и таймлайн)**:
  - `RecommendationCard.tsx`: отображение названия, категории, адреса, плановой длительности визита, источника подбора (`retrieval` vs `nearby_fallback`), проверенных атрибутов OSM и ссылок на источник.
  - `RouteTimeline.tsx`: хронологическая последовательность точек маршрута (Старт -> POI 1..N -> Завершение).
  - Состояния: загрузка (скелетон), ошибка API с рекомендацией, `no_route` с понятным объяснением причины (бюджет времени, недостижимость).
  - Сводка маршрута: общее время, время пешком, время визитов, суммарная дистанция.
- **Правая панель (Интерактивная карта MapLibre GL JS)**:
  - `MapView.tsx`:
    - Карта Астаны на MapLibre GL JS с темной неоновой темой и автоматическим fallback на OpenStreetMap raster tiles.
    - Отображение начальной точки (анкора) с пульсирующим маркером.
    - Нумерованные маркеры POI (#1, #2, #3) с категорией и всплывающими подсказками.
    - Пешеходная геометрия маршрута (LineString GeoJSON) со стилизованным неоновым свечением.
    - Отображение зоны доступности / изохроны (Polygon GeoJSON) при наличии данных.
    - Отображение приблизительного местоположения пользователя через H3-гексагон (без передачи и раскрытия точного GPS).
    - Автоматический `fitBounds` при смене маршрута и `flyTo` при выборе карточки или точки таймлайна.
    - Поддержка ресайза экрана (`ResizeObserver`).

## Синхронизация состояний

- Клик по карточке места -> активирует соответствующий маркер на карте и подсвечивает точку в таймлайне.
- Клик по маркеру на карте -> выбирает соответствующую карточку и фокусирует в списке.
- Клик по шагу в таймлайне -> фокусирует маркер на карте.
- При получении нового маршрута устаревшее выделение сбрасывается.

## Интерфейс интеграции для Developer №3B

Developer №3B подключает свой `useVibeRoute` хук / API клиент:
1. Типы контракта согласованы в [`src/types/api.ts`](src/types/api.ts) и на 100% повторяют Pydantic схемы backend (`apps/api/app/schemas/routes.py`).
2. Props компонентов:
   - `MapView`:
     - `stops: RouteStop[]`
     - `selectedStopId?: string | null`
     - `startAnchor?: Anchor | null`
     - `routeGeoJSON?: RouteGeoJSON | null`
     - `isochronesGeoJSON?: FeatureCollection | null`
     - `userH3Cell?: string | null`
     - `onSelectStop?: (stop: RouteStop) => void`
     - `onSelectAnchor?: (anchor: Anchor) => void`
   - `RecommendationCard`:
     - `stop: RouteStop`
     - `isSelected?: boolean`
     - `onSelect?: (stop: RouteStop) => void`
   - `RouteTimeline`:
     - `stops: RouteStop[]`
     - `startAnchor?: Anchor | null`
     - `roundTrip?: boolean`
     - `selectedStopId?: string | null`
     - `onSelectStop?: (stop: RouteStop) => void`
     - `onSelectAnchor?: (anchor: Anchor) => void`
     - `walkingMinutes?: number | null`
     - `totalDistanceMeters?: number | null`

## Запуск и сборка

```sh
cd apps/web

# Установка зависимостей (при первом запуске)
npm install

# Запуск dev-сервера
npm run dev

# Проверка линтером (oxlint)
npm run lint

# Сборка production bundle и typecheck
npm run build
```
