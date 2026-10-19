/**
 * API Contracts and Types for VibeRoute Web Client.
 * Aligns strictly with FastAPI backend schemas (apps/api/app/schemas/routes.py & poi.py).
 */

export type AnchorID = 'mega_silk_way' | 'botanical_garden' | 'expo_nur_alem' | 'nurzhol_boulevard';

export type Language = 'ru' | 'kk' | 'en';

export type RetrievalMode = 'lexical' | 'hybrid';

export type CoordinateKind = 'osm_node' | 'bounding_box_center' | 'mapped_entrance';

export type Category =
  | 'cafe'
  | 'restaurant'
  | 'fast_food'
  | 'food_court'
  | 'library'
  | 'cinema'
  | 'theatre'
  | 'arts_centre'
  | 'community_centre'
  | 'museum'
  | 'gallery'
  | 'attraction'
  | 'artwork'
  | 'viewpoint'
  | 'park'
  | 'garden'
  | 'playground'
  | 'mall'
  | 'books';

export interface Attribution {
  attribution: string;
  license: string;
  license_url: string;
}

export interface DatasetMetadata extends Attribution {
  dataset_sha256: string;
  raw_sha256: string;
  collected_at: string;
  osm_base_timestamp: string | null;
  endpoint: string;
  schema_version: string;
}

export interface Provenance {
  url: string;
  retrieved_at: string;
  osm_type: 'node' | 'way' | 'relation';
  osm_id: number;
  osm_version: number;
  osm_timestamp: string;
}

export interface PublicPOI {
  id: string; // e.g. "osm:node:1843876259"
  name: string | null;
  category: Category;
  latitude: number;
  longitude: number;
  coordinate_kind: 'osm_node' | 'bounding_box_center';
  address: Record<string, string> | null;
  opening_hours: string | null;
  indoor: boolean | null;
  covered: boolean | null;
  wheelchair: 'yes' | 'no' | 'limited' | null;
  source_url: string;
  retrieved_at: string;
  quality_warnings: string[];
  provenance: Provenance;
  source: Attribution;
  verification_status: 'osm_source_only';
}

export interface RouteStop extends PublicPOI {
  order: number;
  visiting_minutes: number;
  visit_duration_source: 'planned_category_estimate';
  selection_source: 'retrieval' | 'nearby_fallback';
  explanation: string;
}

export interface AnchorLocation {
  longitude: number;
  latitude: number;
}

export interface Anchor {
  id: AnchorID;
  name: string;
  location: AnchorLocation;
  coordinate_kind: CoordinateKind;
  source_url: string;
  osm_version?: number;
  osm_updated_at?: string;
  retrieved_at: string;
  osm_tags?: Record<string, string>;
  verification_status: string;
  entrance_status: string;
  accessibility_status: string;
  opening_status: string;
  limitations: string[];
  landmark_source_url?: string;
  alternative_entrances?: Array<{
    id: string;
    name: string;
    location: AnchorLocation;
    coordinate_kind: CoordinateKind;
    source_url: string;
  }>;
}

export interface RouteSummary {
  distance: number; // in meters
  duration: number; // in seconds
}

export interface RouteGeoJSONProperties {
  summary: RouteSummary;
  way_points: number[];
  warnings?: Array<Record<string, unknown>>;
}

export interface RouteLineString {
  type: 'LineString';
  coordinates: [number, number][]; // [longitude, latitude]
}

export interface RouteFeature {
  type: 'Feature';
  geometry: RouteLineString;
  properties: RouteGeoJSONProperties;
}

export interface RouteGeoJSON {
  type: 'FeatureCollection';
  features: RouteFeature[];
}

export interface GeoProvenance {
  provider: 'openrouteservice';
  profile: 'foot-walking';
  mode: 'live' | 'recorded';
  retrieved_at: string;
  endpoint: string;
  metadata: Record<string, unknown>;
}

export interface RoutingProvenance {
  matrix?: GeoProvenance | null;
  directions?: GeoProvenance | null;
}

export type NoRouteReason =
  | 'no_candidates'
  | 'unreachable'
  | 'budget_exceeded'
  | 'ors_unconfigured'
  | 'ors_timeout'
  | 'ors_unavailable'
  | 'ors_invalid_response';

export interface PlanBase {
  start_anchor_id: AnchorID;
  start_anchor: Anchor;
  requested_duration_minutes: number;
  round_trip: boolean;
  language: Language;
  retrieval_mode: RetrievalMode;
  recommendation: string;
  warnings: string[];
  routing_provenance: RoutingProvenance;
  dataset: DatasetMetadata;
}

export interface RoutePlanSuccess extends PlanBase {
  status: 'success';
  estimated_total_minutes: number;
  walking_minutes: number;
  visiting_minutes: number;
  total_distance_meters: number;
  stops: RouteStop[];
  route_geojson: RouteGeoJSON;
}

export interface RoutePlanUnavailable extends PlanBase {
  status: 'no_route';
  reason: NoRouteReason;
  estimated_total_minutes: null;
  walking_minutes: null;
  visiting_minutes: null;
  total_distance_meters: null;
  stops: [];
  route_geojson: null;
}

export type RoutePlanResponse = RoutePlanSuccess | RoutePlanUnavailable;

export interface RoutePlanRequest {
  start_anchor_id: AnchorID;
  duration_minutes: number; // 30..180
  query: string;
  round_trip?: boolean;
  language?: Language;
}

export interface WeatherResponse {
  status: 'available' | 'unknown';
  anchor_id: AnchorID;
  temperature_c: number | null;
  wind_speed_kmh: number | null;
  warnings: string[];
}

export type H3ResolveResponse = {
  status: 'matched';
  start_anchor_id: AnchorID;
  resolution: 8;
  distance_estimate_m: number;
  warnings: string[];
} | {
  status: 'no_nearby_anchor';
  reason: 'outside_supported_area' | 'no_anchor_within_radius';
  resolution: 8;
  warnings: string[];
};
