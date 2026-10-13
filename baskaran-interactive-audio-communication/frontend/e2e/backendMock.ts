import type { Page } from '@playwright/test'

export function silentWav(seconds = 30) {
  const sampleRate = 8000
  const dataBytes = seconds * sampleRate * 2
  const buffer = Buffer.alloc(44 + dataBytes)
  buffer.write('RIFF', 0); buffer.writeUInt32LE(36 + dataBytes, 4); buffer.write('WAVEfmt ', 8)
  buffer.writeUInt32LE(16, 16); buffer.writeUInt16LE(1, 20); buffer.writeUInt16LE(1, 22)
  buffer.writeUInt32LE(sampleRate, 24); buffer.writeUInt32LE(sampleRate * 2, 28)
  buffer.writeUInt16LE(2, 32); buffer.writeUInt16LE(16, 34); buffer.write('data', 36); buffer.writeUInt32LE(dataBytes, 40)
  return buffer
}

export async function mockBackend(page: Page) {
  const document = {document_id:'doc-1', filename:'Lecture.pdf', file_type:'pdf', chunk_count:3, uploaded_at:'2026-10-12T12:00:00Z'}
  const sections = Array.from({length:3}, (_, id) => ({id, title:`Topic ${id + 1}`, script:`Revision passage ${id + 1}.`, script_language:'english', duration:10, start_seconds:id*10, end_seconds:(id+1)*10}))
  const audio = {action_id:'audio-1', document_id:'doc-1', status:'complete', summary:'Revision passage 1. Revision passage 2. Revision passage 3.', saved:true, error:null, provider:'direct', confirmation:'Your revision is ready.', intent:'audio_revision', trace:['summarize_document','create_revision_audio','save_audio_revision'], audio_ready:true, audio_saved:true, audio_duration:30, language:'english', summary_language:'english', revision_mode:'sectioned', sections}
  const cards = {...audio, action_id:'cards-1', intent:'flashcards', summary:null, audio_ready:false, audio_saved:false, audio_duration:null, sections:[], flashcards:[{question:'What is a dog?',answer:'A domesticated mammal.',source_quote:'Dogs are domesticated mammals.'}]}
  const results: Record<string, Record<string, unknown>> = {'audio-1':audio, 'cards-1':cards}
  const summary = (id: string) => {
    const result = results[id]
    return {...result, filename:document.filename, created_at:'2026-10-12T12:00:00Z'}
  }
  let savedIds = ['audio-1','cards-1']
  let documents = [document]
  const state = { actions: [] as Record<string, unknown>[], deletions: [] as Record<string, unknown>[], asks: [] as Record<string, unknown>[], uploads:0, transcriptions:0, tts:0 }
  await page.route('**/api/v1/**', async route => {
    const request = route.request()
    const path = new URL(request.url()).pathname
    const method = request.method()
    const headers = {'Access-Control-Allow-Origin':'*','Access-Control-Allow-Headers':'content-type,authorization','Access-Control-Allow-Methods':'GET,POST,PUT,DELETE,OPTIONS'}
    if (method === 'OPTIONS') return route.fulfill({status:204,headers})
    const json = async (value: unknown) => route.fulfill({json:value,headers})
    if (path === '/api/v1/documents/' && method === 'GET') return json(documents)
    if (path === '/api/v1/documents/upload') {state.uploads++; documents=[...documents,{...document,document_id:'doc-2',filename:'new-notes.txt'}]; return json(documents.at(-1))}
    if (path === '/api/v1/documents/doc-2' && method === 'DELETE') {documents=documents.filter(d=>d.document_id!=='doc-2');return json({deleted:true})}
    if (path === '/api/v1/documents/enhance') return json({enhanced_query:'Explain dogs clearly.'})
    if (path === '/api/v1/documents/ask') {state.asks.push(request.postDataJSON());return json({answer:'Dogs are domesticated mammals.',enhanced_query:null,references:[{document_id:'doc-1',filename:'Lecture.pdf',chunk_index:0,score:0.95,text:'Dogs are domesticated mammals.'}]})}
    if (path === '/api/v1/voice/transcribe') {state.transcriptions++;return json({transcript:'Explain dogs.',detected_language:'en',selected_language:'english',duration_ms:1000})}
    if (path === '/api/v1/voice/tts') {state.tts++;return route.fulfill({contentType:'audio/wav',body:silentWav(1),headers})}
    if (path === '/api/v1/actions/capabilities') return json({enabled:true,provider:'openclaw_mcp',sectioned_enabled:true,max_document_chars:12000})
    if (path === '/api/v1/actions/saved') return json(savedIds.map(summary))
    if (path === '/api/v1/actions' && method === 'POST') {
      const body = request.postDataJSON()
      state.actions.push(body)
      const command = body.command.toLowerCase()
      const id = `new-${state.actions.length}`
      const explicitLanguage = command.match(/in (tamil|sinhala|english) and save/)
      const language = explicitLanguage?.[1] || body.language
      const isCards = command.includes('flashcards')
      const isAudio = command.includes('audio revision')
      const sectionOnly = command.includes('section only')
      results[id] = {...(isCards ? cards : audio), action_id:id, provider:body.provider, language, summary_language:language,
        intent:isCards ? 'flashcards' : isAudio ? 'audio_revision' : 'summarize_and_save',
        audio_ready:isAudio, audio_saved:isAudio,
        summary:isCards ? null : isAudio ? audio.summary : 'A concise document summary.',
        sections:isAudio ? (sectionOnly ? [sections[body.section_id]] : sections) : [],
        target_duration:command.includes('one-minute') ? 60 : null,
        style:command.includes('detailed') ? 'detailed' : 'short',
        trace:isCards ? ['create_flashcards','save_flashcards'] : audio.trace}
      savedIds.push(id)
      return json({action_id:id})
    }
    const id = path.split('/')[4]
    if (path.endsWith('/audio')) return route.fulfill({contentType:'audio/wav',body:silentWav(),headers})
    if (path.endsWith('/download')) return route.fulfill({contentType:results[id]?.intent==='flashcards' ? 'application/json' : 'text/plain',body:results[id]?.intent==='flashcards' ? JSON.stringify(cards.flashcards) : 'Revision transcript.',headers})
    if (/\/sections\/\d+\/source$/.test(path)) return json({filename:'Lecture.pdf',excerpt:'Original source passage about dogs.',start:0,end:35})
    if (path.startsWith('/api/v1/actions/') && method === 'DELETE') {state.deletions.push(request.postDataJSON());savedIds=savedIds.filter(value=>value!==id);return json({deleted:true})}
    if (path.startsWith('/api/v1/actions/') && results[id]) return json(results[id])
    return route.fulfill({status:404,json:{detail:`Unexpected mock request ${method} ${path}`}})
  })
  return state
}
