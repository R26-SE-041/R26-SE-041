import { expect, test } from '@playwright/test'
import { mockBackend, silentWav } from './backendMock'

test('natural commands show an explicit language preview and do not run until clicked',async({page})=>{
 const state=await mockBackend(page)
 await page.setViewportSize({width:384,height:832})
 await page.goto('/study-assistant#study-actions')
 await page.locator('#action-document').selectOption('doc-1')
 for(const text of ['Make Tamil audio','create a audio review in tamil']){
  await page.locator('#action-command').fill(text)
  await expect(page.getByRole('region',{name:'Command preview'})).toContainText('Create and save an audio revision in Tamil')
  expect(state.actions).toHaveLength(0)
 }
 await page.getByRole('button',{name:'Run action',exact:true}).click()
 await expect.poll(()=>state.actions.length).toBe(1)
 await expect(page.getByRole('heading',{name:'Audio revision transcript',exact:true})).toBeVisible()
 await page.locator('#action-command').fill('Make audio in Tamil and English')
 await expect(page.getByRole('region',{name:'Command preview'})).toContainText('Choose one output language')
 await expect(page.getByRole('button',{name:'Run action',exact:true})).toBeDisabled()
 expect(state.actions).toHaveLength(1)
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true)
 await page.getByRole('region',{name:'Command preview'}).scrollIntoViewIfNeeded()
 await page.screenshot({path:'.workspace-runtime/natural-command-mobile.png'})
})

test('study command audio transcribes automatically, while failed audio remains retryable',async({page})=>{
 const state=await mockBackend(page);let transcriptions=0
 await page.route('**/api/v1/voice/transcribe',route=>{
  transcriptions++
  return transcriptions===1?route.fulfill({status:503,json:{detail:'Transcription is temporarily unavailable.'}}):route.fulfill({json:{transcript:'Make Tamil audio',selected_language:'english',detected_language:'en',duration_ms:1000}})
 })
 await page.goto('/study-assistant#study-actions')
 await page.locator('#action-document').selectOption('doc-1')
 await page.getByRole('tabpanel').locator('input[type=file][accept*="audio/wav"]').setInputFiles({name:'command.wav',mimeType:'audio/wav',buffer:silentWav(1)})
 await expect(page.getByRole('alert')).toContainText('Transcription is temporarily unavailable.')
 await expect(page.getByRole('button',{name:'Transcribe command',exact:true})).toBeVisible()
 expect(transcriptions).toBe(1)
 await page.getByRole('button',{name:'Transcribe command',exact:true}).click()
 await expect(page.locator('#action-command')).toHaveValue('Make Tamil audio')
 await expect(page.getByRole('region',{name:'Command preview'})).toContainText('Create and save an audio revision in Tamil')
 expect(transcriptions).toBe(2);expect(state.actions).toHaveLength(0)
 await page.getByRole('button',{name:'Run action',exact:true}).click()
 await expect.poll(()=>state.actions.length).toBe(1)
})

test('a stale preview cannot enable or overwrite a newly edited command',async({page})=>{
 await mockBackend(page);let first=false
 await page.route('**/api/v1/actions/interpret',async route=>{
  if(route.request().postDataJSON().command!=='Make Tamil audio')return route.fallback()
  first=true
  await new Promise(resolve=>setTimeout(resolve,1300))
  await route.fulfill({json:{status:'ready',intent:'audio_revision',language:'tamil',scope:'document',message:'OLD Tamil preview'}})
 })
 await page.goto('/study-assistant#study-actions')
 await page.locator('#action-document').selectOption('doc-1')
 await page.locator('#action-command').fill('Make Tamil audio')
 await expect.poll(()=>first).toBe(true)
 await page.locator('#action-command').fill('Make Sinhala audio')
 await expect(page.getByRole('button',{name:'Run action',exact:true})).toBeDisabled()
 await expect(page.getByRole('region',{name:'Command preview'})).toContainText('Sinhala')
 await page.waitForTimeout(1400)
 await expect(page.getByRole('region',{name:'Command preview'})).not.toContainText('OLD Tamil')
 await expect(page.getByRole('button',{name:'Run action',exact:true})).toBeEnabled()
})

test('section generation failure offers an explicit single-audio recovery without auto-running it',async({page})=>{
 const state=await mockBackend(page)
 await page.route('**/api/v1/actions/new-1',route=>route.fulfill({json:{action_id:'new-1',status:'failed',intent:'audio_revision',revision_mode:'sectioned',language:'tamil',summary_language:'english',summary:null,sections:[],saved:false,audio_ready:false,audio_saved:false,error:'Section generation returned invalid structured content after one retry. Retry or use Single audio.',trace:[],confirmation:''}}))
 await page.goto('/study-assistant#study-actions')
 await page.locator('#action-document').selectOption('doc-1')
 await page.locator('#action-command').fill('Make Tamil audio')
 await page.getByRole('button',{name:'Run action',exact:true}).click()
 await expect(page.getByRole('alert')).toContainText('invalid structured content')
 await expect(page.getByRole('heading',{name:'Opened study result',exact:true})).toHaveCount(0)
 await expect(page.getByText('Nothing has started yet.',{exact:false})).toHaveCount(0)
 await page.getByRole('button',{name:'Use single audio instead',exact:true}).click()
 await expect(page.locator('#revision-mode')).toHaveValue('single')
 expect(state.actions).toHaveLength(1)
 await page.getByRole('button',{name:'Run action',exact:true}).click()
 await expect.poll(()=>state.actions.length).toBe(2)
 expect(state.actions[1].revision_mode).toBe('single')
})
