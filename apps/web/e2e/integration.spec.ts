import { test, expect, type Page } from '@playwright/test';
import { getResolution, isValidCell } from 'h3-js';

const planPath = '**/api/v1/routes/plan';
const weatherPath = '**/api/v1/weather?*';

async function submit(page: Page) {
  await page.getByRole('button', { name: 'Построить маршрут', exact: true }).click();
}

test('starts without demo route, H3 location or demo isochrone', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('button', { name: 'Показать демо' })).toBeVisible();
  await expect(page.locator('main')).toContainText('Выберите параметры');
  await expect(page.getByText('Зона доступности', { exact: true })).toHaveCount(0);
  await expect(page.locator('main')).not.toContainText('Демонстрационные данные');
  await expect(page.getByText(/^H3:/)).toHaveCount(0);
});

test('live EXPO 60 minutes: Vite proxy → FastAPI → ORS → map', async ({ page }, testInfo) => {
  test.skip(process.env.RUN_LIVE_ORS !== '1', 'Opt in with RUN_LIVE_ORS=1 and a configured backend');
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
  const workerResponse = page.waitForResponse(response => response.url().includes('maplibre-gl-worker.mjs') && response.ok());
  const browserAPIRequests: string[] = [];
  page.on('request', request => { if (request.url().includes('/api/')) browserAPIRequests.push(request.url()); });
  await page.goto('/');
  await workerResponse;
  await page.getByRole('combobox').selectOption('expo_nur_alem');
  await page.getByRole('textbox').fill('Хочу спокойную прогулку возле EXPO');
  const responsePromise = page.waitForResponse(response => response.url().endsWith('/api/v1/routes/plan'));
  await submit(page);
  const response = await responsePromise;
  const plan = await response.json();
  expect(response.status()).toBe(200);
  expect(plan.status).toBe('success');
  expect(plan.requested_duration_minutes).toBe(60);
  expect(plan.routing_provenance.directions.mode).toBe('live');
  expect(plan.route_geojson.features[0].geometry.coordinates.length).toBeGreaterThan(2);
  expect(plan.estimated_total_minutes).toBeLessThanOrEqual(60);
  await expect(page.locator('main')).toContainText(`${(plan.total_distance_meters / 1000).toFixed(2)} км`);
  await expect(page.locator('main')).toContainText(`${plan.walking_minutes.toFixed(1)} мин`);
  await expect(page.locator('main')).toContainText(`${plan.visiting_minutes} мин`);
  for (const stop of plan.stops) {
    if (stop.name) await expect(page.locator('main')).toContainText(stop.name);
  }
  for (const warning of plan.warnings) {
    if (!['visit_times_are_planned_estimates', 'entrance_and_accessibility_not_verified'].includes(warning)) {
      await expect(page.locator('main')).toContainText(warning);
    }
  }
  await expect(page.locator('.maplibregl-marker')).toHaveCount(plan.stops.length + 1);
  await expect(page.locator('canvas.maplibregl-canvas')).toBeVisible();
  expect(browserAPIRequests.every(url => new URL(url).port === '5173')).toBe(true);
  await testInfo.attach('live-plan.json', { body: JSON.stringify(plan, null, 2), contentType: 'application/json' });
  await page.waitForTimeout(1500); // Let camera animation and actual map tiles finish before visual QA.
  await page.screenshot({ path: testInfo.outputPath('desktop-live.png') });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole('button', { name: 'Карта', exact: true }).click();
  await expect(page.locator('canvas.maplibregl-canvas')).toBeVisible();
  await expect.poll(() => page.locator('canvas.maplibregl-canvas').evaluate(canvas => canvas.getBoundingClientRect().width)).toBeGreaterThan(300);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.waitForTimeout(1500);
  await page.screenshot({ path: testInfo.outputPath('mobile-live.png') });
  expect(errors).toEqual([]);
  await page.getByRole('button', { name: 'Маршрут', exact: true }).click();
  await expect(page.locator('main')).toContainText(`${(plan.total_distance_meters / 1000).toFixed(2)} км`);
});

