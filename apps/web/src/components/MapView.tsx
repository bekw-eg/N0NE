import React, { useEffect, useRef, useState } from 'react';
import * as maplibregl from 'maplibre-gl';
import maplibreWorkerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url';
import * as h3 from 'h3-js';
import { Layers, ZoomIn, ZoomOut, Compass, MapPin } from 'lucide-react';
import type { FeatureCollection, GeoJSON } from 'geojson';
import type { RouteStop, Anchor, RouteGeoJSON } from '../types/api';

// Vite relocates the ESM entry; publish its standalone worker as a hashed asset.
maplibregl.setWorkerUrl(maplibreWorkerUrl);

interface MapViewProps {
  stops?: RouteStop[];
  selectedStopId?: string | null;
  startAnchor?: Anchor | null;
  routeGeoJSON?: RouteGeoJSON | null;
  isochronesGeoJSON?: FeatureCollection | null;
  userH3Cell?: string | null;
  onSelectStop?: (stop: RouteStop) => void;
  onSelectAnchor?: (anchor: Anchor) => void;
  className?: string;
}


// Astana Coordinates: Center near EXPO / Nurzhol
const ASTANA_CENTER: [number, number] = [71.4162, 51.0893];
const DEFAULT_ZOOM = 13.5;

// Names and categories come from external OSM/API data, never insert raw HTML.
const escapeHTML = (value: string) => value.replace(/[&<>"']/g, character => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
}[character]!));

// Free Dark Map Style with OSM Fallback
const DARK_MATTER_STYLE = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json';

const OSM_FALLBACK_STYLE: maplibregl.StyleSpecification = {
  version: 8,
  sources: {
    'osm-tiles': {
      type: 'raster',
      tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
      tileSize: 256,
      attribution: '© <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap</a> contributors',
    },
  },
  layers: [
    {
      id: 'osm-tiles-layer',
      type: 'raster',
      source: 'osm-tiles',
      minzoom: 0,
      maxzoom: 19,
    },
  ],
};

