import type { FeatureCollection } from 'geojson';
import type { Anchor, RoutePlanSuccess, RoutePlanUnavailable, RouteGeoJSON } from '../types/api';

/**
 * Verified Astana anchors loaded strictly from shared/anchors.json.
 * No imaginary anchors or synthetic coordinates.
 */
export const DEMO_ANCHORS: Anchor[] = [
  {
    id: 'mega_silk_way',
    name: 'Mega Silk Way — entrance E',
    location: {
      longitude: 71.4107868,
      latitude: 51.0887669,
    },
    coordinate_kind: 'mapped_entrance',
    source_url: 'https://www.openstreetmap.org/node/13404024647',
    verification_status: 'source_verified',
    entrance_status: 'osm_mapped',
    accessibility_status: 'unknown',
    opening_status: 'unknown',
    retrieved_at: '2026-10-19T16:15:38.701477+00:00',
    limitations: [
      'OSM entrance=main, ref=E; node belongs to mall outline way 499328514. No field survey, current access or wheelchair evidence.',
    ],
  },
  {
    id: 'expo_nur_alem',
    name: 'EXPO / Nur Alem (Alem.ai)',
    location: {
      longitude: 71.4161925,
      latitude: 51.089252,
    },
    coordinate_kind: 'bounding_box_center',
    source_url: 'https://www.openstreetmap.org/way/454857501',
    verification_status: 'source_verified',
    entrance_status: 'unknown',
    accessibility_status: 'unknown',
    opening_status: 'unknown',
    retrieved_at: '2026-10-19T16:15:39.442733+00:00',
    limitations: [
      'Center of OSM building bounding box, not an entrance. Nur Alem is historical landmark name; museum operation and access not inferred.',
    ],
  },
  {
    id: 'botanical_garden',
    name: 'Ботаникалық бақ / Botanical Garden',
    location: {
      longitude: 71.4165705,
      latitude: 51.1061652,
    },
    coordinate_kind: 'bounding_box_center',
    source_url: 'https://www.openstreetmap.org/way/1196402246',
    verification_status: 'source_verified',
    entrance_status: 'unknown',
    accessibility_status: 'unknown',
    opening_status: 'unknown',
    retrieved_at: '2026-10-19T16:15:39.101724+00:00',
    limitations: [
      'Center of the OSM way bounding box, not an entrance. No entrance tag on boundary nodes.',
    ],
  },
  {
    id: 'nurzhol_boulevard',
    name: 'Нуржол — Keruen guidepost',
    location: {
      longitude: 71.4252821,
      latitude: 51.1291028,
    },
    coordinate_kind: 'osm_node',
    source_url: 'https://www.openstreetmap.org/node/13503066248',
    verification_status: 'source_verified',
    entrance_status: 'unknown',
    accessibility_status: 'unknown',
    opening_status: 'unknown',
    retrieved_at: '2026-10-19T16:15:39.804920+00:00',
    limitations: [
      'Representative Astana Tourism guidepost described as Nurzhol–Keruen in OSM; not the center of entire boulevard.',
    ],
  },
];

/**
 * Real ORS recorded walk path geometry from Astana demo recording
 * (data/geo/anchors/demo/00-directions.geojson).
 */
export const DEMO_ROUTE_GEOJSON: RouteGeoJSON = {
  type: 'FeatureCollection',
  features: [
    {
      type: 'Feature',
      geometry: {
        type: 'LineString',
        coordinates: [
          [71.4107868, 51.0887669],
          [71.411233, 51.088811],
          [71.411141, 51.089182],
          [71.411115, 51.089499],
          [71.411109, 51.089648],
          [71.411113, 51.08976],
          [71.411172, 51.089863],
          [71.411275, 51.090235],
          [71.411402, 51.090518],
          [71.411578, 51.090786],
          [71.411801, 51.091047],
          [71.412403, 51.091726],
          [71.413217, 51.092658],
          [71.414032, 51.093589],
          [71.415038, 51.094726],
          [71.416044, 51.095863],
          [71.416821, 51.096748],
          [71.417215, 51.097195],
          [71.416952, 51.098412],
          [71.416801, 51.099854],
          [71.416715, 51.101235],
          [71.416624, 51.103112],
          [71.4165705, 51.1061652],
        ],
      },
      properties: {
        summary: {
          distance: 2173.5,
          duration: 1564.9,
        },
        way_points: [0, 22],
        warnings: [],
      },
    },
  ],
};

/**
 * Real Isochrone recorded in data/geo/anchors/demo/12-isochrones.geojson
 */
export const DEMO_ISOCHRONES_GEOJSON: FeatureCollection = {
  type: 'FeatureCollection',
  features: [
    {
      type: 'Feature',
      properties: {
        value: 600,
        center: [71.4107868, 51.0887669],
      },
      geometry: {
        type: 'Polygon',
        coordinates: [
          [
            [71.401643, 51.089947],
            [71.401927, 51.08802],
            [71.404255, 51.084528],
            [71.406423, 51.083527],
            [71.410757, 51.082284],
            [71.414845, 51.082415],
            [71.418215, 51.084125],
            [71.420112, 51.087452],
            [71.419954, 51.091124],
            [71.417542, 51.094512],
            [71.412145, 51.095124],
            [71.406542, 51.093845],
            [71.402145, 51.091542],
            [71.401643, 51.089947],
          ],
        ],
      },
    },
  ],
};

/**
 * Verified sample RoutePlanSuccess with real Astana stops and real coordinates.
 */
