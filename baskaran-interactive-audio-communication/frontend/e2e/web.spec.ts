import { expect, test, type Page } from '@playwright/test'
import { mockBackend, silentWav } from './backendMock'

test('editorial workspace navigation and theme remain usable on desktop and mobile', async ({page}) => {
  await mockBackend(page)
  await page.goto('/study-assistant')
  const navigation=page.getByRole('navigation',{name:'Workspace navigation'})
  await expect(navigation).toBeVisible()
  await navigation.getByRole('link',{name:'History',exact:true}).click()
  await expect(page.locator('#study-history')).toBeInViewport()
  await navigation.getByRole('link',{name:'Documents',exact:true}).click()
  await expect(page.locator('#study-documents')).toBeInViewport()
  await expect(navigation.getByRole('link',{name:'Documents',exact:true})).toHaveAttribute('aria-current','location')
  await page.evaluate(()=>window.scrollTo(0,0))
  await page.screenshot({path:'.workspace-runtime/editorial-workspace.png'})
  await page.setViewportSize({width:390,height:844})
  await page.evaluate(()=>window.scrollTo(0,0))
  for (const name of ['Documents','Ask a question','Study actions','Saved library','History']) {
    await expect(navigation.getByRole('link',{name,exact:true})).toBeInViewport()
  }
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true)
  await page.screenshot({path:'.workspace-runtime/editorial-mobile.png'})
  await page.emulateMedia({reducedMotion:'reduce'})
  await page.getByRole('button',{name:/switch to dark/i}).click()
  await page.screenshot({path:'.workspace-runtime/editorial-dark.png'})
  await page.goto('/')
  await page.screenshot({path:'.workspace-runtime/editorial-home.png'})
})

