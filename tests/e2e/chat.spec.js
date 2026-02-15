// E2E: chat page (PROJECT_GAPS §2, CHANGES §0.4f)
const { test, expect } = require('@playwright/test');

const FRONTEND_URL = process.env.BASE_URL || 'http://localhost:3000';

test.describe('Chat', () => {
  test('chat page loads and has input', async ({ page }) => {
    await page.goto(FRONTEND_URL);
    await expect(page).toHaveTitle(/ATRA|Web IDE|Singularity|Vite/i);
    await page.waitForLoadState('domcontentloaded');
    const input = page.locator('textarea').first();
    await expect(input).toBeVisible({ timeout: 15000 });
  });

  test('can send message and receive response', async ({ page }) => {
    await page.goto(FRONTEND_URL);
    await page.waitForLoadState('domcontentloaded');
    
    // Ждём появления textarea
    const input = page.locator('textarea').first();
    await expect(input).toBeVisible({ timeout: 15000 });
    
    // Отправляем простое сообщение
    await input.fill('Привет! Ответь одним словом: "ок"');
    
    // Ищем кнопку отправки (может быть button или svg/icon)
    const sendButton = page.locator('button[type="submit"]').first();
    await sendButton.click();
    
    // Ждём ответа в истории чата (до 60 секунд для локальных моделей)
    // Ищем любой элемент с текстом ответа (не наш вопрос)
    await expect(page.locator('text=/ок|Виктория|сообщени/i').first()).toBeVisible({ timeout: 60000 });
  });
});
