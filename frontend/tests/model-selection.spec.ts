import { test, expect } from '@playwright/test';

test.use({ baseURL: process.env.FORMA_TEST_URL || 'http://127.0.0.1:8000' });

test('manual model survives reload and image upload', async ({ page }) => {
  const model = {id: 'text-model', name: 'Text model', provider: 'ollama', chat_compatible: true, supports_vision: false};
  await page.addInitScript(() => {
    localStorage.setItem('forma-provider', 'ollama');
    localStorage.setItem('forma-model', 'text-model');
  });
  await page.route('**/api/models?*', async route => {
    await route.fulfill({json: {provider: 'ollama', models: ['text-model'], model_details: [model],
      default: 'text-model', providers: [{id: 'ollama', name: 'Ollama', working: true, models: [model]}]}});
  });
  await page.route('**/api/conversations**', async route => {
    await route.fulfill({json: route.request().method() === 'POST' ? {id: 'test-chat', title: 'New chat'} : []});
  });
  await page.goto('/');
  const selected = page.getByRole('button', {name: 'Select model: currently Text model'});
  await expect(selected).toBeVisible();
  await page.reload();
  await expect(selected).toBeVisible();
  await page.locator('input[type=file]').setInputFiles({name: 'photo.png', mimeType: 'image/png', buffer: Buffer.from('test')});
  await expect(page.getByText('Your selected model does not have verified image support.', {exact: false})).toBeVisible();
  await expect(selected).toBeVisible();
  expect(await page.evaluate(() => localStorage.getItem('forma-model'))).toBe('text-model');
});

test('task menu shows verified choices and an honest unsupported state', async ({page}) => {
  const models = [1, 2, 3].map(i => ({id: `vision-${i}`, name: `Vision ${i}`, provider: 'ollama', chat_compatible: true, supports_vision: true}));
  await page.route('**/api/models?*', route => route.fulfill({json: {
    provider: 'ollama', models: models.map(m => m.id), model_details: models,
    providers: [{id: 'ollama', name: 'Ollama', working: true, models}],
    feature_coverage: {
      vision: {label: 'Image understanding', status: 'ready', message: '3 currently listed options.', options: models.map(m => ({provider: 'ollama', model: m.id, reason: 'Image understanding'}))},
      image_generation: {label: 'Image generation', status: 'unsupported', message: 'An image-generation integration is required.', options: []}
    }
  }}));
  await page.route('**/api/conversations**', route => route.fulfill({json: []}));
  await page.goto('/');
  await page.getByRole('button', {name: /Select model: currently/}).click();
  await page.getByLabel('Choose by task').selectOption('vision');
  for (const i of [1, 2, 3]) await expect(page.getByRole('menuitem').filter({hasText: `Vision ${i}`})).toBeVisible();
  await expect(page.getByRole('status')).toContainText('3 currently listed options');
  await page.getByLabel('Choose by task').selectOption('image_generation');
  await expect(page.getByRole('status')).toContainText('integration is required');
  await expect(page.locator('.model-item')).toHaveCount(0);
});