test('live pizza intent: no substitution at EXPO; real pizzeria from Botanical Garden', async ({ page }, testInfo) => {
  test.skip(process.env.RUN_LIVE_ORS !== '1', 'Opt in with RUN_LIVE_ORS=1 and a configured backend');
  await page.goto('/');
  await page.getByRole('combobox').selectOption('expo_nur_alem');
  await page.getByRole('textbox').fill('хочу пиццу');
  let responsePromise = page.waitForResponse(response => response.url().endsWith('/api/v1/routes/plan'));
  await submit(page);
  const unavailable = await (await responsePromise).json();
  expect(unavailable.status).toBe('no_route');
  expect(unavailable.stops).toEqual([]);
  expect(unavailable.route_geojson).toBeNull();
  await expect(page.locator('main')).toContainText('не найдено пиццерии в пределах 2500 м');

  await page.getByRole('combobox').selectOption('botanical_garden');
  responsePromise = page.waitForResponse(response => response.url().endsWith('/api/v1/routes/plan'));
  await submit(page);
  const plan = await (await responsePromise).json();
  expect(plan.status).toBe('success');
  expect(plan.routing_provenance.directions.mode).toBe('live');
  expect(plan.stops.length).toBeGreaterThan(0);
  for (const stop of plan.stops) {
    expect(stop.name).toMatch(/pizza|пицца/i);
    expect(stop.selection_source).toBe('retrieval');
    await expect(page.locator('main')).toContainText(stop.name);
  }
  expect(plan.warnings).not.toContain('nearby_fallback_not_query_match');
  await expect(page.locator('.maplibregl-marker')).toHaveCount(plan.stops.length + 1);
  await expect(page.locator('main')).not.toContainText('Категория OSM: artwork');
  await testInfo.attach('pizza-live-plan.json', { body: JSON.stringify(plan, null, 2), contentType: 'application/json' });
});

for (const scenario of [
  { port: 8001, reason: 'unreachable' },
  { port: 8002, reason: 'ors_unavailable' },
]) {
  test(`real FastAPI no_route from simulated upstream: ${scenario.reason}`, async ({ page }) => {
    await page.route(planPath, async route => {
      const response = await route.fetch({ url: `http://127.0.0.1:${scenario.port}/api/v1/routes/plan` });
      const data = await response.json();
      expect(data.route_geojson).toBeNull();
      expect(data.stops).toEqual([]);
      await route.fulfill({ response });
    });
    await page.goto('/');
    // A previous demo must be removed when a real request fails.
    await page.getByRole('button', { name: 'Показать демо' }).click();
    await submit(page);
    await expect(page.locator('main')).toContainText(`Причина: ${scenario.reason}`);
    await expect(page.locator('main')).not.toContainText('Демонстрационные данные');
    await expect(page.getByText('Зона доступности', { exact: true })).toHaveCount(0);
    await expect(page.locator('.maplibregl-marker')).toHaveCount(1);
  });
}

test('backend network error clears route; demo requires explicit choice', async ({ page }) => {
  await page.route(planPath, route => route.abort('connectionrefused'));
  await page.goto('/');
  await page.getByRole('button', { name: 'Показать демо' }).click();
  await expect(page.locator('main')).toContainText('Демонстрационные данные');
  await submit(page);
  await expect(page.getByRole('alert')).toContainText('Не удалось связаться с API');
  await expect(page.locator('main')).not.toContainText('Демонстрационные данные');
  await expect(page.locator('.maplibregl-marker')).toHaveCount(1);
  await page.getByRole('button', { name: 'Показать демо' }).click();
  await expect(page.locator('main')).toContainText('Демонстрационные данные');
  await page.getByRole('button', { name: 'Выйти из демо' }).click();
  await expect(page.locator('main')).toContainText('Выберите параметры');
});

