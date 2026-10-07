// Local browser-test fixtures only. Never imported by the app or used as a
// fallback for real backends. All accounts and outputs below are synthetic.
import http from 'node:http';
import { spawn } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
const root=resolve(import.meta.dirname,'..');
const image=readFileSync(resolve(root,'../sarmitha-image-text-extractor-study-gen/frontend-rn/assets/icon.png')).toString('base64');
const user={id:'00000000-0000-4000-8000-000000000001',aud:'authenticated',role:'authenticated',email:'learner@example.test',user_metadata:{full_name:'Test Learner'},app_metadata:{provider:'email'},created_at:new Date().toISOString()};
const token=()=>`${Buffer.from('{"alg":"HS256","typ":"JWT"}').toString('base64url')}.${Buffer.from(JSON.stringify({sub:user.id,aud:'authenticated',role:'authenticated',exp:Math.floor(Date.now()/1000)+3600})).toString('base64url')}.fixture-signature`;
const sessions=new Map(),history=[],audioDocs=[]; let counter=0;
const references=[{document_id:'00000000-0000-4000-8000-000000000002',filename:'fixture-biology.txt',chunk_index:0,page:1,excerpt:'Synthetic reference for frontend testing.',score:0.94}];
const answer={answer:'**Fixture answer**\nThis synthetic response tests the tutor UI.',references};
function question(session){return{q_id:`q-${session.index}`,q_index:session.index,total_questions:2,question:'Fixture question: which organ pumps blood?',q_type:session.exam,options:session.exam==='mcq'?{'1':'Heart','2':'Brain','3':'Liver','4':'Kidney','5':'Lung'}:null,topic:'Circulation',bloom_level:'remember',difficulty:0.5,grounding_score:0.9,grounding_status:'grounded',source_file:'fixture-biology.txt',page_number:1,is_flagged:false};}
function result(session,correct){return{is_correct:correct,score:correct?1:0,feedback:correct?'Correct.':'Try again with this hint.',hint:correct?null:'Think about circulation.',hints_used:correct?0:session.attempts,attempts:session.attempts,next_question_available:!session.complete,quiz_complete:session.complete,correct_answer:correct?'1':null,correct_answer_text:correct?'Heart':null,explanation:correct?'The heart pumps blood.':null};}
function report(id){return{session_id:id,final_score:100,total_marks_earned:2,total_marks_possible:2,total_questions:2,total_answered:2,correct_count:2,topic_scores:{Circulation:{correct:2,total:2}},bloom_scores:{remember:{correct:2,total:2}},difficulty_progression:[0.5,0.7],avg_attempts:1,avg_hints_used:0,total_time_min:0.5,weak_topics:[],strong_topics:['Circulation'],recommendations:[{topic:'Circulation',recommendation_type:'enrichment',concept_notes:['Synthetic follow-up learning note.'],resources:[{title:'Research fixture resource',url:'https://example.com',label:'English'}]}],avg_grounding_score:0.9,flagged_questions_count:0,flagged_questions_pct:0,recommendations_pending:false,question_marks_detail:[{q_num:1,topic:'Circulation',bloom:'remember',difficulty:0.5,is_correct:true,attempts:1,hints_used:0,marks:1,max_marks:1,question:'Which organ pumps blood?',student_answer:'1',correct_answer:'Heart'}]};}
const gltf={asset:{version:'2.0'},scene:0,scenes:[{nodes:[0]}],nodes:[{mesh:0}],meshes:[{primitives:[{attributes:{POSITION:0}}]}],buffers:[{byteLength:36}],bufferViews:[{buffer:0,byteOffset:0,byteLength:36,target:34962}],accessors:[{bufferView:0,componentType:5126,count:3,type:'VEC3',min:[-1,-1,0],max:[1,1,0]}]};
const json=Buffer.from(JSON.stringify(gltf));const jsonChunk=Buffer.alloc(Math.ceil(json.length/4)*4,32);json.copy(jsonChunk);const vertices=Buffer.from(new Float32Array([-1,-1,0,1,-1,0,0,1,0]).buffer);const glb=Buffer.alloc(12+8+jsonChunk.length+8+vertices.length);glb.writeUInt32LE(0x46546c67,0);glb.writeUInt32LE(2,4);glb.writeUInt32LE(glb.length,8);glb.writeUInt32LE(jsonChunk.length,12);glb.writeUInt32LE(0x4e4f534a,16);jsonChunk.copy(glb,20);glb.writeUInt32LE(vertices.length,20+jsonChunk.length);glb.writeUInt32LE(0x004e4942,24+jsonChunk.length);vertices.copy(glb,28+jsonChunk.length);
const server=http.createServer(async(req,res)=>{
  res.setHeader('Access-Control-Allow-Origin','http://localhost:8086');res.setHeader('Access-Control-Allow-Headers','authorization,content-type,apikey,x-client-info,x-supabase-api-version');res.setHeader('Access-Control-Allow-Methods','GET,POST,PUT,DELETE,OPTIONS');
  if(req.method==='OPTIONS'){res.writeHead(204).end();return;}
  const chunks=[];for await(const chunk of req)chunks.push(chunk);const raw=Buffer.concat(chunks).toString();let body={};try{body=JSON.parse(raw);}catch{}
  const url=new URL(req.url,'http://localhost'),path=url.pathname;
  const send=(value,status=200)=>{res.writeHead(status,{'Content-Type':'application/json'}).end(JSON.stringify(value));};
  if(path==='/auth/v1/token'){send({access_token:token(),refresh_token:'fixture-refresh',token_type:'bearer',expires_in:3600,user});return;}
  if(path==='/auth/v1/user'){send(user);return;}
  if(path==='/auth/v1/logout'){res.writeHead(204).end();return;}
  if(path.endsWith('/health')){send({status:'ok'});return;}
  if(!req.headers.authorization){send({detail:'Fixture authentication required'},401);return;}
  if(path==='/quiz/api/v1/documents/'&&req.method==='GET'){send([{document_id:'doc-1',filename:'fixture-biology.txt',topics:['Circulation'],chunk_count:2,created_at:new Date().toISOString()}]);return;}
  if(path==='/quiz/api/v1/documents/upload'){send({document_id:'doc-1',topics:['Circulation']});return;}
  if(path==='/quiz/api/v1/session/start'){const id=`fixture-session-${++counter}`;sessions.set(id,{index:0,attempts:0,exam:body.exam_type,complete:false});send({session_id:id,status:'processing'});return;}
  const quizMatch=/^\/quiz\/api\/v1\/(session|quiz|analytics)\/([^/]+)\/(status|question|answer|advance|report|feedback)$/.exec(path);
  if(quizMatch){const[,service,id,action]=quizMatch;const session=sessions.get(id);if(!session){send({detail:'Session not found'},404);return;}
    if(action==='status'){send({status:'ready',message:''});return;}
    if(action==='question'){if(session.complete){send({detail:'No active question'},404);return;}send(question(session));return;}
    if(action==='answer'){if(!Number.isInteger(body.time_taken_sec)){send({detail:'Integer timing required'},422);return;}if(body.q_id!==`q-${session.index}`){send({detail:'Outdated question'},409);return;}session.attempts++;const correct=body.answer==='1'||body.answer==='Heart';const attempts=session.attempts;if(correct||attempts>=4){session.index++;session.complete=session.index>=2;}const value=result(session,correct);value.attempts=attempts;if(correct||attempts>=4)session.attempts=0;send(value);return;}
    if(action==='advance'){if(!['structured','essay'].includes(session.exam)||body.q_id!==`q-${session.index}`){send({detail:'Invalid advance'},422);return;}session.index++;session.complete=session.index>=2;send({quiz_complete:session.complete,result:{...result(session,false),explanation:'Fixture model answer.'}});return;}
    if(action==='report'){session.complete?send(report(id)):send({detail:'Analytics not available'},404);return;}
    if(action==='feedback'){send({message:'Saved'});return;}
  }
  if(path.startsWith('/notes/api/feedback/ocr')){send({status:'success'});return;}
  if(path==='/notes/api/enhance'){send({original_b64:image,enhanced_b64:image});return;}
  if(path==='/notes/api/ocr'){send({extracted_text:'පරීක්ෂණ සටහන'});return;}
  if(path==='/notes/api/process'){send({original_b64:image,enhanced_b64:image,extracted_text:'පරීක්ෂණ සටහන',extracted_text_ta:'சோதனை குறிப்பு',extracted_text_en:'Synthetic test note.',context_improved:false,lines:[{crop_b64:image,raw_text:'පරීක්ෂණ',final_text:'පරීක්ෂණ',confidence:0.92}]});return;}
  if(path==='/audio/api/v1/documents/'&&req.method==='GET'){send(audioDocs);return;}
  if(path==='/audio/api/v1/documents/upload'){const doc={document_id:'fixture-doc-'+ ++counter,filename:'fixture-biology.txt',file_type:'txt',chunk_count:2,uploaded_at:new Date().toISOString()};audioDocs.push(doc);send(doc,201);return;}
  if(path.startsWith('/audio/api/v1/documents/')&&req.method==='DELETE'){const i=audioDocs.findIndex(d=>d.document_id===path.split('/').pop());if(i>=0)audioDocs.splice(i,1);res.writeHead(204).end();return;}
  if(path==='/audio/api/v1/documents/ask'){send(answer);return;}
  if(path==='/audio/api/v1/documents/enhance'){send({enhanced_query:'Corrected fixture question.'});return;}
  if(path==='/audio/api/v1/voice/transcribe'||path==='/audio/api/v1/voice/query'){if(!raw.includes('name="audio_file"')){send({detail:'audio_file required'},422);return;}send(path.endsWith('/query')?{...answer,transcript:'Fixture voice question.',session_id:'00000000-0000-4000-8000-000000000003'}:{transcript:'Fixture voice question.',detected_language:'en'});return;}
  if(path==='/audio/api/v1/history'&&req.method==='GET'){send(history);return;}
  if(path==='/audio/api/v1/history'&&req.method==='POST'){const field=name=>new RegExp(`name="${name}"\\r\\n\\r\\n([^]*?)\\r\\n--`).exec(raw)?.[1]||'';const item={id:'history-'+ ++counter,question:field('question'),answer:field('answer'),language:field('language'),references:JSON.parse(field('references')||'[]'),has_audio:false,created_at:new Date().toISOString()};history.unshift(item);send(item,201);return;}
  if(path.includes('/history/')&&path.endsWith('/audio')&&req.method==='PUT'){const item=history.find(v=>v.id===path.split('/').at(-2));if(item)item.has_audio=true;send(item);return;}
  if(path==='/audio/api/v1/voice/tts'||(path.includes('/history/')&&path.endsWith('/audio'))){const wav=Buffer.alloc(44+16000);wav.write('RIFF');wav.writeUInt32LE(wav.length-8,4);wav.write('WAVEfmt ',8);wav.writeUInt32LE(16,16);wav.writeUInt16LE(1,20);wav.writeUInt16LE(1,22);wav.writeUInt32LE(8000,24);wav.writeUInt32LE(16000,28);wav.writeUInt16LE(2,32);wav.writeUInt16LE(16,34);wav.write('data',36);wav.writeUInt32LE(16000,40);res.writeHead(200,{'Content-Type':'audio/wav'}).end(wav);return;}
  if(path.startsWith('/audio/api/v1/sessions/')){send(req.method==='POST'?{session_id:'00000000-0000-4000-8000-000000000003'}:{language:'english',messages:[]});return;}
  if(path==='/prompt/enhance'){send({enhanced_prompt:'Fixture heart anatomy',enhanced_prompt_json:{schema_version:'1.0',final_prompt:'Fixture heart anatomy',route:'anatomy',anatomy_mode:'verified',anatomy_spec:{is_anatomy:true,organ:'heart',view:'anterior',view_description:'Anterior heart',required_structures:['left_ventricle']}}});return;}
  if(path==='/image/generate'){send({image_base64:image});return;}
  if(path==='/visual/generate'){send({image_base64:image,enhanced_prompt:'Fixture guided biology visual',anatomy_spec:{is_anatomy:false},retry_count:0,error:null,eval_scores:{visual_score:9,pedagogical_score:9,clip_score:0.9,vlm_score:9,vlm_feedback:'Synthetic guided evaluation.',anatomy_hard_failures:[]}});return;}
  if(path==='/evaluation/evaluate'){send({visual_score:9,pedagogical_score:9,vlm_score:9,clip_score:0.9,vlm_feedback:'Synthetic evaluation passed.',anatomy_hard_failures:[]});return;}
  if(path==='/interactive/auto-labels'){send({annotations:[{structure_id:'left_ventricle',label:'Left ventricle',anchor_x:0.5,anchor_y:0.5,label_x:0.1,label_y:0.2,verified:true,confidence:0.95}]});return;}
  if(path==='/interactive/analyze'){send({response_text:'Fixture selected region explanation.',highlighted_base64:image});return;}
  if(path==='/threed/convert/start'){send({call_id:'fixture-job'},202);return;}
  if(path==='/threed/convert/result/fixture-job'){send({glb_base64:glb.toString('base64'),size_kb:glb.length/1024});return;}
  if(path==='/visual/feedback'){send({feedback_id:'fixture-feedback'},201);return;}
  if(path==='/visual/memory/context'){send({context:''});return;}
  if(path==='/visual/memory/settings'){send({memory_enabled:!!body.memory_enabled});return;}
  if(path==='/visual/memory/preferences'){send({preferences:[]});return;}
  if(path.startsWith('/visual/memory/')){send({status:'ok'});return;}
  send({detail:`Unhandled fixture route: ${req.method} ${path}`},404);
});
server.listen(8790,'127.0.0.1',()=>console.log('Synthetic frontend fixtures: http://127.0.0.1:8790'));
const env={...process.env,CI:'1',EXPO_PUBLIC_SUPABASE_URL:'http://127.0.0.1:8790',EXPO_PUBLIC_SUPABASE_ANON_KEY:'synthetic-test-key'};
for(const name of ['VISUAL','QUIZ','NOTES','AUDIO','PROMPT','IMAGE','INTERACTIVE','EVALUATION','THREED'])env[`EXPO_PUBLIC_${name}_API_URL`]=`http://127.0.0.1:8790/${name.toLowerCase()}`;
const expo=spawn(process.execPath,[resolve(root,'node_modules/expo/bin/cli'),'start','--web','--port','8086','--localhost'],{cwd:root,env,stdio:'inherit',windowsHide:true});
function stop(){expo.kill();server.close();}
process.on('SIGINT',stop);process.on('SIGTERM',stop);expo.on('exit',()=>{server.close();});