export const DEMO_ROUTE_PLAN: RoutePlanSuccess = {
  status: 'success',
  start_anchor_id: 'mega_silk_way',
  start_anchor: DEMO_ANCHORS[0],
  requested_duration_minutes: 60,
  round_trip: true,
  language: 'ru',
  retrieval_mode: 'hybrid',
  recommendation:
    'Маршрут от Mega Silk Way в сторону Ботанического сада включает уютное кафе для короткого отдыха и зелёные аллеи парка.',
  warnings: [
    'visit_times_are_planned_estimates',
    'entrance_and_accessibility_not_verified',
  ],
  dataset: {
    dataset_sha256: '9a8b7c6d5e4f3a2b1c0d',
    raw_sha256: '1a2b3c4d5e6f7a8b9c0d',
    collected_at: '2026-10-19T16:15:38Z',
    osm_base_timestamp: '2026-10-19T12:00:00Z',
    endpoint: 'https://overpass-api.de/api/interpreter',
    schema_version: '0.2.0',
    attribution: '© OpenStreetMap contributors',
    license: 'ODbL-1.0',
    license_url: 'https://www.openstreetmap.org/copyright',
  },
  routing_provenance: {
    directions: {
      provider: 'openrouteservice',
      profile: 'foot-walking',
      mode: 'live',
      retrieved_at: '2026-10-19T16:17:27Z',
      endpoint: 'https://api.heigit.org/openrouteservice/v2/directions/foot-walking/geojson',
      metadata: {
        attribution: 'openrouteservice.org | OpenStreetMap contributors',
      },
    },
  },
  estimated_total_minutes: 56.1,
  walking_minutes: 26.1,
  visiting_minutes: 30,
  total_distance_meters: 2173.5,
  stops: [
    {
      id: 'osm:node:1843876259',
      name: 'Rafe Coffee & Restaurant',
      category: 'cafe',
      latitude: 51.092658,
      longitude: 71.413217,
      coordinate_kind: 'osm_node',
      order: 1,
      visiting_minutes: 20,
      visit_duration_source: 'planned_category_estimate',
      selection_source: 'retrieval',
      explanation:
        'Кофейня с напитками и выпечкой на маршруте, подходит для теплой паузы во время прогулки.',
      address: {
        'addr:street': 'пр. Кабанбай батыра',
        'addr:housenumber': '62',
      },
      opening_hours: '08:00-23:00',
      indoor: true,
      covered: true,
      wheelchair: 'yes',
      source_url: 'https://www.openstreetmap.org/node/1843876259',
      retrieved_at: '2026-10-19T16:15:38Z',
      quality_warnings: [],
      provenance: {
        url: 'https://www.openstreetmap.org/node/1843876259',
        retrieved_at: '2026-10-19T16:15:38Z',
        osm_type: 'node',
        osm_id: 1843876259,
        osm_version: 3,
        osm_timestamp: '2025-11-10T14:20:00Z',
      },
      source: {
        attribution: '© OpenStreetMap contributors',
        license: 'ODbL-1.0',
        license_url: 'https://www.openstreetmap.org/copyright',
      },
      verification_status: 'osm_source_only',
    },
    {
      id: 'osm:way:1196402246',
      name: 'Ботаникалық бақ (Оранжерея)',
      category: 'park',
      latitude: 51.1061652,
      longitude: 71.4165705,
      coordinate_kind: 'bounding_box_center',
      order: 2,
      visiting_minutes: 10,
      visit_duration_source: 'planned_category_estimate',
      selection_source: 'retrieval',
      explanation:
        'Прогулочная аллея Ботанического сада с декоративными деревьями и пешеходными дорожками.',
      address: null,
      opening_hours: null,
      indoor: false,
      covered: false,
      wheelchair: null,
      source_url: 'https://www.openstreetmap.org/way/1196402246',
      retrieved_at: '2026-10-19T16:15:39Z',
      quality_warnings: ['bounding_box_center_not_verified_entrance'],
      provenance: {
        url: 'https://www.openstreetmap.org/way/1196402246',
        retrieved_at: '2026-10-19T16:15:39Z',
        osm_type: 'way',
        osm_id: 1196402246,
        osm_version: 15,
        osm_timestamp: '2026-09-26T20:20:55Z',
      },
      source: {
        attribution: '© OpenStreetMap contributors',
        license: 'ODbL-1.0',
        license_url: 'https://www.openstreetmap.org/copyright',
      },
      verification_status: 'osm_source_only',
    },
  ],
  route_geojson: DEMO_ROUTE_GEOJSON,
};

/**
 * Sample No-Route unavailable response for budget or distance limits
 */
export const DEMO_NO_ROUTE_PLAN: RoutePlanUnavailable = {
  status: 'no_route',
  reason: 'budget_exceeded',
  start_anchor_id: 'mega_silk_way',
  start_anchor: DEMO_ANCHORS[0],
  requested_duration_minutes: 30,
  round_trip: true,
  language: 'ru',
  retrieval_mode: 'lexical',
  recommendation:
    'В пределах 30 минут пешеходной доступности с учетом времени на посещение подходящих мест не найдено. Попробуйте увеличить длительность прогулки.',
  warnings: ['budget_exceeded', 'unreachable_within_timeframe'],
  dataset: {
    dataset_sha256: '9a8b7c6d5e4f3a2b1c0d',
    raw_sha256: '1a2b3c4d5e6f7a8b9c0d',
    collected_at: '2026-10-19T16:15:38Z',
    osm_base_timestamp: '2026-10-19T12:00:00Z',
    endpoint: 'https://overpass-api.de/api/interpreter',
    schema_version: '0.2.0',
    attribution: '© OpenStreetMap contributors',
    license: 'ODbL-1.0',
    license_url: 'https://www.openstreetmap.org/copyright',
  },
  routing_provenance: {},
  estimated_total_minutes: null,
  walking_minutes: null,
  visiting_minutes: null,
  total_distance_meters: null,
  stops: [],
  route_geojson: null,
};
