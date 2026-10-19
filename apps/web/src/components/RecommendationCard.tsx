import React from 'react';
import {
  MapPin,
  Clock,
  ExternalLink,
  ShieldAlert,
  Info,
  CheckCircle2,
  Compass,
  Building,
  Coffee,
  Trees,
  ShoppingBag,
  Sparkles,
} from 'lucide-react';
import type { RouteStop, Category } from '../types/api';

interface RecommendationCardProps {
  stop: RouteStop;
  isSelected?: boolean;
  onSelect?: (stop: RouteStop) => void;
}

const CATEGORY_LABELS: Record<Category, { label: string; icon: React.ElementType }> = {
  cafe: { label: 'Кафе', icon: Coffee },
  restaurant: { label: 'Ресторан', icon: Coffee },
  fast_food: { label: 'Фастфуд', icon: Coffee },
  food_court: { label: 'Фуд-корт', icon: Coffee },
  library: { label: 'Библиотека', icon: Building },
  cinema: { label: 'Кинотеатр', icon: Building },
  theatre: { label: 'Театр', icon: Building },
  arts_centre: { label: 'Арт-центр', icon: Building },
  community_centre: { label: 'Общественный центр', icon: Building },
  museum: { label: 'Музей', icon: Building },
  gallery: { label: 'Галерея', icon: Building },
  attraction: { label: 'Достопримечательность', icon: Sparkles },
  artwork: { label: 'Арт-объект', icon: Sparkles },
  viewpoint: { label: 'Смотровая площадка', icon: Compass },
  park: { label: 'Парк', icon: Trees },
  garden: { label: 'Сад', icon: Trees },
  playground: { label: 'Площадка', icon: Trees },
  mall: { label: 'Торговый центр', icon: ShoppingBag },
  books: { label: 'Книги', icon: Building },
};

function formatAddress(address: Record<string, string> | null): string | null {
  if (!address) return null;
  const parts: string[] = [];
  if (address.street || address['addr:street']) {
    parts.push(address.street || address['addr:street']);
  }
  if (address.housenumber || address['addr:housenumber']) {
    parts.push(address.housenumber || address['addr:housenumber']);
  }
  if (parts.length > 0) return parts.join(', ');
  const values = Object.values(address).filter((v) => typeof v === 'string' && v.trim());
  return values.length > 0 ? values.slice(0, 2).join(', ') : null;
}

