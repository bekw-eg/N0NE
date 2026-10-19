import React from 'react';
import { Flag, Navigation, Clock, CheckCircle2 } from 'lucide-react';
import type { RouteStop, Anchor } from '../types/api';


interface RouteTimelineProps {
  stops: RouteStop[];
  startAnchor?: Anchor | null;
  roundTrip?: boolean;
  selectedStopId?: string | null;
  onSelectStop?: (stop: RouteStop) => void;
  onSelectAnchor?: (anchor: Anchor) => void;
  walkingMinutes?: number | null;
  totalDistanceMeters?: number | null;
}

export const RouteTimeline: React.FC<RouteTimelineProps> = ({
  stops,
  startAnchor,
  roundTrip = true,
  selectedStopId,
  onSelectStop,
  onSelectAnchor,
  walkingMinutes,
  totalDistanceMeters,
}) => {
  const sortedStops = [...stops].sort((a, b) => a.order - b.order);

  return (
    <div className="rounded-xl border border-slate-800/80 bg-slate-900/60 p-4">
      {/* Metrics header */}
      <div className="flex items-center justify-between border-b border-slate-800/80 pb-3 mb-4">
        <div className="flex items-center gap-2">
          <Navigation className="h-4 w-4 text-cyan-400" />
          <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-300">
            Последовательность маршрута
          </h4>
        </div>
        {(walkingMinutes !== null && walkingMinutes !== undefined) && (
          <div className="flex items-center gap-3 text-xs text-slate-400">
            <span className="inline-flex items-center gap-1">
              <Clock className="h-3 w-3 text-cyan-400" />
              {walkingMinutes.toFixed(1)} мин пешком
            </span>
            {totalDistanceMeters !== null && totalDistanceMeters !== undefined && (
              <span className="font-mono text-slate-300">
                {(totalDistanceMeters / 1000).toFixed(2)} км
              </span>
            )}
          </div>
        )}
      </div>

      {/* Timeline Steps */}
      <div className="relative pl-6 space-y-5 before:absolute before:bottom-3 before:top-3 before:left-2.5 before:w-0.5 before:bg-gradient-to-b before:from-cyan-500 before:via-indigo-500 before:to-emerald-500">
        {/* Step 0: Start Anchor */}
        {startAnchor && (
          <div
            onClick={() => onSelectAnchor?.(startAnchor)}
            className="group relative cursor-pointer text-left transition-all"
            role="button"
            tabIndex={0}
          >
            <div className="absolute -left-6 top-0.5 flex h-5 w-5 items-center justify-center rounded-full bg-slate-900 ring-2 ring-cyan-400 shadow-sm shadow-cyan-500/50">
              <Flag className="h-2.5 w-2.5 text-cyan-300" />
            </div>
            <div>
              <div className="flex items-center gap-1.5">
                <span className="text-[11px] font-semibold uppercase text-cyan-400">
                  Точка старта
                </span>
                <span className="text-[10px] text-slate-500">
                  ({startAnchor.coordinate_kind === 'mapped_entrance' ? 'вход OSM' : 'центр объекта'})
                </span>
              </div>
              <p className="text-xs font-medium text-slate-200 group-hover:text-cyan-300 transition-colors">
                {startAnchor.name}
              </p>
            </div>
          </div>
        )}

        {/* POI Stops */}
        {sortedStops.map((stop) => {
          const isSelected = selectedStopId === stop.id;
          return (
            <div
              key={stop.id}
              onClick={() => onSelectStop?.(stop)}
              className={`group relative cursor-pointer text-left transition-all rounded-lg p-2 -ml-2 ${
                isSelected
                  ? 'bg-slate-800/80 ring-1 ring-cyan-400/60 shadow-sm'
                  : 'hover:bg-slate-800/40'
              }`}
              role="button"
              tabIndex={0}
            >
              <div
                className={`absolute -left-4 top-2.5 flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold transition-all ${
                  isSelected
                    ? 'bg-cyan-400 text-slate-950 ring-2 ring-cyan-300 scale-110 shadow-sm shadow-cyan-400/50'
                    : 'bg-slate-800 text-slate-300 ring-1 ring-slate-600 group-hover:bg-slate-700'
                }`}
              >
                {stop.order}
              </div>
              <div className="pl-2">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-semibold text-slate-200 group-hover:text-cyan-300 transition-colors line-clamp-1">
                    {stop.name && stop.name.trim() ? stop.name : 'Точка интереса (без имени в OSM)'}
                  </span>
                  {stop.visiting_minutes > 0 && (
                    <span className="shrink-0 text-[10px] text-amber-300/80 bg-amber-950/30 px-1.5 py-0.5 rounded border border-amber-900/40">
                      ~{stop.visiting_minutes} мин
                    </span>
                  )}
                </div>
                {stop.explanation && (
                  <p className="mt-1 text-[11px] text-slate-400 line-clamp-2 leading-relaxed">
                    {stop.explanation}
                  </p>
                )}
              </div>
            </div>
          );
        })}

        {/* Finish Step (Round Trip or Final Stop) */}
        {roundTrip && startAnchor && sortedStops.length > 0 && (
          <div
            onClick={() => onSelectAnchor?.(startAnchor)}
            className="group relative cursor-pointer text-left transition-all"
            role="button"
            tabIndex={0}
          >
            <div className="absolute -left-6 top-0.5 flex h-5 w-5 items-center justify-center rounded-full bg-slate-900 ring-2 ring-emerald-400 shadow-sm shadow-emerald-500/50">
              <CheckCircle2 className="h-2.5 w-2.5 text-emerald-300" />
            </div>
            <div>
              <span className="text-[11px] font-semibold uppercase text-emerald-400">
                Завершение прогулки
              </span>
              <p className="text-xs font-medium text-slate-300 group-hover:text-emerald-300 transition-colors">
                Возврат к {startAnchor.name}
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
