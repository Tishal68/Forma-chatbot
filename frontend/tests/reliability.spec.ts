import { test, expect, Page } from '@playwright/test';
async function setup(page:Page) {
 const model={id:'text-model',name:'Text model',provider:'ollama',chat_compatible:true};
 await page.route('**/api/models?*',r=>r.fulfill({json:{provider:'ollama',models:[model.id],model_details:[model],providers:[{id:'ollama',name:'Ollama',working:true,models:[model]}]}}));
 const conversation={id:'audit',title:'Audit chat',messages:[{id:1,role:'user',content:'Original question',status:'complete'},{id:2,role:'assistant',content:'Original answer',status:'complete',model:'ollama:text-model'}]};
 await page.route('**/api/conversations**',r=>r.fulfill({json:new URL(r.request().url()).pathname.endsWith('/conversations')?[conversation]:conversation}));
 await page.route('**/api/personalization**',r=>r.fulfill({json:{memory_enabled:true,preferences:{},custom_instructions:'',memories:[]}}));
 await page.goto('/');
 return conversation;
}
test('unsaved memory draft survives switching settings tabs',async({page})=>{
 await setup(page);await page.getByRole('button',{name:'Settings',exact:true}).click();await page.getByRole('button',{name:/^Chat & Memory/}).click();await page.getByLabel('Preferred name',{exact:true}).fill('Unsaved draft');await page.getByRole('button',{name:/^Appearance/}).click();await page.getByRole('button',{name:/^Chat & Memory/}).click();await expect(page.getByLabel('Preferred name',{exact:true})).toHaveValue('Unsaved draft');
});
test('regenerate preserves unsent composer draft',async({page})=>{
 await setup(page);await page.getByText('Audit chat',{exact:true}).click();await page.route('**/api/chat',r=>r.fulfill({contentType:'text/event-stream',body:'data: {"type":"done","status":"complete"}\n\n'}));await page.getByRole('textbox',{name:'Message Forma'}).fill('Unsent next question');await page.getByRole('button',{name:'Regenerate response',exact:true}).click();await expect(page.getByRole('button',{name:'Send message',exact:true})).toBeVisible();await expect(page.getByRole('textbox',{name:'Message Forma'})).toHaveValue('Unsent next question');
});
test('failed edit retains editing state and retries the original message', async ({page}) => {
  const conversation = await setup(page);
  const requests: any[] = [];
  await page.getByText('Audit chat', {exact:true}).click();
  await page.route('**/api/chat', route => {
    requests.push(route.request().postDataJSON());
    if (requests.length === 1) return route.fulfill({status:503,json:{detail:'Retry later'}});
    conversation.messages[0].content = requests[1].content;
    return route.fulfill({contentType:'text/event-stream',body:'data: {"type":"done","status":"complete"}\n\n'});
  });
  await page.locator('article.user').hover();
  await page.getByRole('button', {name:'Edit message',exact:true}).click();
  await page.getByRole('button', {name:'Confirm',exact:true}).click();
  await page.getByRole('textbox', {name:'Message Forma'}).fill('Edited question');
  await page.getByRole('button', {name:'Send message',exact:true}).click();
  await expect(page.getByText('Retry later',{exact:false})).toBeVisible();
  await expect(page.getByText('Editing an earlier message',{exact:false})).toBeVisible();
  await page.getByRole('button', {name:'Send message',exact:true}).click();
  await expect.poll(() => requests.length).toBe(2);
  expect(requests[1].edit_message_id).toBe(1);
  await expect(page.getByText('Editing an earlier message',{exact:false})).not.toBeVisible();
  await expect(page.locator('article.user')).toContainText('Edited question');
});
test('IME Enter does not send partial composition',async({page})=>{
 await setup(page);let sent=0;await page.route('**/api/chat',r=>{sent++;return r.fulfill({status:503,json:{detail:'Unexpected submission'}})});const box=page.getByRole('textbox',{name:'Message Forma'});await box.fill('தமிழ்');await box.dispatchEvent('keydown',{key:'Enter',code:'Enter',isComposing:true});expect(sent).toBe(0);await expect(box).toHaveValue('தமிழ்');
});
test('multi-file upload cannot leak attachments into a new chat',async({page})=>{
 await setup(page);await page.getByText('Audit chat',{exact:true}).click();
 let release:()=>void=()=>{};const gate=new Promise<void>(r=>release=r);let uploads=0;let finished=false;
 await page.route('**/api/conversations/audit/attachments',async r=>{uploads++;const n=uploads;if(n===1)await gate;await r.fulfill({json:{id:'attachment-'+n,conversation_id:'audit',filename:n===1?'first.txt':'second.txt',content_type:'text/plain',size_bytes:4,created_at:new Date().toISOString()}});finished=true;});
 await page.locator('input[type=file]').setInputFiles([{name:'first.txt',mimeType:'text/plain',buffer:Buffer.from('test')},{name:'second.txt',mimeType:'text/plain',buffer:Buffer.from('test')}]);await expect.poll(()=>uploads).toBe(1);await page.getByRole('button',{name:'Start new chat',exact:true}).click();release();await expect.poll(()=>finished).toBe(true);expect(uploads).toBe(1);await expect(page.getByText('second.txt',{exact:true})).not.toBeVisible();
});

test('long manual model name fits beside mobile branding', async ({page}) => {
  await page.setViewportSize({width:360,height:800});
  await setup(page);
  const model={id:'long',name:'A very long reasoning model display name',provider:'ollama',chat_compatible:true};
  await page.route('**/api/models?*',r=>r.fulfill({json:{provider:'ollama',models:[model.id],model_details:[model],providers:[{id:'ollama',name:'Ollama',working:true,models:[model]}]}}));
  await page.reload();
  await page.getByRole('button',{name:/Select model: currently/}).click();
  await page.getByLabel('Selected model',{exact:true}).selectOption(JSON.stringify(['ollama','long']));
  await page.getByRole('button',{name:'Close settings',exact:true}).click();
  const brand=await page.locator('.mobile-header-brand').boundingBox();
  const picker=await page.getByRole('button',{name:/Select model: currently/}).boundingBox();
  expect(brand!.x+brand!.width).toBeLessThanOrEqual(picker!.x);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(360);
});

test('touch users can access message edit without hover', async ({browser}) => {
  const context=await browser.newContext({hasTouch:true,viewport:{width:390,height:844}});
  const page=await context.newPage();
  await setup(page);
  await page.getByRole('button',{name:'Open sidebar',exact:true}).click();
  await page.getByText('Audit chat',{exact:true}).click();
  const edit=page.getByRole('button',{name:'Edit message',exact:true});
  await expect(page.locator('article.user .message-actions')).toHaveCSS('opacity','1');
  await edit.click();
  await expect(page.getByRole('button',{name:'Confirm',exact:true})).toBeVisible();
  await page.screenshot({path:'test-results/mobile-edit-confirmation.png'});
  await context.close();
});
