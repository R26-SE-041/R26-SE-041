import { expect, test, type Page } from '@playwright/test'
import { mockBackend } from './backendMock'

async function installRecognition(page:Page) {
  await page.addInitScript(()=>{
    const scope=window as any
    scope.voiceInstances=[]
    class Recognition {
      onstart:any; onend:any; onresult:any; onerror:any; aborted=false; results:any[]=[]
      start(){scope.voiceInstances.push(this);queueMicrotask(()=>this.onstart?.())}
      abort(){this.aborted=true}
      emit(text:string, final=true, duplicate=false){
        if(!duplicate)this.results.push({isFinal:final,0:{transcript:text}})
        this.onresult?.({resultIndex:this.results.length-1,results:this.results})
      }
    }
    scope.SpeechRecognition=Recognition
  })
}
async function say(page:Page,text:string, final=true, duplicate=false) {
  await page.evaluate(({text,final,duplicate})=>(window as any).voiceInstances.at(-1).emit(text,final,duplicate),{text,final,duplicate})
}
async function openAudio(page:Page, enable = true) {
  await page.goto('/study-assistant#saved-library-title')
  await page.getByRole('region',{name:'Saved revisions and flashcards'}).getByRole('button',{name:'Open',exact:true}).first().click()
  await expect(page.locator('audio').last()).toHaveAttribute('src',/^blob:/)
  if (!enable) return
  await page.getByRole('button',{name:'Enable hands-free',exact:true}).click()
  await expect(page.getByText(/^Listening/)).toBeVisible()
}

test('real playing audio responds to all playback intents without a task API call',async({page})=>{
  await installRecognition(page);const state=await mockBackend(page);await openAudio(page)
  const audio=page.locator('audio').last()
  await audio.evaluate((a:HTMLAudioElement)=>a.play())
  await say(page,'pause the audio')
  expect(await audio.evaluate((a:HTMLAudioElement)=>a.paused)).toBe(false)
  await say(page,'VoiceLearn pause audio',false)
  expect(await audio.evaluate((a:HTMLAudioElement)=>a.paused)).toBe(false)
  await say(page,'VoiceLearn pause audio')
  await expect.poll(()=>audio.evaluate((a:HTMLAudioElement)=>a.paused)).toBe(true)
  await say(page,'VoiceLearn resume the audio')
  await expect.poll(()=>audio.evaluate((a:HTMLAudioElement)=>a.paused)).toBe(false)
  for(const [command,time] of [['Play section two',10],['Play the next section',20],['Play the previous section',10],['Replay this section',10]] as const){
    await say(page,'VoiceLearn '+command)
    await expect.poll(()=>audio.evaluate((a:HTMLAudioElement)=>Math.floor(a.currentTime))).toBe(time)
  }
  await say(page,'VoiceLearn stop the audio')
  await expect.poll(()=>audio.evaluate((a:HTMLAudioElement)=>a.currentTime)).toBe(0)
  await say(page,'VoiceLearn skip forward ten seconds')
  await expect.poll(()=>audio.evaluate((a:HTMLAudioElement)=>Math.floor(a.currentTime))).toBe(10)
  await say(page,'VoiceLearn go back ten seconds')
  await expect.poll(()=>audio.evaluate((a:HTMLAudioElement)=>Math.floor(a.currentTime))).toBe(0)
  for(const rate of [0.75,1.25]){
    await say(page,'VoiceLearn set playback speed to '+rate)
    await expect.poll(()=>audio.evaluate((a:HTMLAudioElement)=>a.playbackRate)).toBe(rate)
  }
  await say(page,'VoiceLearn play the audio')
  await expect.poll(()=>audio.evaluate((a:HTMLAudioElement)=>a.paused)).toBe(false)
  expect(state.actions).toHaveLength(0);expect(state.transcriptions).toBe(0);expect(state.tts).toBe(0)
})

test('creation requires confirmation, ignores duplicate finals and invalidates changed context',async({page})=>{
  await installRecognition(page);const state=await mockBackend(page);await openAudio(page)
  await say(page,'VoiceLearn create a one-minute audio revision and save it')
  await expect(page.getByText(/within 20 seconds/)).toBeVisible()
  expect(state.actions).toHaveLength(0)
  await page.locator('#action-language').selectOption('tamil')
  await say(page,'VoiceLearn confirm')
  expect(state.actions).toHaveLength(0)
  await say(page,'VoiceLearn create a one-minute audio revision and save it')
  await say(page,'VoiceLearn confirm')
  await page.evaluate(()=>{const r=(window as any).voiceInstances.at(-1);if(r?.results.length)r.emit('',true,true)})
  await expect.poll(()=>state.actions.length).toBe(1)
  expect(state.actions[0]).toMatchObject({language:'tamil',command:'create a one-minute audio revision and save it'})
  await expect(page.getByRole('button',{name:'Run action',exact:true})).toBeEnabled()
  await say(page,'VoiceLearn delete this saved revision')
  expect(state.deletions).toHaveLength(0)
  await say(page,'VoiceLearn confirm')
  expect(state.deletions).toHaveLength(0)
  await say(page,'VoiceLearn confirm delete')
  await expect.poll(()=>state.deletions.length).toBe(1)
  expect(state.actions).toHaveLength(1)
})

