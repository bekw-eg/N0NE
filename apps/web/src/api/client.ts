import type { AnchorID, H3ResolveResponse, RoutePlanRequest, RoutePlanResponse, WeatherResponse } from '../types/api';

// Development always uses the Vite proxy. Production accepts a backend origin
// (optionally ending in /api), or a same-origin /api reverse proxy.
const configuredBase = import.meta.env.DEV ? '/api' : (import.meta.env.VITE_API_BASE_URL?.trim() || '/api');
const apiBase = `${configuredBase.replace(/\/+$/, '').replace(/\/api$/, '')}/api`;

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  try {
    const response = await fetch(`${apiBase}/v1${path}`, {
      ...init,
      credentials: 'omit',
      cache: 'no-store',
      referrerPolicy: 'no-referrer',
      signal: init.signal ?? AbortSignal.timeout(65000),
    });
    if (!response.ok) {
      if (response.status === 422) throw new Error('Проверьте параметры запроса (длительность 30–180 минут).');
      if (response.status === 413) throw new Error('Слишком длинный запрос.');
      throw new Error(`Ошибка API (${response.status}). Повторите попытку.`);
    }
    return await response.json() as T;
  } catch (error) {
    if (error instanceof TypeError) throw new Error('Не удалось связаться с API. Проверьте подключение и повторите попытку.');
    if (error instanceof DOMException && error.name === 'TimeoutError') throw new Error('API не ответил вовремя. Повторите попытку.');
    throw error;
  }
}

export async function planRoute(payload: RoutePlanRequest): Promise<RoutePlanResponse> {
  const data = await request<RoutePlanResponse>('/routes/plan', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
  });
  if (!data || !['success', 'no_route'].includes(data.status) || !data.start_anchor || !Array.isArray(data.warnings)) {
    throw new Error('API вернул некорректный ответ маршрута.');
  }
  if (data.status === 'success' && (
    !data.stops?.length || data.route_geojson?.type !== 'FeatureCollection' ||
    data.route_geojson.features?.[0]?.geometry?.type !== 'LineString' ||
    ![data.walking_minutes, data.visiting_minutes, data.estimated_total_minutes, data.total_distance_meters].every(Number.isFinite)
  )) throw new Error('API вернул неполные данные маршрута.');
  if (data.status === 'no_route' && (data.route_geojson !== null || data.stops?.length !== 0)) {
    throw new Error('API вернул некорректный ответ no_route.');
  }
  return data;
}

export const getWeather = (anchorId: AnchorID, signal: AbortSignal) =>
  request<WeatherResponse>(`/weather?start_anchor_id=${encodeURIComponent(anchorId)}`, { signal });

export const resolveH3 = (h3Cell: string) => request<H3ResolveResponse>('/privacy/resolve-h3', {
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ h3_cell: h3Cell }),
});