export const MapView: React.FC<MapViewProps> = ({
  stops = [],
  selectedStopId = null,
  startAnchor = null,
  routeGeoJSON = null,
  isochronesGeoJSON = null,
  userH3Cell = null,
  onSelectStop,
  onSelectAnchor,
  className = '',
}) => {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const markersRef = useRef<maplibregl.Marker[]>([]);
  const startAnchorMarkerRef = useRef<maplibregl.Marker | null>(null);
  const [mapLoaded, setMapLoaded] = useState(false);
  const [mapError, setMapError] = useState<string | null>(null);
  const isMapLoadedRef = useRef(false);

  // Initialize Map
  useEffect(() => {
    if (!mapContainerRef.current || mapRef.current) return;

    let mapInstance: maplibregl.Map;
    let usingFallback = false;

    try {
      mapInstance = new maplibregl.Map({
        container: mapContainerRef.current,
        style: DARK_MATTER_STYLE,
        center: ASTANA_CENTER,
        zoom: DEFAULT_ZOOM,
        attributionControl: false,
      });

      // Add navigation controls
      mapInstance.addControl(
        new maplibregl.NavigationControl({ showCompass: true, showZoom: false }),
        'bottom-right'
      );
      mapInstance.addControl(
        new maplibregl.AttributionControl({ compact: true }),
        'bottom-left'
      );

      mapInstance.on('load', () => {
        isMapLoadedRef.current = true;
        setMapLoaded(true);
        mapInstance.resize();
      });

      mapInstance.on('error', (e: { error?: unknown }) => {
        // If vector tiles fail to load (e.g. offline/network), fallback cleanly to OSM raster tiles
        if (!isMapLoadedRef.current && e.error && !usingFallback) {
          usingFallback = true;
          console.warn('Map style load issue, applying OSM raster fallback:', e.error);
          try {
            mapInstance.setStyle(OSM_FALLBACK_STYLE);
          } catch {
            setMapError('Не удалось загрузить подложку карты');
          }
        } else if (!isMapLoadedRef.current && e.error && usingFallback) {
          setMapError('Не удалось загрузить подложку карты');
        }
      });

      mapRef.current = mapInstance;
    } catch (err) {
      console.error('MapLibre initialization failed:', err);
      setTimeout(() => setMapError('Ошибка инициализации карты'), 0);
    }


    // Resize observer for responsive layout changes
    const resizeObserver = new ResizeObserver(() => {
      if (mapRef.current) {
        mapRef.current.resize();
      }
    });

    if (mapContainerRef.current) {
      resizeObserver.observe(mapContainerRef.current);
    }

    return () => {
      resizeObserver.disconnect();
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
      }
      isMapLoadedRef.current = false;
    };
  }, []);

  // Sync Start Anchor Marker
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapLoaded) return;

    if (startAnchorMarkerRef.current) {
      startAnchorMarkerRef.current.remove();
      startAnchorMarkerRef.current = null;
    }

    if (startAnchor && startAnchor.location) {
      const { longitude, latitude } = startAnchor.location;
      if (
        typeof longitude === 'number' &&
        typeof latitude === 'number' &&
        !isNaN(longitude) &&
        !isNaN(latitude)
      ) {
        const el = document.createElement('div');
        el.className = 'maplibre-marker-container';
        el.innerHTML = `
          <div class="relative flex items-center justify-center">
            <div class="absolute -inset-1.5 rounded-full bg-cyan-400/40 animate-ping"></div>
            <div class="relative flex h-8 w-8 items-center justify-center rounded-full bg-slate-950 border-2 border-cyan-400 text-cyan-300 shadow-lg shadow-cyan-950/80">
              <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"></path>
                <line x1="4" y1="22" x2="4" y2="15"></line>
              </svg>
            </div>
          </div>
        `;

        el.addEventListener('click', () => {
          onSelectAnchor?.(startAnchor);
        });

        const popup = new maplibregl.Popup({ offset: 25, closeButton: false }).setHTML(`
          <div class="text-xs">
            <div class="font-bold text-cyan-400 uppercase tracking-wider text-[10px]">Точка старта</div>
            <div class="font-semibold text-slate-100 mt-0.5">${escapeHTML(startAnchor.name)}</div>
            <div class="text-[10px] text-slate-400 mt-0.5">${
              startAnchor.coordinate_kind === 'mapped_entrance'
                ? 'Размеченный вход OSM'
                : 'Координаты центра объекта'
            }</div>
          </div>
        `);

        startAnchorMarkerRef.current = new maplibregl.Marker({ element: el })
          .setLngLat([longitude, latitude])
          .setPopup(popup)
          .addTo(map);
      }
    }
  }, [mapLoaded, startAnchor, onSelectAnchor]);

  // Sync POI Markers
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapLoaded) return;

    // Remove previous POI markers
    markersRef.current.forEach((marker) => marker.remove());
    markersRef.current = [];

    // Add new POI markers
    stops.forEach((stop) => {
      if (
        typeof stop.longitude !== 'number' ||
        typeof stop.latitude !== 'number' ||
        isNaN(stop.longitude) ||
        isNaN(stop.latitude)
      ) {
        return;
      }

      const isSelected = selectedStopId === stop.id;

      const el = document.createElement('div');
      el.className = `maplibre-marker-container ${isSelected ? 'active' : ''}`;
      el.innerHTML = `
        <div class="relative flex items-center justify-center">
          ${
            isSelected
              ? '<div class="absolute -inset-2 rounded-full bg-cyan-400/40 animate-pulse"></div>'
              : ''
          }
          <div class="relative flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold transition-all shadow-md ${
            isSelected
              ? 'bg-cyan-400 text-slate-950 ring-3 ring-cyan-200 scale-110 shadow-cyan-400/50'
              : 'bg-slate-900 text-slate-200 border-2 border-slate-600 hover:border-cyan-400 hover:text-cyan-300'
          }">
            ${stop.order}
          </div>
        </div>
      `;

      el.addEventListener('click', () => {
        onSelectStop?.(stop);
      });

      const popup = new maplibregl.Popup({ offset: 20, closeButton: false }).setHTML(`
        <div class="text-xs">
          <div class="flex items-center gap-1.5">
            <span class="inline-block px-1.5 py-0.2 rounded bg-cyan-950 text-cyan-400 text-[10px] font-bold">#${
              stop.order
            }</span>
            <span class="text-slate-400 text-[10px] uppercase font-semibold">${escapeHTML(stop.category)}</span>
          </div>
          <div class="font-bold text-slate-100 mt-1">${escapeHTML(stop.name || 'Точка интереса')}</div>
          ${
            stop.visiting_minutes
              ? `<div class="text-[10px] text-amber-300 mt-1">Оценка визита: ~${stop.visiting_minutes} мин</div>`
              : ''
          }
        </div>
      `);

      const marker = new maplibregl.Marker({ element: el })
        .setLngLat([stop.longitude, stop.latitude])
        .setPopup(popup)
        .addTo(map);

      if (isSelected) {
        popup.addTo(map);
      }

      markersRef.current.push(marker);
    });
  }, [mapLoaded, stops, selectedStopId, onSelectStop]);

  // Sync Route GeoJSON Layer
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapLoaded) return;

    const sourceId = 'viberoute-walk-path';
    const glowLayerId = 'viberoute-walk-path-glow';
    const lineLayerId = 'viberoute-walk-path-line';

    const existingSource = map.getSource(sourceId) as maplibregl.GeoJSONSource | undefined;

    if (routeGeoJSON && routeGeoJSON.features && routeGeoJSON.features.length > 0) {
      if (existingSource) {
        existingSource.setData(routeGeoJSON as unknown as GeoJSON);
      } else {
        map.addSource(sourceId, {
          type: 'geojson',
          data: routeGeoJSON as unknown as GeoJSON,
        });


        // Glow Layer for vibrant urban neon aesthetic
        map.addLayer({
          id: glowLayerId,
          type: 'line',
          source: sourceId,
          layout: {
            'line-join': 'round',
            'line-cap': 'round',
          },
          paint: {
            'line-color': '#06b6d4',
            'line-width': 8,
            'line-opacity': 0.35,
            'line-blur': 4,
          },
        });

        // Walking Line Layer
        map.addLayer({
          id: lineLayerId,
          type: 'line',
          source: sourceId,
          layout: {
            'line-join': 'round',
            'line-cap': 'round',
          },
          paint: {
            'line-color': '#38bdf8',
            'line-width': 4.5,
            'line-opacity': 0.95,
          },
        });
      }
    } else {
      // Remove layer if route is null or cleared
      if (map.getLayer(lineLayerId)) map.removeLayer(lineLayerId);
      if (map.getLayer(glowLayerId)) map.removeLayer(glowLayerId);
      if (map.getSource(sourceId)) map.removeSource(sourceId);
    }
  }, [mapLoaded, routeGeoJSON]);

  // Sync Isochrones Layer
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapLoaded) return;

    const sourceId = 'viberoute-isochrones';
    const fillLayerId = 'viberoute-isochrones-fill';
    const outlineLayerId = 'viberoute-isochrones-outline';

    const existingSource = map.getSource(sourceId) as maplibregl.GeoJSONSource | undefined;

    if (isochronesGeoJSON && isochronesGeoJSON.features && isochronesGeoJSON.features.length > 0) {
      if (existingSource) {
        existingSource.setData(isochronesGeoJSON);
      } else {
        map.addSource(sourceId, {
          type: 'geojson',
          data: isochronesGeoJSON,
        });

        map.addLayer({
          id: fillLayerId,
          type: 'fill',
          source: sourceId,
          paint: {
            'fill-color': '#6366f1',
            'fill-opacity': 0.12,
          },
        });

        map.addLayer({
          id: outlineLayerId,
          type: 'line',
          source: sourceId,
          paint: {
            'line-color': '#818cf8',
            'line-width': 1.5,
            'line-dasharray': [3, 2],
            'line-opacity': 0.7,
          },
        });
      }
    } else {
      if (map.getLayer(outlineLayerId)) map.removeLayer(outlineLayerId);
      if (map.getLayer(fillLayerId)) map.removeLayer(fillLayerId);
      if (map.getSource(sourceId)) map.removeSource(sourceId);
    }
  }, [mapLoaded, isochronesGeoJSON]);

  // Sync H3 Approximate User Cell Layer
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapLoaded) return;

    const sourceId = 'viberoute-h3-cell';
    const fillLayerId = 'viberoute-h3-cell-fill';
    const outlineLayerId = 'viberoute-h3-cell-outline';

    const existingSource = map.getSource(sourceId) as maplibregl.GeoJSONSource | undefined;

    if (userH3Cell) {
      try {
        // H3 cell to boundary returns [ [lat, lng], [lat, lng], ... ]
        const rawBoundary = h3.cellToBoundary(userH3Cell);
        if (rawBoundary && rawBoundary.length > 0) {
          // Convert to GeoJSON [lng, lat] and close polygon
          const coordinates = rawBoundary.map(([lat, lng]) => [lng, lat]);
          coordinates.push(coordinates[0]);

          const h3GeoJSON: FeatureCollection = {
            type: 'FeatureCollection',

            features: [
              {
                type: 'Feature',
                properties: {
                  h3Index: userH3Cell,
                  description: 'Приблизительная зона местоположения (H3)',
                },
                geometry: {
                  type: 'Polygon',
                  coordinates: [coordinates],
                },
              },
            ],
          };

          if (existingSource) {
            existingSource.setData(h3GeoJSON);
          } else {
            map.addSource(sourceId, {
              type: 'geojson',
              data: h3GeoJSON,
            });

            map.addLayer({
              id: fillLayerId,
              type: 'fill',
              source: sourceId,
              paint: {
                'fill-color': '#0ea5e9',
                'fill-opacity': 0.15,
              },
            });

            map.addLayer({
              id: outlineLayerId,
              type: 'line',
              source: sourceId,
              paint: {
                'line-color': '#38bdf8',
                'line-width': 2,
                'line-dasharray': [4, 3],
                'line-opacity': 0.85,
              },
            });
          }
        }
      } catch {
        // Do not log location-sensitive cell values or parsing diagnostics.
      }
    } else {
      if (map.getLayer(outlineLayerId)) map.removeLayer(outlineLayerId);
      if (map.getLayer(fillLayerId)) map.removeLayer(fillLayerId);
      if (map.getSource(sourceId)) map.removeSource(sourceId);
    }
  }, [mapLoaded, userH3Cell]);

  // Fit bounds when route or stops change
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapLoaded) return;

    const bounds = new maplibregl.LngLatBounds();
    let hasPoints = false;

    // Include route line coordinates if present
    if (routeGeoJSON && routeGeoJSON.features && routeGeoJSON.features.length > 0) {
      const coords = routeGeoJSON.features[0].geometry.coordinates;
      coords.forEach(([lng, lat]) => {
        if (!isNaN(lng) && !isNaN(lat)) {
          bounds.extend([lng, lat]);
          hasPoints = true;
        }
      });
    }

    // Include stops
    stops.forEach((stop) => {
      if (!isNaN(stop.longitude) && !isNaN(stop.latitude)) {
        bounds.extend([stop.longitude, stop.latitude]);
        hasPoints = true;
      }
    });

    // Include start anchor
    if (startAnchor && startAnchor.location) {
      const { longitude, latitude } = startAnchor.location;
      if (!isNaN(longitude) && !isNaN(latitude)) {
        bounds.extend([longitude, latitude]);
        hasPoints = true;
      }
    }

    if (hasPoints) {
      try {
        map.fitBounds(bounds, {
          padding: { top: 60, bottom: 60, left: 60, right: 60 },
          maxZoom: 16,
          duration: 1000,
        });
      } catch (e) {
        console.warn('fitBounds error:', e);
      }
    }
  }, [mapLoaded, routeGeoJSON, stops, startAnchor]);

  // Fly to selected stop when selected externally
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapLoaded || !selectedStopId) return;

    const activeStop = stops.find((s) => s.id === selectedStopId);
    if (activeStop && !isNaN(activeStop.longitude) && !isNaN(activeStop.latitude)) {
      map.flyTo({
        center: [activeStop.longitude, activeStop.latitude],
        zoom: Math.max(map.getZoom(), 15),
        duration: 800,
      });
    }
  }, [mapLoaded, selectedStopId, stops]);

  return (
    <div className={`relative h-full w-full overflow-hidden rounded-2xl border border-slate-800 bg-slate-950 shadow-2xl ${className}`}>
      {/* Map container */}
      <div ref={mapContainerRef} className="h-full w-full" />

      {/* Map Status Overlays */}
      {mapError && (
        <div className="absolute inset-0 flex items-center justify-center bg-slate-950/80 p-4 text-center">
          <div className="rounded-xl border border-red-500/30 bg-red-950/50 p-4 text-sm text-red-200">
            <p className="font-semibold">{mapError}</p>
            <p className="mt-1 text-xs text-red-300/80">Проверьте подключение к интернету или доступ к тайлам.</p>
          </div>
        </div>
      )}

      {/* Top Map Badges Bar */}
      <div className="absolute top-4 left-4 right-4 flex items-center justify-between pointer-events-none">
        <div className="flex flex-wrap items-center gap-2 pointer-events-auto">
          <div className="glass-panel flex items-center gap-2 rounded-xl px-3 py-1.5 text-xs font-medium text-slate-200 shadow-md">
            <MapPin className="h-3.5 w-3.5 text-cyan-400" />
            <span>Астана, Казахстан</span>
          </div>

          {userH3Cell && (
            <div className="glass-panel flex items-center gap-1.5 rounded-xl px-2.5 py-1 text-[11px] text-cyan-300 border-cyan-500/30">
              <span className="h-2 w-2 rounded-full bg-cyan-400 animate-pulse"></span>
              <span>H3: {userH3Cell}</span>
            </div>
          )}

          {isochronesGeoJSON && (
            <div className="glass-panel flex items-center gap-1.5 rounded-xl px-2.5 py-1 text-[11px] text-indigo-300 border-indigo-500/30">
              <Layers className="h-3 w-3 text-indigo-400" />
              <span>Зона доступности</span>
            </div>
          )}
        </div>

        {/* Map custom control buttons */}
        <div className="flex items-center gap-1 glass-panel rounded-xl p-1 pointer-events-auto shadow-md">
          <button
            type="button"
            title="Приблизить"
            onClick={() => mapRef.current?.zoomIn()}
            className="flex h-7 w-7 items-center justify-center rounded-lg text-slate-300 hover:bg-slate-800 hover:text-white transition-colors"
          >
            <ZoomIn className="h-4 w-4" />
          </button>
          <button
            type="button"
            title="Отдалить"
            onClick={() => mapRef.current?.zoomOut()}
            className="flex h-7 w-7 items-center justify-center rounded-lg text-slate-300 hover:bg-slate-800 hover:text-white transition-colors"
          >
            <ZoomOut className="h-4 w-4" />
          </button>
          <button
            type="button"
            title="Сбросить на центр Астаны"
            onClick={() => {
              mapRef.current?.flyTo({
                center: ASTANA_CENTER,
                zoom: DEFAULT_ZOOM,
                duration: 900,
              });
            }}
            className="flex h-7 w-7 items-center justify-center rounded-lg text-slate-300 hover:bg-slate-800 hover:text-white transition-colors"
          >
            <Compass className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Legend at bottom left */}
      <div className="absolute bottom-5 left-4 pointer-events-auto hidden sm:block">
        <div className="glass-panel rounded-xl px-3 py-2 text-[11px] text-slate-300 space-y-1.5 border border-slate-800 shadow-lg">
          <div className="flex items-center gap-2">
            <span className="flex h-3 w-3 items-center justify-center rounded-full bg-cyan-400 ring-2 ring-cyan-200"></span>
            <span>Старт маршрута</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="flex h-3 w-3 items-center justify-center rounded-full bg-slate-900 border border-slate-500 font-bold text-[8px] text-white">
              #
            </span>
            <span>Точки визита (POI)</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="h-0.5 w-4 bg-cyan-400 rounded-full"></span>
            <span>Пешеходная геометрия (ORS)</span>
          </div>
        </div>
      </div>
    </div>
  );
};