export const RecommendationCard: React.FC<RecommendationCardProps> = ({
  stop,
  isSelected = false,
  onSelect,
}) => {
  const categoryInfo = CATEGORY_LABELS[stop.category] || {
    label: stop.category,
    icon: MapPin,
  };
  const CategoryIcon = categoryInfo.icon;
  const formattedAddr = formatAddress(stop.address);

  return (
    <div
      onClick={() => onSelect?.(stop)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onSelect?.(stop);
        }
      }}
      role="button"
      tabIndex={0}
      className={`group relative rounded-xl border p-4.5 text-left transition-all duration-200 cursor-pointer outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 ${
        isSelected
          ? 'border-cyan-400/80 bg-slate-900/95 ring-1 ring-cyan-400/50 shadow-lg shadow-cyan-950/40'
          : 'border-slate-800/80 bg-slate-900/60 hover:border-slate-700 hover:bg-slate-900/80'
      }`}
    >
      {/* Header with sequence badge, category, and selection indicator */}
      <div className="flex items-start justify-between gap-2 mb-2.5">
        <div className="flex items-center gap-2">
          <div
            className={`flex h-7 w-7 items-center justify-center rounded-lg text-xs font-bold transition-colors ${
              isSelected
                ? 'bg-cyan-500 text-slate-950 shadow-sm shadow-cyan-400/50'
                : 'bg-slate-800 text-slate-300 group-hover:bg-slate-700'
            }`}
          >
            {stop.order}
          </div>
          <span className="inline-flex items-center gap-1.5 rounded-md bg-slate-800/80 px-2 py-0.5 text-xs font-medium text-slate-300 border border-slate-700/50">
            <CategoryIcon className="h-3 w-3 text-cyan-400" />
            {categoryInfo.label}
          </span>
        </div>

        {/* Planned visit duration */}
        {stop.visiting_minutes > 0 && (
          <span className="inline-flex items-center gap-1 text-xs text-amber-300/90 bg-amber-950/40 border border-amber-900/50 px-2 py-0.5 rounded-full">
            <Clock className="h-3 w-3" />
            ~{stop.visiting_minutes} мин (оценка)
          </span>
        )}
      </div>

      {/* POI Name */}
      <h3 className="text-base font-semibold text-slate-100 group-hover:text-cyan-300 transition-colors line-clamp-1">
        {stop.name && stop.name.trim() ? stop.name : 'Название не указано в OSM'}
      </h3>

      {/* Address if present */}
      {formattedAddr && (
        <p className="mt-1 flex items-center gap-1.5 text-xs text-slate-400">
          <MapPin className="h-3 w-3 shrink-0 text-slate-500" />
          <span className="truncate">{formattedAddr}</span>
        </p>
      )}

      {/* Explanation text */}
      {stop.explanation && (
        <p className="mt-2.5 text-xs leading-relaxed text-slate-300/90 bg-slate-950/60 p-2.5 rounded-lg border border-slate-800/60">
          {stop.explanation}
        </p>
      )}

      {/* Prominent warning if selected by proximity fallback */}
      {stop.selection_source === 'nearby_fallback' && (
        <div className="mt-2.5 flex items-start gap-1.5 rounded-md bg-amber-950/30 border border-amber-800/40 px-2.5 py-1.5 text-[11px] text-amber-200">
          <ShieldAlert className="h-3.5 w-3.5 text-amber-400 shrink-0 mt-0.5" />
          <span>
            Подобрано по близости к маршруту: соответствие предпочтениям запроса не гарантировано.
          </span>
        </div>
      )}

      {/* Verified attributes and factual badges */}
      <div className="mt-3 flex flex-wrap items-center gap-1.5 text-[11px]">
        {/* Coordinate precision badge */}
        {stop.coordinate_kind === 'bounding_box_center' ? (
          <span className="inline-flex items-center gap-1 rounded bg-slate-800/60 px-1.5 py-0.5 text-slate-400 border border-slate-700/40">
            <Info className="h-3 w-3 text-slate-400" />
            Центр контура (вход не размечен)
          </span>
        ) : (
          <span className="inline-flex items-center gap-1 rounded bg-emerald-950/30 px-1.5 py-0.5 text-emerald-300 border border-emerald-800/40">
            <CheckCircle2 className="h-3 w-3 text-emerald-400" />
            Точка OSM
          </span>
        )}

        {/* Wheelchair access if known */}
        {stop.wheelchair && (
          <span className="rounded bg-slate-800/60 px-1.5 py-0.5 text-slate-300 border border-slate-700/40">
            Доступность: {stop.wheelchair === 'yes' ? 'да' : stop.wheelchair === 'limited' ? 'ограничена' : 'нет'}
          </span>
        )}

        {/* Indoor / covered status if known */}
        {stop.indoor !== null && (
          <span className="rounded bg-slate-800/60 px-1.5 py-0.5 text-slate-300 border border-slate-700/40">
            {stop.indoor ? 'В помещении' : 'На улице'}
          </span>
        )}

        {/* Opening hours if known */}
        {stop.opening_hours && (
          <span className="rounded bg-slate-800/60 px-1.5 py-0.5 text-slate-300 border border-slate-700/40 truncate max-w-[200px]" title={stop.opening_hours}>
            Часы: {stop.opening_hours}
          </span>
        )}
      </div>

      {/* Footer attribution & link */}
      <div className="mt-3 flex items-center justify-between border-t border-slate-800/60 pt-2 text-[10px] text-slate-500">
        <span className="truncate">OSM: {stop.id}</span>
        {stop.source_url && (
          <a
            href={stop.source_url}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="inline-flex items-center gap-1 text-cyan-400/80 hover:text-cyan-300 hover:underline"
          >
            OpenStreetMap
            <ExternalLink className="h-2.5 w-2.5" />
          </a>
        )}
      </div>
    </div>
  );
};
