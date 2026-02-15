// E2E: health endpoints (PROJECT_GAPS §2, CHANGES §0.4f)
const { test, expect } = require('@playwright/test');

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8080';

test.describe('Health', () => {
  test('GET /health returns 200', async ({ request }) => {
    const res = await request.get(`${BACKEND_URL}/health`);
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    expect(['healthy', 'degraded', 'unhealthy']).toContain(body.status);
  });
});
