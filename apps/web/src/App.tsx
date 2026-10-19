import React, { useRef, useState, useTransition } from 'react';
import { latLngToCell } from 'h3-js';
import { planRoute, resolveH3 } from './api/client';
import { WeatherCard } from './components/WeatherCard';
import { formatRouteWarnings, noRouteLabels } from './utils/routeMessages';
import {
  Compass,
  Navigation,
  Sliders,
  Sparkles,
  AlertCircle,
  RotateCcw,
  Footprints,
  Info,
  ExternalLink,
  ShieldCheck,
} from 'lucide-react';


import { MapView } from './components/MapView';
import { RecommendationCard } from './components/RecommendationCard';
import { RouteTimeline } from './components/RouteTimeline';
import {
  DEMO_ANCHORS,
  DEMO_ROUTE_PLAN,
  DEMO_ISOCHRONES_GEOJSON,
} from './data/fixtures';
import type {
  Anchor,
  AnchorID,
  RouteStop,
  RoutePlanResponse,
  RoutePlanRequest,
} from './types/api';

export const App: React.FC = () => {
  // Mobile Tab State: 'controls' | 'recommendations' | 'map'
  const [activeTab, setActiveTab] = useState<'controls' | 'recommendations' | 'map'>('controls');

  // Route planning inputs.
  const [selectedAnchorId, setSelectedAnchorId] = useState<AnchorID>('mega_silk_way');
  const [query, setQuery] = useState('Хочу спокойную прогулку возле парка с кофе');
  const [durationMinutes, setDurationMinutes] = useState<number>(60);
  const [roundTrip, setRoundTrip] = useState<boolean>(true);

  // Application State
  const [planResponse, setPlanResponse] = useState<RoutePlanResponse | null>(null);
  const [selectedStopId, setSelectedStopId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [apiError, setApiError] = useState<string | null>(null);
  const [isDemoFixture, setIsDemoFixture] = useState<boolean>(false);
  const [userH3Cell, setUserH3Cell] = useState<string | null>(null);
  const [locationMessage, setLocationMessage] = useState<string | null>(null);
  const [isLocating, setIsLocating] = useState(false);
  const locationRequest = useRef(0);

  const [, startTransition] = useTransition();

  const activeAnchor =
    DEMO_ANCHORS.find((a) => a.id === selectedAnchorId) || DEMO_ANCHORS[0];

  // Synchronize selection between cards, timeline, and map
  const handleSelectStop = (stop: RouteStop) => {
    startTransition(() => {
      setSelectedStopId(stop.id);
      // On mobile, if clicked in timeline or cards, user can switch to map
    });
  };

  const handleSelectAnchor = (_anchor: Anchor) => {
    // Focus start anchor
    setSelectedStopId(null);
  };

  const clearPlan = () => {
    setPlanResponse(null);
    setSelectedStopId(null);
    setIsDemoFixture(false);
    setApiError(null);
  };

  const selectManualAnchor = (anchorId: AnchorID) => {
    locationRequest.current += 1;
    setIsLocating(false);
    setUserH3Cell(null);
    setLocationMessage(null);
    setSelectedAnchorId(anchorId);
    clearPlan();
  };

  const handleUseLocation = () => {
    const requestId = ++locationRequest.current;
    setUserH3Cell(null);
    if (!navigator.geolocation || !window.isSecureContext) {
      setLocationMessage('Геолокация недоступна. Выберите точку старта вручную.');
      return;
    }
    setIsLocating(true);
    setLocationMessage('Ожидание разрешения на геолокацию…');
    navigator.geolocation.getCurrentPosition(async ({ coords }) => {
      if (requestId !== locationRequest.current) return;
      try {
        // GPS exists only in this callback; only the resolution-8 cell leaves the device.
        const cell = latLngToCell(coords.latitude, coords.longitude, 8);
        const result = await resolveH3(cell);
        if (requestId !== locationRequest.current) return;
        if (result.status === 'matched') {
          setSelectedAnchorId(result.start_anchor_id);
          setUserH3Cell(cell);
          clearPlan();
          setLocationMessage(`Старт выбран по приблизительной области H3: около ${result.distance_estimate_m} м по прямой от центра ячейки, не пешее расстояние.`);
        } else {
          setLocationMessage('Рядом нет поддерживаемой точки старта. Выберите её вручную.');
        }
      } catch {
        if (requestId === locationRequest.current) setLocationMessage('Не удалось определить точку старта. Выберите её вручную.');
      } finally {
        if (requestId === locationRequest.current) setIsLocating(false);
      }
    }, (error) => {
      if (requestId !== locationRequest.current) return;
      setIsLocating(false);
      setLocationMessage(error.code === 1
        ? 'Доступ к геолокации отклонён. Выберите точку старта вручную.'
        : 'Геолокация недоступна. Выберите точку старта вручную.');
    }, { enableHighAccuracy: false, timeout: 15000, maximumAge: 0 });
  };

  // Every submission requests the real backend. Demo is an explicit separate choice.
  const handlePlanRoute = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!query.trim() || isLoading || isLocating) return;

    clearPlan();
    setIsLoading(true);
    setActiveTab('recommendations');

    const payload: RoutePlanRequest = {
      start_anchor_id: selectedAnchorId,
      duration_minutes: durationMinutes,
      query: query.trim(),
      round_trip: roundTrip,
      language: 'ru',
    };

    try {
      const data = await planRoute(payload);
      setPlanResponse(data);
      setIsDemoFixture(false);
      if (data.status === 'success' && data.stops.length > 0) {
        setSelectedStopId(data.stops[0].id);
      } else {
        setSelectedStopId(null);
      }
    } catch (err: unknown) {
      setApiError(err instanceof Error ? err.message : 'Не удалось построить маршрут. Повторите попытку.');
    } finally {
      setIsLoading(false);
    }
  };

  // Quick preset triggers for Astana walking vibes
  const handleApplyPreset = (text: string, anchorId: AnchorID, duration: number) => {
    setQuery(text);
    selectManualAnchor(anchorId);
    setDurationMinutes(duration);
  };

  const isSuccess = planResponse?.status === 'success';
  const successPlan = planResponse?.status === 'success' ? planResponse : null;
  const unavailablePlan = planResponse?.status === 'no_route' ? planResponse : null;
  const routeWarnings = formatRouteWarnings(planResponse?.warnings ?? []);

  return (
    <div className="flex h-dvh w-full flex-col overflow-hidden bg-slate-950 text-slate-100">
      {/* Top Navigation Bar */}
      <header className="flex h-14 shrink-0 items-center justify-between border-b border-slate-800/80 bg-slate-900/80 px-4 md:px-6 backdrop-blur-md z-30">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-tr from-cyan-500 to-indigo-600 text-slate-950 font-black shadow-md shadow-cyan-500/20">
            <Footprints className="h-5 w-5 text-white" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold tracking-tight text-slate-100 font-heading text-base">
                VibeRoute
              </span>
              <span className="rounded-full bg-cyan-950/80 border border-cyan-800/60 px-2 py-0.2 text-[10px] font-semibold text-cyan-300">
                Astana
              </span>
            </div>
            <p className="hidden sm:block text-[10px] text-slate-400">
              Персонализированные городские пешеходные микромаршруты
            </p>
          </div>
        </div>

        {/* Header Right Badges & Controls */}
        <div className="flex items-center gap-2 sm:gap-3 text-xs">
          {/* H3 Privacy Cell Badge */}
          <div className="hidden lg:flex items-center gap-1.5 rounded-lg border border-slate-800 bg-slate-900/60 px-2.5 py-1 text-slate-300">
            <span className="h-2 w-2 rounded-full bg-cyan-400"></span>
            <span className="text-[11px] text-slate-400">Старт:</span>
            <span className="text-[11px] text-cyan-300">{userH3Cell ? 'Приблизительная область H3' : 'Ручной выбор'}</span>
          </div>

          {/* Mode Switcher / Demo Notice */}
          <div className="flex items-center gap-1.5 rounded-lg border border-slate-800 bg-slate-900/60 px-2.5 py-1">
            <span
              className={`h-2 w-2 rounded-full ${
                isDemoFixture ? 'bg-amber-400' : 'bg-emerald-400'
              }`}
            ></span>
            <span className="text-[11px] font-medium text-slate-300">
              {isDemoFixture ? 'Демонстрационные данные' : apiError ? 'Ошибка API' : planResponse ? 'Ответ API' : 'Ожидание API'}
            </span>
          </div>

          {/* Demo requires an explicit user choice. */}
          <button
            type="button"
            disabled={isLoading || isLocating}
            onClick={() => {
              if (isDemoFixture) {
                clearPlan();
              } else {
                selectManualAnchor(DEMO_ROUTE_PLAN.start_anchor_id);
                setPlanResponse(DEMO_ROUTE_PLAN);
                setSelectedStopId(DEMO_ROUTE_PLAN.stops[0].id);
                setIsDemoFixture(true);
              }
            }}
            className="flex items-center gap-1 rounded-lg border border-slate-700/60 bg-slate-800/80 px-2 py-1 text-[11px] text-slate-300 hover:bg-slate-700 transition-colors"
          >
            {isDemoFixture ? 'Выйти из демо' : 'Показать демо'}
          </button>
        </div>
      </header>

      {/* Main 3-Column Responsive Work Area */}
      <div className="relative flex flex-1 overflow-hidden">
        {/* ========================================================================= */}
        {/* 1. LEFT PANEL: CONTROLS & SCENARIO SELECTION */}
        {/* ========================================================================= */}
        <aside
          className={`flex flex-col border-r border-slate-800/80 bg-slate-950/95 overflow-y-auto z-20 transition-all duration-300 ${
            activeTab === 'controls' ? 'flex-1 w-full lg:flex-none lg:w-80 xl:w-96' : 'hidden lg:flex lg:w-80 xl:w-96'
          }`}
        >
          <fieldset disabled={isLoading} className="p-4 sm:p-5 space-y-5 min-w-0">
            {/* Panel Title */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Sliders className="h-4 w-4 text-cyan-400" />
                <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-200">
                  Параметры прогулки
                </h2>
              </div>
              <span className="text-[10px] text-slate-500">FastAPI & ORS</span>
            </div>

            {/* Quick Vibe Presets */}
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-slate-400">Быстрые сценарии:</label>
              <div className="flex flex-wrap gap-1.5">
                <button
                  type="button"
                  onClick={() =>
                    handleApplyPreset(
                      'Спокойная прогулка у парка с кофе',
                      'mega_silk_way',
                      60
                    )
                  }
                  className="rounded-lg border border-slate-800 bg-slate-900/80 px-2.5 py-1 text-xs text-slate-300 hover:border-cyan-500/50 hover:text-cyan-300 transition-colors"
                >
                  🌿 Парк и кофе (60м)
                </button>
                <button
                  type="button"
                  onClick={() =>
                    handleApplyPreset(
                      'Архитектура EXPO и искусство',
                      'expo_nur_alem',
                      45
                    )
                  }
                  className="rounded-lg border border-slate-800 bg-slate-900/80 px-2.5 py-1 text-xs text-slate-300 hover:border-cyan-500/50 hover:text-cyan-300 transition-colors"
                >
                  🌐 EXPO & Музей (45м)
                </button>
                <button
                  type="button"
                  onClick={() =>
                    handleApplyPreset(
                      'Бульвар Нуржол и смотровые площадки',
                      'nurzhol_boulevard',
                      90
                    )
                  }
                  className="rounded-lg border border-slate-800 bg-slate-900/80 px-2.5 py-1 text-xs text-slate-300 hover:border-cyan-500/50 hover:text-cyan-300 transition-colors"
                >
                  🏙️ Нуржол тур (90м)
                </button>
              </div>
            </div>

            {/* Start Anchor Selection Form */}
            <form onSubmit={handlePlanRoute} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1.5">
                  Каталожный анкор старта
                </label>
                <select
                  value={selectedAnchorId}
                  id="start-anchor"
                  aria-label="Каталожный анкор старта"
                  onChange={(e) => selectManualAnchor(e.target.value as AnchorID)}
                  className="w-full rounded-xl border border-slate-700/80 bg-slate-900 px-3 py-2 text-xs text-slate-100 outline-none focus:border-cyan-400 focus:ring-1 focus:ring-cyan-400 transition-colors"
                >
                  {DEMO_ANCHORS.map((anchor) => (
                    <option key={anchor.id} value={anchor.id}>
                      {anchor.name}
                    </option>
                  ))}
                </select>
                <div className="mt-1 flex items-center gap-1 text-[10px] text-slate-500">
                  <Info className="h-3 w-3" />
                  <span>
                    {activeAnchor.coordinate_kind === 'mapped_entrance'
                      ? 'Вход подтверждён в OSM (ref E)'
                      : 'Координаты центра объекта (не вход)'}
                  </span>
                </div>
              </div>

              <div className="rounded-xl border border-slate-800 p-3 space-y-2">
                <button type="button" onClick={handleUseLocation} disabled={isLocating} className="text-xs text-cyan-300 disabled:opacity-50">
                  {isLocating ? 'Определение точки старта…' : 'Выбрать старт по моей геолокации'}
                </button>
                <p className="text-[10px] text-slate-400">Добровольно: GPS преобразуется на устройстве в H3 resolution 8. В API отправляется только ID ячейки; он раскрывает приблизительную область. Местоположение не сохраняется.</p>
                {locationMessage && <p role="status" className="text-[11px] text-amber-200">{locationMessage}</p>}
                {userH3Cell && <button type="button" onClick={() => selectManualAnchor(selectedAnchorId)} className="text-[11px] text-cyan-300">Очистить местоположение</button>}
              </div>

              {/* Natural Language Preference Query */}
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1.5">
                  Пожелания к маршруту
                </label>
                <textarea
                  aria-label="Пожелания к маршруту"
                  maxLength={1000}
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  rows={3}
                  placeholder="Опишите желаемое настроение или типы мест..."
                  className="w-full rounded-xl border border-slate-700/80 bg-slate-900 p-2.5 text-xs text-slate-100 placeholder-slate-500 outline-none focus:border-cyan-400 focus:ring-1 focus:ring-cyan-400 transition-colors resize-none"
                />
              </div>

              {/* Duration Slider (30 to 180 min) */}
              <div>
                <div className="flex items-center justify-between mb-1.5 text-xs">
                  <span className="font-medium text-slate-300">Длительность</span>
                  <span className="font-mono font-bold text-cyan-400">
                    {durationMinutes} минут
                  </span>
                </div>
                <input
                  type="range"
                  aria-label="Длительность"
                  min={30}
                  max={180}
                  step={5}
                  value={durationMinutes}
                  onChange={(e) => setDurationMinutes(Number(e.target.value))}
                  className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-cyan-400"
                />
                <div className="flex justify-between text-[10px] text-slate-500 mt-1">
                  <span>30 мин</span>
                  <span>60 мин</span>
                  <span>120 мин</span>
                  <span>180 мин</span>
                </div>
              </div>

              {/* Round Trip Checkbox */}
              <label className="flex items-center gap-2.5 cursor-pointer text-xs text-slate-300 select-none">
                <input
                  type="checkbox"
                  checked={roundTrip}
                  onChange={(e) => setRoundTrip(e.target.checked)}
                  className="h-4 w-4 rounded border-slate-700 bg-slate-900 text-cyan-500 focus:ring-cyan-400"
                />
                <span>Кольцевой маршрут (возврат к старту)</span>
              </label>

              {/* Submit Button */}
              <button
                type="submit"
                disabled={isLoading || isLocating || !query.trim()}
                className="w-full flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-cyan-500 to-indigo-600 px-4 py-2.5 text-xs font-semibold text-slate-950 hover:from-cyan-400 hover:to-indigo-500 transition-all shadow-md shadow-cyan-500/20 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isLoading ? (
                  <>
                    <RotateCcw className="h-4 w-4 animate-spin" />
                    <span>Построение маршрута...</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="h-4 w-4" />
                    <span>Построить маршрут</span>
                  </>
                )}
              </button>
            </form>

            <WeatherCard anchorId={selectedAnchorId} />

            <div className="rounded-xl border border-dashed border-slate-800 p-3 bg-slate-950/40">
              <div className="flex items-center gap-1.5 text-[11px] font-semibold text-slate-400 mb-1">
                <ShieldCheck className="h-3.5 w-3.5 text-cyan-400" />
                <span>Приватность местоположения</span>
              </div>
              <p className="text-[10px] text-slate-500 leading-relaxed">
                Ручной выбор всегда доступен. GPS и H3 не сохраняются в браузере, URL или аналитике.
              </p>
            </div>
          </fieldset>
        </aside>

        {/* ========================================================================= */}
        {/* 2. CENTER PANEL: RECOMMENDATIONS & ROUTE TIMELINE */}
        {/* ========================================================================= */}
        <main
          className={`flex flex-col border-r border-slate-800/80 bg-slate-950 overflow-y-auto z-10 transition-all duration-300 ${
            activeTab === 'recommendations' ? 'flex-1 w-full lg:flex-none lg:w-96 xl:w-[440px]' : 'hidden lg:flex lg:w-96 xl:w-[440px]'
          }`}
        >
          <div className="p-4 sm:p-5 space-y-4">
            {/* Panel Title & Status */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Navigation className="h-4 w-4 text-cyan-400" />
                <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-200">
                  Рекомендации
                </h2>
              </div>
              {isSuccess && (
                <span className="rounded-md bg-emerald-950/60 border border-emerald-800/50 px-2 py-0.5 text-[11px] font-medium text-emerald-300">
                  {successPlan?.stops.length} точек
                </span>
              )}
            </div>

            {/* Error Notification if any */}
            {apiError && (
              <div role="alert" className="rounded-xl border border-amber-500/30 bg-amber-950/30 p-3 text-xs text-amber-200 flex items-start gap-2">
                <AlertCircle className="h-4 w-4 text-amber-400 shrink-0 mt-0.5" />
                <div className="space-y-1">
                  <p>{apiError}</p>
                </div>
              </div>
            )}

            {isDemoFixture && <p role="status" className="rounded-xl border border-amber-500 bg-amber-950/60 p-3 text-sm font-semibold text-amber-200">Демонстрационные данные — пример маршрута, не ответ текущего API.</p>}
            {!isLoading && !planResponse && !apiError && <p className="text-xs text-slate-400">Выберите параметры и нажмите «Построить маршрут».</p>}

            {/* Loading Skeleton */}
            {isLoading && (
              <div className="space-y-3">
                <div className="h-20 rounded-xl bg-slate-900/60 animate-pulse border border-slate-800/80" />
                <div className="h-32 rounded-xl bg-slate-900/60 animate-pulse border border-slate-800/80" />
                <div className="h-32 rounded-xl bg-slate-900/60 animate-pulse border border-slate-800/80" />
              </div>
            )}

            {/* Unavailable / No Route State */}
            {!isLoading && unavailablePlan && (
              <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-5 text-center space-y-3">
                <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-full bg-slate-800 text-slate-400">
                  <Compass className="h-5 w-5" />
                </div>
                <h3 className="text-sm font-semibold text-slate-200">
                  {unavailablePlan.reason === 'budget_exceeded' ? 'Не хватает времени на весь маршрут' : 'Маршрут не может быть сформирован'}
                </h3>
                <p className="text-xs text-slate-400 leading-relaxed">
                  {unavailablePlan.recommendation ||
                    'В заданное время невозможно дойти до подходящих мест и вернуться к старту. Попробуйте увеличить бюджет времени.'}
                </p>
                <div className="inline-flex items-center gap-1.5 rounded-full bg-slate-800/80 px-2.5 py-1 text-[11px] text-slate-400 font-mono">
                  Причина: {noRouteLabels[unavailablePlan.reason]}
                </div>
                {unavailablePlan.reason === 'budget_exceeded' && (
                  <button type="button" onClick={() => setActiveTab('controls')} className="block mx-auto rounded-lg border border-cyan-700 px-3 py-2 text-xs text-cyan-300 hover:bg-cyan-950">
                    Изменить параметры
                  </button>
                )}
                {routeWarnings.map(warning => <p key={warning} className="text-[10px] text-amber-200">{warning}</p>)}
              </div>
            )}

            {/* Successful Route Presentation */}
            {!isLoading && isSuccess && successPlan && (
              <>
                {/* Route Summary Metrics Card */}
                <div className="rounded-xl border border-cyan-500/30 bg-gradient-to-br from-cyan-950/30 to-indigo-950/30 p-4 space-y-3 shadow-lg shadow-cyan-950/20">
                  <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 text-center">
                    <div className="rounded-lg bg-slate-900/60 p-2 border border-slate-800/60">
                      <div className="text-[10px] text-slate-400">Итого время</div>
                      <div className="text-sm font-bold text-cyan-300">
                        ~{successPlan.estimated_total_minutes.toFixed(0)} мин
                      </div>
                    </div>
                    <div className="rounded-lg bg-slate-900/60 p-2 border border-slate-800/60">
                      <div className="text-[10px] text-slate-400">Пешком</div>
                      <div className="text-sm font-bold text-slate-200">
                        {successPlan.walking_minutes.toFixed(1)} мин
                      </div>
                    </div>
                    <div className="rounded-lg bg-slate-900/60 p-2 border border-slate-800/60">
                      <div className="text-[10px] text-slate-400">Визиты</div>
                      <div className="text-sm font-bold text-amber-300">
                        {successPlan.visiting_minutes} мин
                      </div>
                    </div>
                    <div className="rounded-lg bg-slate-900/60 p-2 border border-slate-800/60">
                      <div className="text-[10px] text-slate-400">Дистанция</div>
                      <div className="text-sm font-bold text-slate-200 font-mono">
                        {(successPlan.total_distance_meters / 1000).toFixed(2)} км
                      </div>
                    </div>
                  </div>

                  {/* Recommendation Text */}
                  {successPlan.recommendation && (
                    <p className="text-xs text-slate-300 leading-relaxed pt-1 border-t border-slate-800/60">
                      {successPlan.recommendation}
                    </p>
                  )}

                  {/* Caveat Warnings */}
                  {routeWarnings.length > 0 && (
                    <div className="flex flex-wrap gap-1 text-[10px]">
                      {routeWarnings.map((w) => (
                        <span
                          key={w}
                          className="rounded bg-slate-800/80 px-1.5 py-0.5 text-slate-400 border border-slate-700/50"
                        >
                          {w}
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                {/* Timeline Component */}
                <RouteTimeline
                  stops={successPlan.stops}
                  startAnchor={successPlan.start_anchor}
                  roundTrip={successPlan.round_trip}
                  selectedStopId={selectedStopId}
                  onSelectStop={handleSelectStop}
                  onSelectAnchor={handleSelectAnchor}
                  walkingMinutes={successPlan.walking_minutes}
                  totalDistanceMeters={successPlan.total_distance_meters}
                />

                {/* Recommendation POI Cards */}
                <div className="space-y-3">
                  <div className="flex items-center justify-between text-xs text-slate-400">
                    <span>Подробные карточки мест</span>
                    <span className="text-[10px] text-slate-500">Нажмите для фокуса на карте</span>
                  </div>
                  {successPlan.stops.map((stop) => (
                    <RecommendationCard
                      key={stop.id}
                      stop={stop}
                      isSelected={selectedStopId === stop.id}
                      onSelect={handleSelectStop}
                    />
                  ))}
                </div>

                {/* Attribution & Provenance Footer */}
                <div className="rounded-xl border border-slate-800/60 bg-slate-900/40 p-3 text-[10px] text-slate-500 space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span>{successPlan.dataset.attribution}</span>
                    <a
                      href={successPlan.dataset.license_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-cyan-400/80 hover:underline inline-flex items-center gap-0.5"
                    >
                      {successPlan.dataset.license}
                      <ExternalLink className="h-2.5 w-2.5" />
                    </a>
                  </div>
                  <div>
                    Маршрут:{' '}
                    {successPlan.routing_provenance.directions
                      ? `${successPlan.routing_provenance.directions.provider} (${successPlan.routing_provenance.directions.profile})`
                      : 'ORS Graph Directions'}
                  </div>
                </div>
              </>
            )}
          </div>
        </main>

        {/* ========================================================================= */}
        {/* 3. RIGHT PANEL: INTERACTIVE MAP (MapLibre GL JS) */}
        {/* ========================================================================= */}
        <section
          aria-label="Карта маршрута"
          className={`flex-1 min-w-0 relative h-full w-full bg-slate-950 p-2 sm:p-3 transition-all duration-300 ${
            activeTab === 'map' ? 'flex' : 'hidden lg:flex'
          }`}
        >
          <MapView
            stops={isSuccess && successPlan ? successPlan.stops : []}
            selectedStopId={selectedStopId}
            startAnchor={isSuccess && successPlan ? successPlan.start_anchor : activeAnchor}
            routeGeoJSON={isSuccess && successPlan ? successPlan.route_geojson : null}
            isochronesGeoJSON={isDemoFixture ? DEMO_ISOCHRONES_GEOJSON : null}
            userH3Cell={userH3Cell}
            onSelectStop={handleSelectStop}
            onSelectAnchor={handleSelectAnchor}
            className="h-full w-full"
          />
          {isDemoFixture && <p className="absolute bottom-6 right-6 rounded-lg border border-amber-500 bg-amber-950 px-3 py-2 text-xs text-amber-200">Демонстрационные данные</p>}
        </section>
      </div>

      {/* Mobile Navigation Tabs Bar (Visible on mobile/tablet < 1024px) */}
      <nav className="flex lg:hidden h-14 shrink-0 items-center justify-around border-t border-slate-800/80 bg-slate-900/95 px-2 z-30">
        <button
          type="button"
          onClick={() => setActiveTab('controls')}
          className={`flex flex-col items-center justify-center gap-1 flex-1 py-1 text-xs transition-colors ${
            activeTab === 'controls' ? 'text-cyan-400 font-semibold' : 'text-slate-400'
          }`}
        >
          <Sliders className="h-4 w-4" />
          <span className="text-[10px]">Параметры</span>
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('recommendations')}
          className={`flex flex-col items-center justify-center gap-1 flex-1 py-1 text-xs transition-colors ${
            activeTab === 'recommendations' ? 'text-cyan-400 font-semibold' : 'text-slate-400'
          }`}
        >
          <Navigation className="h-4 w-4" />
          <span className="text-[10px]">Маршрут</span>
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('map')}
          className={`flex flex-col items-center justify-center gap-1 flex-1 py-1 text-xs transition-colors ${
            activeTab === 'map' ? 'text-cyan-400 font-semibold' : 'text-slate-400'
          }`}
        >
          <Compass className="h-4 w-4" />
          <span className="text-[10px]">Карта</span>
        </button>
      </nav>
    </div>
  );
};

export default App;
