const fs = require('fs');
const os = require('os');
const path = require('path');

const { test, expect } = require('@playwright/test');

const E2E_DIR = path.join(os.tmpdir(), 'stats-sheets-e2e');
const PUBLIC_CSV_URL = 'https://raw.githubusercontent.com/plotly/datasets/master/iris.csv';

test.beforeAll(async () => {
  fs.mkdirSync(E2E_DIR, { recursive: true });
});

test.afterAll(async () => {
  for (const name of fs.readdirSync(E2E_DIR)) {
    if (name.startsWith('e2e-iris')) {
      fs.rmSync(path.join(E2E_DIR, name), { force: true, recursive: true });
    }
  }
});

test('app loads and connects to backend', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('.nav-tab[data-tab="datasets-tab"]')).toBeVisible();
  await page.locator('.nav-tab[data-tab="datasets-tab"]').click();
  await expect(page.locator('#datasetsList')).toBeVisible({ timeout: 15000 });
  const toast = page.locator('#toast');
  await expect(toast).not.toContainText('Connection error', { timeout: 5000 });
});

test('blocks SSRF download URLs', async ({ request }) => {
  const res = await request.post('/download', {
    data: {
      url: 'http://127.0.0.1/data.csv',
      dataset_name: 'ssrf-test',
      format: 'csv',
      target_dir: E2E_DIR,
    },
  });
  expect(res.status()).toBe(400);
  const body = await res.json();
  expect(body.error_code).toBe('url_localhost');
});

test('CSV download completes via API', async ({ request }) => {
  test.skip(!process.env.RUN_NETWORK_E2E, 'Set RUN_NETWORK_E2E=1 to run networked download E2E');

  const res = await request.post('/download', {
    data: {
      url: PUBLIC_CSV_URL,
      dataset_name: 'e2e-iris',
      format: 'csv',
      target_dir: E2E_DIR,
    },
  });
  expect(res.ok()).toBeTruthy();
  const { job_id: jobId } = await res.json();
  expect(jobId).toBeTruthy();

  const deadline = Date.now() + 90000;
  let status = null;
  while (Date.now() < deadline) {
    const poll = await request.get(`/download/status?job_id=${encodeURIComponent(jobId)}`);
    status = await poll.json();
    if (status.done) break;
    await new Promise((r) => setTimeout(r, 500));
  }

  expect(status).toBeTruthy();
  expect(status.error_code).toBeFalsy();
  expect(status.file_path).toBeTruthy();
  expect(fs.existsSync(status.file_path)).toBeTruthy();
});
