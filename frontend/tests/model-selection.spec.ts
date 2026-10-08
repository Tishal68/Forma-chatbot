import { test, expect } from '@playwright/test';

test.use({ baseURL: process.env.FORMA_TEST_URL || 'http://127.0.0.1:8000' });

test('new conversation defaults to Forma Auto and hides raw model management from normal workspace', async ({ page }) => {
  const model = {id: 'text-model', name: 'Text model', provider: 'ollama', chat_compatible: true, supports_vision: false};
  await page.route('**/api/models?*', async route => {
    await route.fulfill({json: {provider: 'ollama', models: ['text-model'], model_details: [model],
      default: 'text-model', providers: [{id: 'ollama', name: 'Ollama', working: true, models: [model]}]}});
  });
  await page.route('**/api/conversations**', async route => {
    await route.fulfill({json: route.request().method() === 'POST' ? {id: 'test-chat', title: 'New chat'} : []});
  });
  await page.goto('/');

  // 1. New conversation defaults to Forma Auto
  const autoIndicator = page.getByRole('button', { name: /Select model: currently Auto/ });
  await expect(autoIndicator).toBeVisible();
  await expect(page.locator('.forma-auto-pill-text')).toHaveText('Forma Auto');

  // 2. Normal workspace does NOT prominently expose raw provider names, raw model IDs, or large selector controls
  await expect(page.locator('.topbar').getByText('Ollama', { exact: true })).toHaveCount(0);
  await expect(page.locator('.topbar').getByText('text-model', { exact: true })).toHaveCount(0);
  await expect(page.locator('.topbar select')).toHaveCount(0);
  await expect(page.locator('.filter-chip')).toHaveCount(0);
});

test('manual model selection in Advanced Settings changes active model, survives reload, and returns to Auto', async ({ page }) => {
  const model = {id: 'text-model', name: 'Text model', provider: 'ollama', chat_compatible: true, supports_vision: false};
  await page.route('**/api/models?*', async route => {
    await route.fulfill({json: {provider: 'ollama', models: ['text-model'], model_details: [model],
      default: 'text-model', providers: [{id: 'ollama', name: 'Ollama', working: true, models: [model]}]}});
  });
  await page.route('**/api/conversations**', async route => {
    await route.fulfill({json: route.request().method() === 'POST' ? {id: 'test-chat', title: 'New chat'} : []});
  });
  await page.goto('/');

  // 3. Advanced Settings exposes manual model selection
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  await page.getByRole('button', { name: /^Advanced Models/ }).click();
  const modelSelect = page.getByLabel('Selected model', { exact: true });
  await expect(modelSelect).toBeVisible();

  // 4. Selecting a manual model in Advanced Settings changes the active model
  await modelSelect.selectOption(JSON.stringify(['ollama', 'text-model']));
  await page.getByRole('button', { name: 'Close settings', exact: true }).click();
  const manualPill = page.getByRole('button', { name: 'Select model: currently Text model' });
  await expect(manualPill).toBeVisible();
  await expect(page.locator('.forma-auto-pill-text')).toHaveText('Text model');

  // 5. Reload preserves manual selection
  await page.reload();
  await expect(page.getByRole('button', { name: 'Select model: currently Text model' })).toBeVisible();
  expect(await page.evaluate(() => localStorage.getItem('forma-model'))).toBe('text-model');

  // 6. Returning to Auto restores Forma Auto
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  await page.getByRole('button', { name: /^Advanced Models/ }).click();
  await page.getByLabel('Selected model', { exact: true }).selectOption('auto');
  await page.getByRole('button', { name: 'Close settings', exact: true }).click();
  await expect(page.getByRole('button', { name: /Select model: currently Auto/ })).toBeVisible();
  await expect(page.locator('.forma-auto-pill-text')).toHaveText('Forma Auto');
  expect(await page.evaluate(() => localStorage.getItem('forma-model'))).toBe('auto');
});

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

test('assistant message hides raw model in normal view and reveals it via disclosure', async ({ page }) => {
  const model = {id: 'text-model', name: 'Text model', provider: 'ollama', chat_compatible: true, supports_vision: false};
  await page.route('**/api/models?*', async route => {
    await route.fulfill({json: {provider: 'ollama', models: ['text-model'], model_details: [model],
      default: 'text-model', providers: [{id: 'ollama', name: 'Ollama', working: true, models: [model]}]}});
  });
  const conversation: any = {
    id: 'test-chat',
    title: 'New chat',
    messages: [
      { id: 1, role: 'user', content: 'Hello Forma', status: 'complete' },
      { id: 2, role: 'assistant', content: 'Forma response text.', status: 'complete', model: 'ollama:text-model', auto_reason: 'Selected for general conversation.' }
    ]
  };
  await page.route('**/api/conversations**', async route => {
    const url = new URL(route.request().url());
    if (route.request().method() === 'POST') {
      return route.fulfill({ json: { id: 'test-chat', title: 'New chat' } });
    }
    if (url.pathname.includes('/test-chat')) {
      return route.fulfill({ json: conversation });
    }
    return route.fulfill({ json: [] });
  });
  await page.route('**/api/chat', async route => {
    const events = [
      { type: 'start', message_id: 2, provider: 'ollama', model: 'text-model', auto_reason: 'Selected for general conversation.' },
      { type: 'token', content: 'Forma response text.' },
      { type: 'done', status: 'complete' }
    ];
    await route.fulfill({ contentType: 'text/event-stream', body: events.map(e => 'data: ' + JSON.stringify(e) + '\n\n').join('') });
  });

  await page.goto('/');
  await page.getByRole('textbox', { name: 'Message Forma' }).fill('Hello Forma');
  await page.getByRole('button', { name: 'Send message', exact: true }).click();

  // 7. Normal view shows Forma Auto label, not raw model ID
  await expect(page.getByText('Auto · Selected for general conversation')).toBeVisible();
  await expect(page.locator('.message-model-name')).not.toBeVisible();

  // 8. Expanding "Why this model?" reveals raw model details and routing rationale
  await page.getByText('Why this model?', { exact: true }).click();
  await expect(page.locator('.message-model-name')).toBeVisible();
  await expect(page.locator('.message-model-name')).toContainText('text-model');
  await expect(page.getByText('Selected for general conversation.')).toBeVisible();
});

test('removed provider selection returns to Auto', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('forma-provider', 'openrouter');
    localStorage.setItem('forma-model', 'openai/gpt-4o-mini');
  });
  await page.route('**/api/models?*', route => {
    expect(new URL(route.request().url()).searchParams.has('provider')).toBe(false);
    return route.fulfill({ json: { providers: [], models: [], model_details: [] } });
  });
  await page.route('**/api/conversations**', route => route.fulfill({ json: [] }));
  await page.goto('/');
  await expect(page.getByRole('button', { name: /Select model: currently Auto/ })).toBeVisible();
  expect(await page.evaluate(() => localStorage.getItem('forma-provider'))).toBe('auto');
  expect(await page.evaluate(() => localStorage.getItem('forma-model'))).toBe('auto');
});
