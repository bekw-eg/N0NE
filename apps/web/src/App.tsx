import React, { useState, useTransition } from 'react';
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
  Zap,
} from 'lucide-react';


import { MapView } from './components/MapView';
import { RecommendationCard } from './components/RecommendationCard';
import { RouteTimeline } from './components/RouteTimeline';
import {
  DEMO_ANCHORS,
  DEMO_ROUTE_PLAN,
  DEMO_ISOCHRONES_GEOJSON,
  DEMO_NO_ROUTE_PLAN,
} from './data/fixtures';
import type {
  Anchor,
  AnchorID,
  RouteStop,
  RoutePlanSuccess,
  RoutePlanUnavailable,
  RoutePlanResponse,
  RoutePlanRequest,
} from './types/api';

// Approximate H3 cell index for Astana EXPO / Mega Silk Way area
const DEFAULT_ASTANA_H3_CELL = '8820984547fffff';

export const App: React.FC = () => {
  // Mobile Tab State: 'controls' | 'recommendations' | 'map'
  const [activeTab, setActiveTab] = useState<'controls' | 'recommendations' | 'map'>('recommendations');

  // Route Planning Inputs (Managed for initial UX, readily connectable to Developer №3B state)
  const [selectedAnchorId, setSelectedAnchorId] = useState<AnchorID>('mega_silk_way');
  const [query, setQuery] = useState('Хочу спокойную прогулку возле парка с кофе');
  const [durationMinutes, setDurationMinutes] = useState<number>(60);
  const [roundTrip, setRoundTrip] = useState<boolean>(true);

  // Application State
  const [planResponse, setPlanResponse] = useState<RoutePlanResponse | null>(DEMO_ROUTE_PLAN);
  const [selectedStopId, setSelectedStopId] = useState<string | null>(
    DEMO_ROUTE_PLAN.stops[0]?.id || null
  );
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [apiError, setApiError] = useState<string | null>(null);
  const [isDemoFixture, setIsDemoFixture] = useState<boolean>(true);

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

  // Plan Route Handler (Calls FastAPI backend if available, or falls back to verified fixtures)
  const handlePlanRoute = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!query.trim()) return;

    setIsLoading(true);
    setApiError(null);

    const payload: RoutePlanRequest = {
      start_anchor_id: selectedAnchorId,
      duration_minutes: durationMinutes,
      query: query.trim(),
      round_trip: roundTrip,
      language: 'ru',
    };

    try {
      const apiBase = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';
      const res = await fetch(`${apiBase}/api/v1/routes/plan`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        if (res.status === 422) {
          throw new Error('Проверьте параметры маршрута (длительность от 30 до 180 минут).');
        }
        if (res.status === 413) {
          throw new Error('Слишком длинный поисковый запрос.');
        }
        throw new Error(`Ошибка сервера маршрутизации (${res.status}).`);
      }

      const data: RoutePlanResponse = await res.json();
      setPlanResponse(data);
      setIsDemoFixture(false);
      if (data.status === 'success' && data.stops.length > 0) {
        setSelectedStopId(data.stops[0].id);
      } else {
        setSelectedStopId(null);
      }
    } catch (err: unknown) {
      console.warn('Backend API request unavailable, using verified local Astana demo fixtures:', err);
      // Informative banner that backend is offline and verified Astana demo was retained
      setApiError(
        'Сервер FastAPI недоступен на localhost:8000. Включен автономный режим демонстрации (Astana Verified Dataset).'
      );
      setPlanResponse(DEMO_ROUTE_PLAN);
      setIsDemoFixture(true);
      setSelectedStopId(DEMO_ROUTE_PLAN.stops[0].id);
    } finally {
      setIsLoading(false);
    }
  };

  // Quick preset triggers for Astana walking vibes
  const handleApplyPreset = (text: string, anchorId: AnchorID, duration: number) => {
    setQuery(text);
    setSelectedAnchorId(anchorId);
    setDurationMinutes(duration);
  };

  const isSuccess = planResponse?.status === 'success';
  const successPlan = isSuccess ? (planResponse as RoutePlanSuccess) : null;
  const unavailablePlan = !isSuccess && planResponse ? (planResponse as RoutePlanUnavailable) : null;

  return (
    <div className="flex h-screen w-screen flex-col overflow-hidden bg-slate-950 text-slate-100">
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
            <span className="text-[11px] text-slate-400">H3 Cell:</span>
            <span className="font-mono text-[11px] text-cyan-300">{DEFAULT_ASTANA_H3_CELL}</span>
          </div>

          {/* Mode Switcher / Demo Notice */}
          <div className="flex items-center gap-1.5 rounded-lg border border-slate-800 bg-slate-900/60 px-2.5 py-1">
            <span
              className={`h-2 w-2 rounded-full ${
                isDemoFixture ? 'bg-amber-400' : 'bg-emerald-400'
              }`}
            ></span>
            <span className="text-[11px] font-medium text-slate-300">
              {isDemoFixture ? 'Offline Demo' : 'Live API'}
            </span>
          </div>

          {/* Toggle between demo success and no_route for testing */}
          <button
            type="button"
            onClick={() => {
              if (isSuccess) {
                setPlanResponse(DEMO_NO_ROUTE_PLAN);
                setSelectedStopId(null);
              } else {
                setPlanResponse(DEMO_ROUTE_PLAN);
                setSelectedStopId(DEMO_ROUTE_PLAN.stops[0].id);
              }
            }}
            title="Переключить состояние ответа (Успех / Маршрут не найден)"
            className="flex items-center gap-1 rounded-lg border border-slate-700/60 bg-slate-800/80 px-2 py-1 text-[11px] text-slate-300 hover:bg-slate-700 transition-colors"
          >
            <Zap className="h-3 w-3 text-cyan-400" />
            <span className="hidden sm:inline">Тест ответа</span>
          </button>
        </div>
      </header>

      {/* Main 3-Column Responsive Work Area */}
      <div className="relative flex flex-1 overflow-hidden">
        {/* ========================================================================= */}
        {/* 1. LEFT PANEL: CONTROLS & SCENARIO SELECTION (Developer №3A slot for 3B) */}
        {/* ========================================================================= */}
        <aside
          className={`flex flex-col border-r border-slate-800/80 bg-slate-950/95 overflow-y-auto z-20 transition-all duration-300 ${
            activeTab === 'controls' ? 'flex-1 w-full' : 'hidden lg:flex lg:w-80 xl:w-96'
          }`}
        >
          <div className="p-4 sm:p-5 space-y-5">
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
                  onChange={(e) => setSelectedAnchorId(e.target.value as AnchorID)}
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

              {/* Natural Language Preference Query */}
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1.5">
                  Пожелания к маршруту
                </label>
                <textarea
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
                disabled={isLoading || !query.trim()}
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

            {/* Integration slot designated for Developer №3B */}
            <div className="rounded-xl border border-dashed border-slate-800 p-3 bg-slate-950/40">
              <div className="flex items-center gap-1.5 text-[11px] font-semibold text-slate-400 mb-1">
                <ShieldCheck className="h-3.5 w-3.5 text-cyan-400" />
                <span>Зона расширений Developer №3B</span>
              </div>
              <p className="text-[10px] text-slate-500 leading-relaxed">
                Сюда подключаются модули: выбор тонких сценариев, переключение языков (kk/ru/en),
                индикатор доверия рекомендаций и фильтрация доступности.
              </p>
            </div>
          </div>
        </aside>

        {/* ========================================================================= */}
        {/* 2. CENTER PANEL: RECOMMENDATIONS & ROUTE TIMELINE */}
        {/* ========================================================================= */}
        <main
          className={`flex flex-col border-r border-slate-800/80 bg-slate-950 overflow-y-auto z-10 transition-all duration-300 ${
            activeTab === 'recommendations' ? 'flex-1 w-full' : 'hidden lg:flex lg:w-96 xl:w-[440px]'
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
              <div className="rounded-xl border border-amber-500/30 bg-amber-950/30 p-3 text-xs text-amber-200 flex items-start gap-2">
                <AlertCircle className="h-4 w-4 text-amber-400 shrink-0 mt-0.5" />
                <div className="space-y-1">
                  <p>{apiError}</p>
                </div>
              </div>
            )}

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
                  Маршрут не может быть сформирован
                </h3>
                <p className="text-xs text-slate-400 leading-relaxed">
                  {unavailablePlan.recommendation ||
                    'В заданное время невозможно дойти до подходящих мест и вернуться к старту. Попробуйте увеличить бюджет времени.'}
                </p>
                <div className="inline-flex items-center gap-1.5 rounded-full bg-slate-800/80 px-2.5 py-1 text-[11px] text-slate-400 font-mono">
                  Причина: {unavailablePlan.reason}
                </div>
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
                  {successPlan.warnings.length > 0 && (
                    <div className="flex flex-wrap gap-1 text-[10px]">
                      {successPlan.warnings.map((w) => (
                        <span
                          key={w}
                          className="rounded bg-slate-800/80 px-1.5 py-0.5 text-slate-400 border border-slate-700/50"
                        >
                          {w === 'visit_times_are_planned_estimates'
                            ? 'Оценки времени плановые'
                            : w === 'entrance_and_accessibility_not_verified'
                            ? 'Входы не верифицированы'
                            : w}
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
          className={`flex-1 relative h-full w-full bg-slate-950 p-2 sm:p-3 transition-all duration-300 ${
            activeTab === 'map' ? 'flex' : 'hidden lg:flex'
          }`}
        >
          <MapView
            stops={isSuccess && successPlan ? successPlan.stops : []}
            selectedStopId={selectedStopId}
            startAnchor={isSuccess && successPlan ? successPlan.start_anchor : activeAnchor}
            routeGeoJSON={isSuccess && successPlan ? successPlan.route_geojson : null}
            isochronesGeoJSON={DEMO_ISOCHRONES_GEOJSON}
            userH3Cell={DEFAULT_ASTANA_H3_CELL}
            onSelectStop={handleSelectStop}
            onSelectAnchor={handleSelectAnchor}
            className="h-full w-full"
          />
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