test('listening cleans up on tab change, network failure and page hiding; unsupported browsers show fallback',async({page})=>{
  await installRecognition(page);const state=await mockBackend(page);await openAudio(page)
  await page.getByRole('tab',{name:'Documents',exact:true}).click()
  await expect.poll(()=>page.evaluate(()=>(window as any).voiceInstances.at(-1).aborted)).toBe(true)
  await page.getByRole('tab',{name:'Study tools',exact:true}).click()
  await expect(page.getByRole('button',{name:'Enable hands-free',exact:true})).toBeVisible()
  await page.getByRole('button',{name:'Enable hands-free',exact:true}).click()
  await page.evaluate(()=>(window as any).voiceInstances.at(-1).onerror({error:'network'}))
  await expect(page.getByText(/Speech recognition lost its connection/)).toBeVisible()
  await page.getByRole('button',{name:'Enable hands-free',exact:true}).click()
  await page.evaluate(()=>{Object.defineProperty(document,'visibilityState',{value:'hidden',configurable:true});document.dispatchEvent(new Event('visibilitychange'))})
  await expect(page.getByRole('button',{name:'Enable hands-free',exact:true})).toBeVisible()
  expect(state.actions).toHaveLength(0)
  await page.addInitScript(()=>{delete (window as any).SpeechRecognition;delete (window as any).webkitSpeechRecognition})
  await page.reload()
  await expect(page.getByText(/Live voice recognition is unavailable/)).toBeVisible()
  await expect(page.getByRole('button',{name:'Enable hands-free',exact:true})).toBeDisabled()
})

test('all seven creation presets and summary commands run through voice confirmation',async({page})=>{
  test.setTimeout(150_000)
  await installRecognition(page);const state=await mockBackend(page)
  const commands=[
    'Create an audio revision of this section only and save it',
    'Create a one-minute audio revision and save it',
    'Create a detailed audio revision and save it',
    'Create an audio revision in Tamil and save it',
    'Create an audio revision in Sinhala and save it',
    'Create an audio revision in English and save it',
    'Create flashcards from this document and save them',
    'Summarize this document','Save the summary','Summarize this document and save it',
    'Create a short audio revision of this document and save it',
  ]
  for(const [index,command] of commands.entries()){
    await openAudio(page)
    await say(page,'VoiceLearn '+command)
    expect(state.actions.length).toBe(index)
    await say(page,'VoiceLearn confirm')
    await expect.poll(()=>state.actions.length).toBe(index+1)
    await expect(page.getByRole('button',{name:'Run action',exact:true})).toBeEnabled()
    expect(state.actions[index].command).toBe(command.toLowerCase())
  }
})

test('permission errors, silence restart, cancellation and expired confirmations do not submit work',async({page})=>{
  await installRecognition(page);const state=await mockBackend(page);await openAudio(page)
  await page.evaluate(()=>(window as any).voiceInstances.at(-1).onerror({error:'not-allowed'}))
  await expect(page.getByText(/Microphone permission was denied/)).toBeVisible()
  await page.getByRole('button',{name:'Enable hands-free',exact:true}).click()
  await page.evaluate(()=>{const r=(window as any).voiceInstances.at(-1);r.onerror({error:'no-speech'});r.onend()})
  await expect.poll(()=>page.evaluate(()=>(window as any).voiceInstances.length)).toBe(3)
  await say(page,'VoiceLearn create flashcards from this document and save them')
  await say(page,'VoiceLearn cancel')
  await say(page,'VoiceLearn confirm')
  expect(state.actions).toHaveLength(0)
  await page.clock.install()
  await say(page,'VoiceLearn create flashcards from this document and save them')
  await page.clock.runFor(20_100)
  await expect(page.getByText(/Confirmation expired/)).toBeVisible()
  await say(page,'VoiceLearn confirm')
  expect(state.actions).toHaveLength(0)
  await page.getByText('How to use voice controls',{exact:true}).click()
  await expect(page.getByRole('checkbox',{name:/Allow short playback/})).toHaveCount(0)
  await say(page,'pause')
  await expect(page.getByText('Audio paused',{exact:true})).toHaveCount(0)
  await say(page,'VoiceLearn stop listening')
  await expect(page.getByRole('button',{name:'Enable hands-free',exact:true})).toBeVisible()
})

