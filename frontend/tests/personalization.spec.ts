import { test, expect, Page } from '@playwright/test';

async function appMocks(page: Page) {
  const model = { id: 'text-model', name: 'Text model', provider: 'ollama', chat_compatible: true };
  await page.route('**/api/models?*', route => route.fulfill({ json: {
    provider: 'ollama', models: [model.id], model_details: [model], default: model.id,
    providers: [{ id: 'ollama', name: 'Ollama', working: true, models: [model] }],
  } }));
}

async function openPersonalization(page: Page) {
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  await page.getByRole('tab', { name: 'Personalization', exact: true }).click();
}

test('personalization persists, edits memories, disables and clears with confirmation', async ({ page }) => {
  await appMocks(page);
  await page.route('**/api/conversations**', route => route.fulfill({ json: [] }));
  let profile: any = { memory_enabled: true, preferences: {}, custom_instructions: '', memories: [] };
  await page.route('**/api/personalization**', async route => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const body = request.method() === 'GET' || request.method() === 'DELETE' ? {} : request.postDataJSON();
    if (path.endsWith('/personalization')) {
      if (request.method() === 'PATCH') profile = { ...profile, ...body };
      if (request.method() === 'DELETE') profile = { memory_enabled: true, preferences: {}, custom_instructions: '', memories: [] };
    } else if (request.method() === 'POST') profile.memories.push({ id: 1, ...body });
    else if (request.method() === 'PATCH') profile.memories = [{ id: 1, ...body }];
    else if (request.method() === 'DELETE') profile.memories = [];
    await route.fulfill({ json: profile });
  });
  await page.goto('/');
  await openPersonalization(page);
  await page.getByLabel('Preferred name', { exact: true }).fill('Tishal');
  await page.getByLabel('Tone', { exact: true }).fill('Friendly');
  await page.getByLabel('Custom instructions', { exact: true }).fill('Explain with short examples.');
  await page.getByRole('button', { name: 'Save preferences', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('Preferences saved');
  await page.reload();
  await openPersonalization(page);
  await expect(page.getByLabel('Preferred name', { exact: true })).toHaveValue('Tishal');
  await expect(page.getByLabel('Custom instructions', { exact: true })).toHaveValue('Explain with short examples.');
  await page.getByLabel('Memory label', { exact: true }).fill('Project');
  await page.getByLabel('Memory fact', { exact: true }).fill('The project name is Cedar.');
  await page.getByRole('button', { name: 'Add memory', exact: true }).click();
  await expect(page.locator('.memory-list')).toContainText('Cedar');
  await page.getByRole('button', { name: 'Edit memory Project', exact: true }).click();
  await page.getByLabel('Memory fact', { exact: true }).fill('The project name is Maple.');
  await page.getByRole('button', { name: 'Save memory', exact: true }).click();
  await expect(page.locator('.memory-list')).toContainText('Maple');
  await page.getByLabel('Use and save personalization').uncheck();
  await page.getByRole('button', { name: 'Save preferences', exact: true }).click();
  await expect.poll(() => profile.memory_enabled).toBe(false);
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByLabel('Preferred name')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: 'test-results/personalization-mobile.png', fullPage: true });
  await page.getByRole('button', { name: 'Delete memory Project', exact: true }).click();
  await expect(page.getByText('No saved memories yet.')).toBeVisible();
  await page.getByRole('button', { name: 'Forget all personalization', exact: true }).click();
  expect(profile.preferences.name).toBe('Tishal');
  await page.getByRole('button', { name: 'Confirm forget personalization', exact: true }).click();
  await expect(page.getByLabel('Preferred name', { exact: true })).toHaveValue('');
});

test('failed preference save keeps the draft and reports an error', async ({ page }) => {
  await appMocks(page);
  await page.route('**/api/conversations**', route => route.fulfill({ json: [] }));
  await page.route('**/api/personalization', route => route.request().method() === 'PATCH'
    ? route.fulfill({ status: 503, json: { detail: 'Please retry saving.' } })
    : route.fulfill({ json: { memory_enabled: true, preferences: {}, custom_instructions: '', memories: [] } }));
  await page.goto('/');
  await openPersonalization(page);
  await page.getByLabel('Preferred name', { exact: true }).fill('Draft name');
  await page.getByRole('button', { name: 'Save preferences', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('Please retry saving.');
  await expect(page.getByLabel('Preferred name', { exact: true })).toHaveValue('Draft name');
});

test('Auto survives multiple responses, fallback events and reload', async ({ page }) => {
  await appMocks(page);
  const requests: any[] = [];
  const conversation: any = { id: 'auto-test', title: 'Auto test', messages: [] };
  await page.route('**/api/conversations**', route => {
    const url = new URL(route.request().url());
    return route.fulfill({ json: url.pathname.endsWith('/conversations') && route.request().method() === 'GET'
      ? [conversation] : conversation });
  });
  await page.route('**/api/chat', async route => {
    const body = route.request().postDataJSON();
    requests.push(body);
    const id = requests.length * 2;
    conversation.messages.push({ id: id - 1, role: 'user', content: body.content, status: 'complete' },
      { id, role: 'assistant', content: 'Test answer.', status: 'complete', model: 'ollama:text-model' });
    const events = [{ type: 'start', message_id: id, provider: 'ollama', model: 'primary', auto_reason: 'Task selection' },
      { type: 'shift', message_id: id, provider: 'ollama', model: 'text-model', auto_reason: 'Fallback selection' },
      { type: 'token', content: 'Test answer.' }, { type: 'done', status: 'complete' }];
    await route.fulfill({ contentType: 'text/event-stream', body: events.map(e => 'data: ' + JSON.stringify(e) + '\n\n').join('') });
  });
  await page.goto('/');
  for (const text of ['Write Python code', 'Make it faster']) {
    await page.getByRole('textbox', { name: 'Message Forma' }).fill(text);
    await page.getByRole('button', { name: 'Send message', exact: true }).click();
    await expect(page.locator('article.assistant')).toHaveCount(requests.length || 1);
    await expect(page.getByRole('button', { name: /Select model: currently Auto/ })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Send message', exact: true })).toBeVisible();
  }
  await page.reload();
  await expect(page.getByRole('button', { name: /Select model: currently Auto/ })).toBeVisible();
  await page.getByRole('textbox', { name: 'Message Forma' }).fill('New topic: tell me about birds');
  await page.getByRole('button', { name: 'Send message', exact: true }).click();
  await expect.poll(() => requests.length).toBe(3);
  expect(requests.every(r => r.provider === 'auto' && r.model === 'auto')).toBe(true);
  expect(await page.evaluate(() => localStorage.getItem('forma-model'))).toBe('auto');
});