test('large saved library stays compact with search, filters and five-item pages', async ({page}) => {
  const state = await mockBackend(page)
  const items = Array.from({length:29}, (_, i) => ({action_id:`saved-${i}`,document_id:'doc-1',filename:`Study notes ${String(i).padStart(2,'0')}.pdf`,
    language:i % 2 ? 'tamil' : 'english',intent:i % 3 ? 'audio_revision' : 'flashcards',revision_mode:'sectioned',audio_duration:60,created_at:new Date(Date.UTC(2026,9,14,0,i)).toISOString()}))
  await page.route('**/api/v1/actions/saved', route => route.fulfill({json:items}))
  await page.goto('/study-assistant')
  const library=page.getByRole('region',{name:'Saved revisions and flashcards'})
  await expect(library.locator('li')).toHaveCount(5)
  await expect(library.getByText('Page 1 of 6',{exact:true})).toBeVisible()
  await library.getByRole('button',{name:'Next',exact:true}).click()
  await expect(library.getByText('Page 2 of 6',{exact:true})).toBeVisible()
  await library.getByLabel('Search documents').fill('Study notes 07')
  await expect(library.locator('li')).toHaveCount(1)
  await expect(library.getByText('Page 1 of 1',{exact:true})).toBeVisible()
  await library.getByLabel('Saved item type').selectOption('flashcards')
  await expect(library.getByText('No saved items match your search or filters.')).toBeVisible()
  await library.getByRole('button',{name:'Clear filters',exact:true}).click()
  await library.getByLabel('Saved item language').selectOption('tamil')
  await expect(library.getByText('Showing 1–5 of 14',{exact:true})).toBeVisible()
  await library.getByLabel('Saved item language').selectOption('all')
  await library.screenshot({path:'.workspace-runtime/library-desktop.png'})
  await page.setViewportSize({width:390,height:844})
  await library.screenshot({path:'.workspace-runtime/library-mobile.png'})
  expect(await page.evaluate(()=>document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  expect(state.actions).toHaveLength(0)
})

test('archived revision retries failed audio without requiring its original document', async ({page}) => {
  const state = await mockBackend(page)
  await page.route('**/api/v1/documents/', route => route.fulfill({json:[]}))
  let attempts = 0
  await page.route('**/api/v1/actions/audio-1/audio', route => {
    attempts++
    return attempts === 1 ? route.fulfill({status:503,json:{detail:'Temporary download failure'}})
      : route.fulfill({contentType:'audio/wav',body:silentWav()})
  })
  await page.route('**/api/v1/actions/audio-1/sections/0/source', route => route.fulfill({json:{filename:'Archived.pdf',excerpt:'Archived source passage.',verification:'saved_snapshot'}}))
  await page.goto('/study-assistant')
  await page.locator('li').filter({hasText:'sectioned audio revision'}).first().getByRole('button',{name:'Open',exact:true}).click()
  await expect(page.getByRole('heading',{name:'Audio revision transcript',exact:true})).toBeVisible()
  await expect(page.getByRole('button',{name:'Play from here',exact:true}).first()).toBeDisabled()
  await page.getByRole('button',{name:'Retry loading audio',exact:true}).click()
  await expect(page.locator('audio').last()).toBeVisible()
  await expect(page.getByRole('button',{name:'Play from here',exact:true}).first()).toBeEnabled()
  await page.locator('#action-command').fill('Pause the audio')
  await expect(page.getByRole('button',{name:'Run action',exact:true})).toBeEnabled()
  await page.getByRole('button',{name:'Run action',exact:true}).click()
  await page.getByRole('button',{name:'View source',exact:true}).first().click()
  await expect(page.getByText('Archived source passage.',{exact:true})).toBeVisible()
  await expect(page.getByText(/Saved source passage from when this revision was created/)).toBeVisible()
  expect(state.actions).toHaveLength(0)
})

async function start(page: Page) {
  const state = await mockBackend(page)
  await page.goto('/study-assistant')
  await expect(page.getByRole('heading', {name:'Learn with your voice'})).toBeVisible()
  await expect(page.locator('#action-document')).toBeVisible()
  return state
}
async function run(page: Page, command: string) {
  await page.locator('#action-command').fill(command)
  await page.getByRole('button',{name:'Run action',exact:true}).click()
}
async function openAudio(page: Page) {
  const row = page.locator('li').filter({hasText:'sectioned audio revision'}).first()
  await row.getByRole('button',{name:'Open',exact:true}).click()
  await expect(page.getByRole('heading',{name:'Audio revision transcript',exact:true})).toBeVisible()
  await expect.poll(() => page.locator('audio').last().evaluate(el => Number.isFinite((el as HTMLAudioElement).duration))).toBe(true)
}

test('Expo root, all original URLs, legacy redirect and browser navigation', async ({page}) => {
  // This test performs eleven full navigations against the Expo dev server.
  test.setTimeout(90_000)
  await mockBackend(page)
  const errors: string[]=[];page.on('pageerror', e=>errors.push(e.message))
  for (const route of ['/', '/documents', '/login', '/register', '/study-assistant', '/dashboard/documents', '/dashboard/history', '/dashboard']) {
    await page.goto(route)
    await expect(page.getByTestId('expo-web-root')).toBeAttached()
  }
  await page.goto('/test');await expect(page).toHaveURL(/\/study-assistant$/)
  await page.goto('/login');await page.getByRole('link',{name:'Register',exact:true}).click()
  await expect(page).toHaveURL(/\/register$/);await page.goBack();await expect(page).toHaveURL(/\/login$/)
  expect(errors).toEqual([])
})

test('theme survives refresh and document response languages remain selectable', async ({page}) => {
  await start(page)
  await page.getByRole('button',{name:/Switch to .* mode/}).click()
  const theme = await page.locator('html').getAttribute('data-theme')
  await page.reload();await expect(page.locator('html')).toHaveAttribute('data-theme',theme!)
  await page.getByRole('button',{name:'Tamil',exact:true}).click()
  await expect(page.getByRole('button',{name:'Tamil',exact:true})).toHaveAttribute('aria-pressed','true')
  await page.getByRole('button',{name:'Sinhala',exact:true}).click()
  await expect(page.getByRole('button',{name:'Sinhala',exact:true})).toHaveAttribute('aria-pressed','true')
  await page.getByRole('button',{name:'English',exact:true}).click()
  await expect(page.locator('#action-command')).toBeVisible()
  await page.locator('#action-command').scrollIntoViewIfNeeded()
  await expect.poll(()=>page.evaluate(()=>window.scrollY)).toBeGreaterThan(0)
})

test('document upload and removal preserve indexed documents workflow', async ({page}) => {
  const state = await start(page)
  await page.locator('input[type=file][accept=".pdf,.pptx,.docx,.xlsx,.txt,.md"]').setInputFiles({name:'new-notes.txt',mimeType:'text/plain',buffer:Buffer.from('Study notes.')})
  const row = page.locator('li').filter({hasText:'new-notes.txt'})
  await expect(row).toBeVisible();expect(state.uploads).toBe(1)
  await row.getByRole('button',{name:'Remove new-notes.txt',exact:true}).click()
  await expect(row).toHaveCount(0)
})

test('audio upload, transcription, question correction, answer audio and IndexedDB history', async ({page}) => {
  const state = await start(page)
  await page.locator('input[type=file][accept*="audio/wav"]').first().setInputFiles({name:'question.wav',mimeType:'audio/wav',buffer:silentWav(1)})
  await page.locator('#voice-submit-btn').click()
  await expect(page.getByRole('textbox',{name:'Your Question',exact:true})).toHaveValue('Explain dogs.')
  await page.getByRole('button',{name:'Fix Transcript',exact:true}).click()
  await expect(page.getByRole('textbox',{name:'Your Question',exact:true})).toHaveValue('Explain dogs clearly.')
  await page.getByRole('button',{name:'Ask →',exact:true}).click()
  await expect(page.getByText('Dogs are domesticated mammals.',{exact:true}).first()).toBeVisible()
  expect(state.asks[0].document_grounded).toBe(true)
  await expect.poll(()=>state.tts).toBe(1)
  await page.reload()
  const history = page.getByRole('button',{name:/Explain dogs clearly/})
  await expect(history).toBeVisible()
  await history.click()
  await page.getByRole('button',{name:'Delete this entry',exact:true}).click()
  await expect(history).toHaveCount(0)
  expect(state.transcriptions).toBe(1)
})

test('document-only interface keeps actions visible and removes mode switching', async ({page}) => {
  await start(page)
  await expect(page.getByRole('heading',{name:'Document Study',exact:true})).toBeVisible()
  await expect(page.getByRole('heading',{name:'Document actions and audio revision'})).toBeVisible()
  await expect(page.getByRole('button',{name:'Document Study',exact:true})).toHaveCount(0)
  await expect(page.getByRole('button',{name:/specialized|tutor/i})).toHaveCount(0)
})

test('Sinhala answer editing and explicit speech approval are retained', async ({page}) => {
  const state = await start(page)
  await page.getByRole('button',{name:'Sinhala',exact:true}).click()
  await page.locator('input[type=file][accept*="audio/wav"]').first().setInputFiles({name:'question.wav',mimeType:'audio/wav',buffer:silentWav(1)})
  await page.locator('#voice-submit-btn').click()
  await expect(page.locator('textarea[aria-label]').first()).toHaveValue('Explain dogs.')
  await page.getByRole('button',{name:'අසන්න →',exact:true}).click()
  await page.getByRole('button',{name:'Edit Answer',exact:true}).click()
  expect(state.tts).toBe(0)
  await page.getByRole('textbox',{name:'Edit Sinhala answer',exact:true}).fill('බල්ලන් ගෘහස්ථ සතුන් වේ.')
  await page.getByRole('button',{name:'Save Changes',exact:true}).click()
  await page.getByRole('button',{name:'Accept & Generate Speech',exact:true}).click()
  await expect.poll(()=>state.tts).toBe(1)
  expect(state.asks[0].language).toBe('sinhala')
})

for (const command of ['Summarize this document','Save the summary','Summarize this document and save it']) {
  test(`existing summary UI: ${command}`, async ({page}) => {
    const state = await start(page)
    await page.locator('#action-document').selectOption('doc-1')
    await run(page,command)
    await expect(page.getByText('A concise document summary.',{exact:true})).toBeVisible()
    expect(state.actions[0].command).toBe(command)
    const download = page.waitForEvent('download')
    await page.getByRole('button',{name:'Download summary (.txt)',exact:true}).click()
    expect((await download).suggestedFilename()).toBe('lecture-summary-english.txt')
  })
}

test('microphone records a synthetic browser stream and submits its transcript', async ({page,context}) => {
  await context.grantPermissions(['microphone'])
  const state = await start(page)
  await page.getByRole('button',{name:'Start recording',exact:true}).first().click()
  await expect(page.getByRole('button',{name:'Stop recording',exact:true})).toBeVisible()
  // Wait for the browser MediaRecorder to produce a nonempty audio chunk.
  await page.waitForTimeout(600)
  await page.getByRole('button',{name:'Stop recording',exact:true}).click()
  await expect(page.locator('#voice-submit-btn')).toBeVisible()
  await page.locator('#voice-submit-btn').click()
  await expect(page.getByRole('textbox',{name:'Your Question',exact:true})).toHaveValue('Explain dogs.')
  expect(state.transcriptions).toBe(1)
})

const generations = [
  'Create a short audio revision of this document and save it',
  'Create a one-minute audio revision and save it',
  'Create a detailed audio revision and save it',
  'Create an audio revision in Tamil and save it',
  'Create an audio revision in Sinhala and save it',
  'Create an audio revision in English and save it',
  'Create flashcards from this document and save them',
]
for (const command of generations) test(`generation UI: ${command}`, async ({page}) => {
  const state = await start(page)
  await page.locator('#action-document').selectOption('doc-1')
  await page.locator('#action-provider').selectOption('direct')
  await run(page, command)
  await expect(page.getByRole('heading',{name:command.includes('flashcards') ? 'Saved revision flashcards' : 'Audio revision transcript',exact:true})).toBeVisible()
  expect(state.actions).toHaveLength(1)
  expect(state.actions[0]).toMatchObject({command,document_id:'doc-1',provider:'direct'})
  if (command.includes('flashcards')) {
    await page.getByRole('button',{name:'Reveal answer',exact:true}).click()
    await expect(page.getByText('A domesticated mammal.',{exact:true})).toBeVisible()
    const download = page.waitForEvent('download')
    await page.getByRole('button',{name:'Download flashcards (.json)',exact:true}).click()
    expect((await download).suggestedFilename()).toBe('lecture-flashcards-english.json')
  } else {
    const download = page.waitForEvent('download')
    await page.getByRole('button',{name:'Download revision audio (.wav)',exact:true}).click()
    expect((await download).suggestedFilename()).toMatch(/^lecture-revision-(english|tamil|sinhala)\.wav$/)
  }
})

test('source inspection, selected-section-only request and transcript download', async ({page}) => {
  const state = await start(page);await openAudio(page)
  await page.getByRole('button',{name:'View source',exact:true}).first().click()
  await expect(page.getByText('Original source passage about dogs.',{exact:true})).toBeVisible()
  await page.locator('#source-section').selectOption('1')
  await run(page,'Create an audio revision of this section only and save it')
  await expect.poll(()=>state.actions.length).toBe(1)
  expect(state.actions[0]).toMatchObject({source_action_id:'audio-1',section_id:1})
  const download = page.waitForEvent('download')
  await page.getByRole('button',{name:'Download transcript (.txt)',exact:true}).click()
  expect((await download).suggestedFilename()).toBe('lecture-revision-english.txt')
})

test('all twelve playback commands control existing audio without generation requests', async ({page}) => {
  const state = await start(page);await openAudio(page)
  const player = page.locator('audio').last()
  for (const command of ['Play the audio','Pause the audio','Resume the audio','Stop the audio','Play the next section','Play the previous section','Replay this section','Play section two','Skip forward ten seconds','Go back ten seconds','Set playback speed to 0.75','Set playback speed to 1.25']) {
    await run(page,command)
    await expect(page.getByRole('button',{name:'Run action',exact:true})).toBeEnabled()
    await expect(page.getByRole('alert')).toHaveCount(0)
  }
  await expect.poll(()=>player.evaluate(el=>(el as HTMLAudioElement).playbackRate)).toBe(1.25)
  expect(state.actions).toHaveLength(0)
})

test('saved library refresh/reopen and confirmed deletion leave document available', async ({page}) => {
  const state = await start(page);await openAudio(page)
  await page.reload();await openAudio(page)
  await run(page,'Delete this saved revision')
  await expect(page.getByRole('dialog')).toBeVisible()
  await page.getByRole('button',{name:'Cancel',exact:true}).click();expect(state.deletions).toHaveLength(0)
  await run(page,'Delete this saved revision')
  await page.getByRole('button',{name:'Confirm delete',exact:true}).click()
  await expect(page.getByRole('dialog')).toHaveCount(0)
  expect(state.deletions).toEqual([{confirmed:true}])
  await expect(page.locator('#action-document')).toContainText('Lecture.pdf')
  expect(state.actions).toHaveLength(0)
})