test('a running task suspends recognition and ignores late results until it finishes',async({page})=>{
  await installRecognition(page);const state=await mockBackend(page)
  let release=false
  await page.route('**/api/v1/actions/new-1',route=>release ? route.fallback() : route.fulfill({json:{action_id:'new-1',status:'processing',trace:[]}}))
  await openAudio(page)
  await page.evaluate(()=>{const r=(window as any).voiceInstances.at(-1);(window as any).lateResult=r.onresult})
  await say(page,'VoiceLearn create a detailed audio revision and save it')
  await say(page,'VoiceLearn confirm')
  await expect(page.getByText('Listening paused while your task runs.',{exact:true})).toBeVisible()
  await expect.poll(()=>page.evaluate(()=>(window as any).voiceInstances.at(-1).aborted)).toBe(true)
  await page.evaluate(()=>(window as any).lateResult({resultIndex:5,results:{length:6,5:{isFinal:true,0:{transcript:'VoiceLearn confirm'}}}}))
  expect(state.actions).toHaveLength(1)
  release=true
  await expect(page.getByText(/^Listening/).first()).toHaveText(/^Listening .*say/)
  expect(state.actions).toHaveLength(1)
})

test('S24-sized view keeps hands-free controls readable above the glass dock',async({page})=>{
  await page.setViewportSize({width:384,height:832})
  await installRecognition(page);await mockBackend(page);await openAudio(page)
  const panel=page.getByRole('complementary',{name:'Hands-free voice controls'})
  await panel.scrollIntoViewIfNeeded()
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true)
  await expect(panel.getByRole('button',{name:'Turn off hands-free',exact:true})).toBeInViewport()
  await page.screenshot({path:'.workspace-runtime/hands-free-mobile.png',fullPage:false})
})

test('Android recognition ending cannot restart the microphone or oscillate playback',async({page})=>{
  await page.addInitScript(()=>Object.defineProperty(navigator,'userAgent',{value:'Mozilla/5.0 (Linux; Android 15; SM-S928B) Chrome/140 Mobile Safari/537.36',configurable:true}))
  await installRecognition(page);const state=await mockBackend(page);await openAudio(page)
  const audio=page.locator('audio').last()
  await audio.evaluate((a:HTMLAudioElement)=>a.play())
  await say(page,'VoiceLearn pause audio')
  await expect.poll(()=>audio.evaluate((a:HTMLAudioElement)=>a.paused)).toBe(true)
  await expect(page.getByRole('button',{name:'Turn off hands-free',exact:true})).toBeVisible()
  await say(page,'VoiceLearn resume audio')
  await expect.poll(()=>audio.evaluate((a:HTMLAudioElement)=>a.paused)).toBe(false)
  await page.clock.install()
  await page.evaluate(()=>(window as any).voiceInstances.at(-1).onend())
  await expect(page.getByText(/Your Android browser ended voice listening/)).toBeVisible()
  await page.clock.runFor(15_000)
  expect(await page.evaluate(()=>(window as any).voiceInstances.length)).toBe(1)
  expect(await audio.evaluate((a:HTMLAudioElement)=>a.paused)).toBe(false)
  expect(state.actions).toHaveLength(0)
})

test('Android microphone focus interruption turns listening off and permits stable manual playback',async({page})=>{
  await page.addInitScript(()=>Object.defineProperty(navigator,'userAgent',{value:'Mozilla/5.0 (Linux; Android 15; SM-S928B) Chrome/140 Mobile Safari/537.36',configurable:true}))
  await installRecognition(page);const state=await mockBackend(page);await openAudio(page,false)
  const audio=page.locator('audio').last()
  await audio.evaluate((a:HTMLAudioElement)=>{
    (window as any).playEvents=0
    a.addEventListener('play',()=>{(window as any).playEvents++})
    return a.play()
  })
  await page.getByRole('button',{name:'Enable hands-free',exact:true}).click()
  await expect(page.getByText(/^Listening/)).toBeVisible()
  // Model the OS/browser pausing media to grant microphone audio focus.
  await audio.evaluate((a:HTMLAudioElement)=>a.pause())
  await expect(page.getByText(/Playback was interrupted outside a voice command/)).toBeVisible()
  await expect(page.getByRole('button',{name:'Enable hands-free',exact:true})).toBeVisible()
  await expect.poll(()=>page.evaluate(()=>(window as any).voiceInstances.at(-1).aborted)).toBe(true)
  await page.clock.install()
  await page.clock.runFor(15_000)
  expect(await page.evaluate(()=>(window as any).voiceInstances.length)).toBe(1)
  expect(await page.evaluate(()=>(window as any).playEvents)).toBe(1)
  await audio.evaluate((a:HTMLAudioElement)=>a.play())
  await page.clock.runFor(3_000)
  expect(await audio.evaluate((a:HTMLAudioElement)=>a.paused)).toBe(false)
  expect(await page.evaluate(()=>(window as any).voiceInstances.length)).toBe(1)
  expect(state.actions).toHaveLength(0)
})
