import test from 'node:test';
import assert from 'node:assert/strict';
import { advanceRequest, answerRequest, isTerminal } from '../src/features/quiz/contracts.mjs';
import { historyForm, voiceForm } from '../src/features/audio/contracts.mjs';
import { readResponse, ApiError } from '../src/transport.mjs';
import { buildLabeledSvg } from '../src/features/visual/components/anatomyExport.ts';
test('answers obey integer timing and preserve original MCQ keys', () => {
  assert.deepEqual(answerRequest({q_id:'q1'},' 5 ',1000,2999),{q_id:'q1',answer:'5',time_taken_sec:2});
  assert.equal(answerRequest({q_id:'q1'},'answer',5000,2000).time_taken_sec,0);
});
test('only unfinished structured/essay questions use the advance contract', () => {
  assert.deepEqual(advanceRequest({q_id:'essay-1',q_type:'essay'}),{q_id:'essay-1'});
  assert.throws(()=>advanceRequest({q_id:'mcq-1',q_type:'mcq'}),/advance when/);
  assert.equal(isTerminal({},null),false);
  assert.equal(isTerminal({}, {is_correct:false,attempts:3,quiz_complete:false}),false);
  assert.equal(isTerminal({}, {is_correct:false,attempts:4,quiz_complete:false}),true);
  assert.equal(isTerminal({}, {is_correct:true,attempts:1,quiz_complete:false}),true);
});
test('voice uploads use audio_file instead of the document upload field', () => {
  const form=voiceForm({name:'question.webm',file:new Blob(['audio'],{type:'audio/webm'})},'tamil','session-1');
  assert.equal(form.has('file'),false);assert.equal(form.get('audio_file').name,'question.webm');assert.equal(form.get('language'),'tamil');assert.equal(form.get('session_id'),'session-1');
});
test('persistent audio history uses multipart JSON references and optional audio', () => {
  const references=[{filename:'biology.pdf',excerpt:'Cell respiration'}];
  const form=historyForm({question:'Why?',answer:'Because…',language:'english',references},new Blob(['wav']));
  assert.equal(form.get('question'),'Why?');assert.deepEqual(JSON.parse(form.get('references')),references);assert.equal(form.get('audio_file').name,'answer.wav');
});
test('DELETE 204 responses succeed without parsing nonexistent JSON', async () => {
  assert.equal(await readResponse(new Response(null,{status:204}),'Audio'),undefined);
});
test('validation errors and temporary analytics-not-ready responses retain status', async () => {
  await assert.rejects(()=>readResponse(new Response(JSON.stringify({detail:[{msg:'q_id is required'}]}),{status:422}),'Quiz'),e=>e instanceof ApiError&&e.status===422&&e.message==='q_id is required');
  await assert.rejects(()=>readResponse(new Response(JSON.stringify({detail:'Analytics not available'}),{status:404}),'Quiz'),e=>e.status===404);
});
test('3D 202 responses and binary TTS remain intact', async () => {
  assert.deepEqual(await readResponse(new Response('{"status":"pending"}',{status:202}),'3D'),{status:'pending'});
  const wav=await readResponse(new Response(new Uint8Array([1,2,3])),'Audio','blob');assert.equal(wav.size,3);
});
test('label SVG exports escape text and omit unverified annotations', () => {
  const annotation={structure_id:'heart',label:'Heart <script>',anchor_x:0.5,anchor_y:0.5,label_x:0.1,label_y:0.2,confidence:0.95,verified:true};
  const svg=buildLabeledSvg('abcd',[annotation,{...annotation,label:'UNVERIFIED',verified:false}]);
  assert.match(svg,/&lt;script&gt;/);assert.doesNotMatch(svg,/<script>/);assert.doesNotMatch(svg,/UNVERIFIED/);
});
