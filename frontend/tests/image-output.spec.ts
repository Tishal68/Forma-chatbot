import {test, expect} from '@playwright/test';
test.use({baseURL: process.env.FORMA_TEST_URL || 'http://127.0.0.1:8000'});
const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aZ1kAAAAASUVORK5CYII=', 'base64');

for (const width of [1440, 768, 390]) {
  test(`image creation and responsive layout at ${width}px`, async ({page}) => {
    await page.setViewportSize({width, height: 900});
    const models = [{id:'x/z-image-turbo:latest', name:'Z-Image Turbo', provider:'ollama', supports_image_generation:true, chat_compatible:false,
      description:'Creates images on a supported experimental Ollama server.'}];
    const attachment = {id:'image-1', conversation_id:'image-chat', filename:'forma-image.png', size_bytes:png.length, content_type:'image/png', generated:true, is_image:true};
    let generated = false;
    await page.route('**/api/models?*', route => route.fulfill({json:{provider:'ollama', models:models.map(m=>m.id), model_details:models,
      providers:[{id:'ollama',name:'Ollama', working:true, models}], feature_coverage:{image_generation:{label:'Image generation', status:'limited', message:'One image generator connected.', options:[{provider:'ollama', model:models[0].id}]}}}}));
    await page.route('**/api/conversations**', route => {
      const path = new URL(route.request().url()).pathname;
      if(path.includes('/attachments/')) return route.fulfill({contentType:'image/png',body:png});
      if(route.request().method()==='POST') return route.fulfill({json:{id:'image-chat',title:'Image creation'}});
      if(path==='/api/conversations') return route.fulfill({json:generated ? [{id:'image-chat',title:'Image creation',updated_at:new Date().toISOString()}] : []});
      return route.fulfill({json:{id:'image-chat',title:'Image creation',messages:generated ? [
        {id:1,role:'user',content:'Create a green landscape',status:'complete',output_mode:'image'},
        {id:2,role:'assistant',content:'Here is your image.',status:'complete',output_mode:'image',model:'ollama:x/z-image-turbo:latest',attachments:[attachment],auto_reason:'Selected for image generation.'}
      ] : []}});
    });
    await page.route('**/api/chat', async route=>{
      const payload = route.request().postDataJSON();
      expect(payload.output_mode).toBe('image');
      expect(payload.web_search).toBe(false);
      generated = true;
      await route.fulfill({contentType:'text/event-stream',body:[
        {type:'start',message_id:2,provider:'ollama',model:models[0].id},
        {type:'status',message:'Creating image · 50%'},
        {type:'image',attachment}, {type:'done',status:'complete'}
      ].map(event=>`data: ${JSON.stringify(event)}\n\n`).join('')});
    });
    await page.goto('/');
    const toolsBtn = page.getByRole('button', {name: 'Tools'});
    if (await toolsBtn.isVisible()) {
      await toolsBtn.click();
    }
    await page.getByRole('button',{name:'Create image mode'}).click();
    await page.getByRole('textbox',{name:'Message Forma'}).fill('Create a green landscape');
    await page.getByRole('button',{name:'Send message',exact:true}).click();
    const picture = page.getByRole('img',{name:'AI-generated image'});
    await expect(picture).toBeVisible();
    await expect(page.getByRole('link',{name:'Download image'})).toHaveAttribute('href',/\/download$/);
    await page.reload();
    await expect(picture).toBeVisible();
    await expect(page.getByRole('button', {name:'Create image mode'})).toHaveAttribute('aria-pressed','true');
    await expect.poll(() => picture.evaluate((img: HTMLImageElement) => img.naturalWidth)).toBeGreaterThan(0);
    await expect(page.locator('.message-model-name')).toContainText('x/z-image-turbo:latest');
    await page.getByText('Why this model?', {exact:true}).click();
    await expect(page.getByText('Selected for image generation.', {exact:true})).toBeVisible();
    expect(await page.evaluate(()=>document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.getByRole('button',{name:/Select model: currently/}).click();
    await expect(page.getByLabel('Choose by task')).toBeVisible();
    expect(await page.evaluate(()=>document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.keyboard.press('Escape');
    await page.screenshot({path:`test-results/image-ui-${width}.png`});
  });
}