test('weather outage returns unknown/null from real FastAPI', async ({ page }) => {
  await page.route(weatherPath, async route => {
    const response = await route.fetch({ url: 'http://127.0.0.1:8001/api/v1/weather?start_anchor_id=mega_silk_way' });
    expect((await response.json()).status).toBe('unknown');
    await route.fulfill({ response });
  });
  await page.goto('/');
  await expect(page.getByTestId('weather')).toContainText('Погодные условия неизвестны');
  await expect(page.getByTestId('weather')).toContainText('Температура: Нет данных');
  await expect(page.getByTestId('weather')).toContainText('Ветер: Нет данных');
});

test('weather partial values, zero and warnings; HTTP failure', async ({ page }) => {
  await page.route(weatherPath, route => route.fulfill({ json: {
    status: 'available', anchor_id: 'mega_silk_way', temperature_c: null,
    wind_speed_kmh: 0, warnings: ['weather_low_temperature'],
  } }));
  await page.goto('/');
  await expect(page.getByTestId('weather')).toContainText('Температура: Нет данных');
  await expect(page.getByTestId('weather')).toContainText('Ветер: 0.0 км/ч');
  await expect(page.getByTestId('weather')).toContainText('Низкая температура');
  await page.route(weatherPath, route => route.abort('connectionrefused'));
  await page.reload();
  await expect(page.getByTestId('weather')).toContainText('Погода недоступна');
});

test('geolocation denial leaves manual choice and sends no H3', async ({ page, context }) => {
  await context.clearPermissions();
  let privacyRequests = 0;
  page.on('request', request => { if (request.url().includes('/privacy/')) privacyRequests++; });
  await page.goto('/');
  await page.getByRole('button', { name: 'Выбрать старт по моей геолокации' }).click();
  await expect(page.getByRole('status')).toContainText('Доступ к геолокации отклонён');
  await page.getByRole('combobox').selectOption('expo_nur_alem');
  await expect(page.getByRole('combobox')).toHaveValue('expo_nur_alem');
  expect(privacyRequests).toBe(0);
});

test('consented test GPS → resolution-8 H3 → real FastAPI anchor; no persistence', async ({ page, context }) => {
  await context.grantPermissions(['geolocation']);
  await context.setGeolocation({ latitude: 51.089252, longitude: 71.4161925 });
  await page.goto('/');
  const requestPromise = page.waitForRequest('**/api/v1/privacy/resolve-h3');
  const responsePromise = page.waitForResponse('**/api/v1/privacy/resolve-h3');
  await page.getByRole('button', { name: 'Выбрать старт по моей геолокации' }).click();
  const request = await requestPromise;
  const body = request.postDataJSON();
  expect(Object.keys(body)).toEqual(['h3_cell']);
  expect(isValidCell(body.h3_cell)).toBe(true);
  expect(getResolution(body.h3_cell)).toBe(8);
  expect(new URL(request.url()).search).toBe('');
  const data = await (await responsePromise).json();
  expect(data.status).toBe('matched');
  await expect(page.getByRole('combobox')).toHaveValue(data.start_anchor_id);
  await expect(page.getByRole('status')).toContainText('приблизительной области H3');
  const storage = await page.evaluate(() => ({ local: { ...localStorage }, session: { ...sessionStorage }, url: location.href }));
  expect(JSON.stringify(storage)).not.toContain(body.h3_cell);
  expect(JSON.stringify(storage)).not.toContain('51.089252');
  await page.getByRole('button', { name: 'Очистить местоположение' }).click();
  await expect(page.getByText(/^H3:/)).toHaveCount(0);
  await page.reload();
  await expect(page.getByText(/^H3:/)).toHaveCount(0);
  await expect(page.getByRole('combobox')).toHaveValue('mega_silk_way');
});
