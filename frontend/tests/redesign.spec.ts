import { test, expect, Page } from '@playwright/test';

async function mockApp(page: Page) {
  const model = {id: 'text-model', name: 'Text model', provider: 'ollama', chat_compatible: true};
  await page.route('**/api/models?*', route => route.fulfill({json: {
    provider: 'ollama', models: [model.id], model_details: [model],
    providers: [{id: 'ollama', name: 'Ollama', working: true, models: [model]}],
  }}));
  await page.route('**/api/conversations**', route => route.fulfill({json: []}));
  await page.route('**/api/personalization', route => route.fulfill({json: {
    memory_enabled: true, preferences: {}, custom_instructions: '', memories: [],
  }}));
}

for (const width of [360, 390, 768, 1024, 1366, 1920]) {
  test(`workspace and model menu fit at ${width}px`, async ({page}) => {
    await page.setViewportSize({width, height: 844});
    await mockApp(page);
    await page.goto('/');
    const composer = page.locator('textarea');
    await expect(composer).toBeVisible();
    const bounds = await composer.boundingBox();
    expect(bounds!.y + bounds!.height).toBeLessThanOrEqual(844);
    expect(bounds!.x).toBeGreaterThanOrEqual(0);
    expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(width);
    await page.screenshot({path: `test-results/welcome-${width}.png`});
    if (width <= 800) await page.getByRole('button', {name: 'Open sidebar', exact: true}).click();
    const selector = page.getByRole('button', {name: /Select model: currently/});
    await expect(selector).toHaveCount(1);
    await selector.click();
    const menu = page.getByRole('menu');
    await expect(menu).toBeVisible();
    const menuBounds = await menu.boundingBox();
    expect(menuBounds!.x).toBeGreaterThanOrEqual(0);
    expect(menuBounds!.x + menuBounds!.width).toBeLessThanOrEqual(width);
    expect(menuBounds!.y + menuBounds!.height).toBeLessThanOrEqual(844);
    await page.screenshot({path: `test-results/model-menu-${width}.png`});
    await page.keyboard.press('Escape');
    if (width <= 800) {
      const open = page.getByRole('button', {name: 'Open sidebar', exact: true});
      if (await open.isVisible()) await open.click();
    }
    await page.getByRole('button', {name: 'Settings', exact: true}).click();
    await expect(page.getByRole('dialog')).toBeVisible();
    await page.screenshot({path: `test-results/settings-general-${width}.png`});
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  });
}

test('settings model selection shares state and appearance persists', async ({page}) => {
  await mockApp(page);
  await page.goto('/');
  await page.getByRole('button', {name: 'Settings', exact: true}).click();
  await page.getByRole('button', {name: /^Advanced Models/}).click();
  await page.getByLabel('Selected model', {exact: true}).selectOption(JSON.stringify(['ollama', 'text-model']));
  await page.screenshot({path: 'test-results/settings-models.png'});
  await page.getByRole('button', {name: /^Chat & Memory/}).click();
  await expect(page.getByLabel('Preferred name', {exact: true})).toBeVisible();
  await page.screenshot({path: 'test-results/settings-memory.png'});
  await page.getByRole('button', {name: /^Appearance Theme/}).click();
  await page.getByRole('button', {name: 'Light', exact: true}).click();
  await page.getByLabel('Compact spacing', {exact: true}).check();
  await page.getByLabel('Interface animations', {exact: true}).uncheck();
  await page.screenshot({path: 'test-results/settings-appearance.png'});
  await page.getByRole('button', {name: 'Close settings', exact: true}).click();
  await expect(page.getByRole('button', {name: 'Select model: currently Text model'})).toBeVisible();
  await page.reload();
  await expect(page.getByRole('button', {name: 'Select model: currently Text model'})).toBeVisible();
  await page.getByRole('button', {name: 'Settings', exact: true}).click();
  await page.getByRole('button', {name: /^Appearance Theme/}).click();
  await expect(page.getByRole('button', {name: 'Light', exact: true})).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByLabel('Compact spacing', {exact: true})).toBeChecked();
  await expect(page.getByLabel('Interface animations', {exact: true})).not.toBeChecked();
});
