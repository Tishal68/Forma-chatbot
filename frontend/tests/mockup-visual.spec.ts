import { test, expect } from '@playwright/test';

test.use({ baseURL: process.env.FORMA_TEST_URL || 'http://127.0.0.1:8000' });

test('render desktop conversation matching mockup', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });

  const now = new Date();
  const yesterday = new Date(Date.now() - 24 * 60 * 60 * 1000);

  const chats = [
    { id: 'workday-plan', title: 'Plan a better workday', updated_at: now.toISOString() },
    { id: 'writing', title: 'Improve my writing', updated_at: now.toISOString() },
    { id: 'side-project', title: 'Ideas for a side project', updated_at: now.toISOString() },
    { id: 'complex-topic', title: 'Explain a complex topic', updated_at: now.toISOString() },
    { id: 'meal-prep', title: 'Healthy meal prep ideas', updated_at: now.toISOString() },
    { id: 'resume', title: 'Review my resume', updated_at: yesterday.toISOString() },
    { id: 'japan-trip', title: 'Plan a trip to Japan', updated_at: yesterday.toISOString() },
    { id: 'marketing', title: 'Marketing strategy ideas', updated_at: yesterday.toISOString() },
    { id: 'workout', title: 'Build a workout routine', updated_at: yesterday.toISOString() },
    { id: 'home-office', title: 'Home office setup tips', updated_at: yesterday.toISOString() },
  ];

  const assistantText = `Start with your most important work, then leave room to recharge.

1. **Protect your focus.** Block time early for your most important work. Turn off non-urgent notifications and set a clear goal for the session.

2. **Make space for breaks.** Plan short breaks throughout the day to move, stretch, or step away from your screen. Even 5–10 minutes can help you stay sharp.

3. **Finish with a clear plan.** Take a few minutes at the end of the day to review what you accomplished and set your top 3 priorities for tomorrow.`;

  const conversationData = {
    id: 'workday-plan',
    title: 'Plan a better workday',
    messages: [
      {
        id: 1,
        role: 'user',
        content: 'Help me plan a focused, balanced workday.',
        status: 'complete',
      },
      {
        id: 2,
        role: 'assistant',
        content: assistantText,
        status: 'complete',
        model: 'auto',
        auto_reason: 'selected for planning',
      },
    ],
  };

  await page.route('**/api/models?*', route =>
    route.fulfill({
      json: {
        provider: 'auto',
        models: ['llama3.2', 'deepseek-r1'],
        model_details: [
          { id: 'llama3.2', name: 'Llama 3.2', provider: 'ollama', chat_compatible: true },
          { id: 'deepseek-r1', name: 'DeepSeek R1', provider: 'ollama', chat_compatible: true },
        ],
        providers: [
          {
            id: 'ollama',
            name: 'Ollama',
            working: true,
            models: [{ id: 'llama3.2', name: 'Llama 3.2', provider: 'ollama' }],
          },
        ],
        feature_coverage: {},
      },
    })
  );

  await page.route('**/api/conversations**', route => {
    const url = new URL(route.request().url());
    if (url.pathname === '/api/conversations') {
      return route.fulfill({ json: chats });
    }
    if (url.pathname.endsWith('/workday-plan')) {
      return route.fulfill({ json: conversationData });
    }
    return route.fulfill({ json: chats });
  });

  await page.goto('/');
  await page.getByRole('button', { name: 'Plan a better workday' }).click();

  await expect(page.locator('.header-title')).toHaveText('Plan a better workday');
  await expect(page.getByText('Help me plan a focused, balanced workday.')).toBeVisible();
  await expect(page.getByText('Protect your focus.')).toBeVisible();
  await expect(page.getByText('Auto · selected for planning')).toBeVisible();

  // Click background to ensure no focus rings
  await page.locator('.conversation-scroll').click({ position: { x: 50, y: 50 } });

  await page.screenshot({ path: 'test-results/mockup-desktop-1440.png' });
});

test('render mobile new chat matching mockup', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });

  await page.route('**/api/models?*', route =>
    route.fulfill({
      json: {
        provider: 'auto',
        models: ['llama3.2'],
        model_details: [{ id: 'llama3.2', name: 'Llama 3.2', provider: 'ollama', chat_compatible: true }],
        providers: [
          {
            id: 'ollama',
            name: 'Ollama',
            working: true,
            models: [{ id: 'llama3.2', name: 'Llama 3.2', provider: 'ollama', chat_compatible: true }],
          },
        ],
        feature_coverage: {},
      },
    })
  );

  await page.route('**/api/conversations**', route => route.fulfill({ json: [] }));

  await page.goto('/');

  await expect(page.getByText('What can we work on?')).toBeVisible();
  await expect(page.getByRole('button', { name: /Write: Polish, draft, edit/ })).toBeVisible();
  await expect(page.getByRole('button', { name: /Learn: Explain anything/ })).toBeVisible();
  await expect(page.getByRole('button', { name: /^Code/ })).toBeVisible();
  await expect(page.getByRole('button', { name: /Create image/ })).toBeVisible();

  // Ensure textarea is blurred so no focus ring
  await page.locator('.welcome').click({ position: { x: 20, y: 20 } });

  await page.screenshot({ path: 'test-results/mockup-mobile-390.png' });
});
