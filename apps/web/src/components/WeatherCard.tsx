import { useEffect, useState } from 'react';
import { getWeather } from '../api/client';
import type { AnchorID, WeatherResponse } from '../types/api';

const warningLabels: Record<string, string> = {
  weather_strong_wind: 'Сильный ветер',
  weather_significant_precipitation: 'Значительные осадки',
  weather_low_temperature: 'Низкая температура',
  weather_high_precipitation_probability: 'Высокая вероятность осадков',
  weather_conditions_unknown: 'Погодные условия неизвестны',
  weather_model_estimate_not_station_observation: 'Модельный прогноз Open-Meteo',
  weather_current_incomplete: 'Часть погодных данных отсутствует',
  weather_hourly_probability_unavailable: 'Вероятность осадков неизвестна',
};

export function WeatherCard({ anchorId }: { anchorId: AnchorID }) {
  const [result, setResult] = useState<{ anchorId: AnchorID; weather?: WeatherResponse; error?: string } | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    getWeather(anchorId, AbortSignal.any([controller.signal, AbortSignal.timeout(12000)]))
      .then(weather => {
        if (!controller.signal.aborted) setResult({ anchorId, weather });
      })
      .catch(() => {
        if (!controller.signal.aborted) setResult({ anchorId, error: 'Погода недоступна. Маршрут можно построить без неё.' });
      });
    return () => controller.abort();
  }, [anchorId]);

  const current = result?.anchorId === anchorId ? result : null;
  const weather = current?.weather;
  const known = weather?.status === 'available';
  const value = (number: number | null | undefined, unit: string) =>
    known && number != null ? `${number.toFixed(1)} ${unit}` : 'Нет данных';

  return (
    <div aria-live="polite" className="rounded-xl border border-slate-800 bg-slate-900/40 p-3 text-xs space-y-2" data-testid="weather">
      <h3 className="font-semibold text-slate-300">Погода у точки старта</h3>
      {!current ? <p className="text-slate-400">Загрузка погоды…</p> : current.error ? (
        <p className="text-amber-300">{current.error}</p>
      ) : (
        <>
          {!known && <p className="text-amber-300">Погодные условия неизвестны</p>}
          <div className="flex flex-wrap gap-3 text-slate-300">
            <span>Температура: {value(weather?.temperature_c, '°C')}</span>
            <span>Ветер: {value(weather?.wind_speed_kmh, 'км/ч')}</span>
          </div>
          {weather?.warnings.map(warning => <p key={warning} className="text-[11px] text-amber-200">{warningLabels[warning] ?? warning}</p>)}
        </>
      )}
    </div>
  );
}
