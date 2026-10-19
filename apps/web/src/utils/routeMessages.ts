import type { NoRouteReason } from '../types/api';

export const noRouteLabels: Record<NoRouteReason, string> = {
  no_candidates: 'Не найдены подходящие места',
  unreachable: 'Нет подтверждённого пешего пути',
  budget_exceeded: 'Не хватает времени на весь маршрут',
  ors_unconfigured: 'Сервис маршрутов не настроен',
  ors_timeout: 'Сервис маршрутов не ответил вовремя',
  ors_unavailable: 'Сервис маршрутов недоступен',
  ors_invalid_response: 'Не удалось проверить пеший путь',
};

const labels: Record<string, string | null> = {
  current_opening_status_unknown: 'Открытие заведений сейчас не проверено.',
  entrance_and_accessibility_not_verified: 'Входы и доступность не подтверждены.',
  osm_source_only: 'Сведения о местах взяты из OpenStreetMap.',
  preferences_not_verified: 'Соответствие всем пожеланиям не подтверждено.',
  visit_times_are_planned_estimates: 'Время посещений — плановая оценка.',
  nearby_fallback_not_query_match: 'Часть мест выбрана по близости без подтверждения запроса.',
  missing_name: 'У части мест нет названия в OpenStreetMap.',
  missing_opening_hours: 'У части мест не указаны часы работы.',
  indoor_unknown: 'Наличие помещения у части мест неизвестно.',
  covered_unknown: 'Наличие укрытия от осадков неизвестно.',
  directions_exceeded_budget: 'Пеший путь оказался дольше предварительной оценки.',
  stop_removed_after_directions_check: 'После проверки времени число остановок сокращено.',
  ors_directions_warning: 'У сервиса маршрутов есть ограничения для этого пешего пути.',
  ors_transport_error: 'Не удалось связаться с сервисом маршрутов.',
  'required_stop_missing:coffee': 'Рядом не найдена кофейня.',
  'required_stop_missing:park': 'Рядом не найден парк или сад.',
  required_stages_exceed_candidate_limit: 'Не удалось подобрать все необходимые остановки.',
  // Internal search diagnostics are not caveats about a user's walking route.
  semantic_disabled: null,
  embedding_unavailable: null,
  retrieval_scores_are_not_factual_confidence: null,
  route_is_snapped_to_ors_walking_graph: null,
};

export function formatRouteWarnings(warnings: string[]): string[] {
  const messages = warnings.map(warning => {
    if (warning.startsWith('bounding_box_center_not_verified_entrance:') || warning === 'location_is_bbox_center_not_entrance') {
      return 'Часть точек указана центром объекта, а не подтверждённым входом.';
    }
    return warning in labels ? labels[warning] : 'Есть дополнительные ограничения данных.';
  });
  return [...new Set(messages.filter((message): message is string => message !== null))];
}
