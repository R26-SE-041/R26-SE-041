import React, { useEffect, useRef, useState } from 'react';
import { Text, View } from 'react-native';
import { api, ApiError } from '../../api';
import { listArchive, removeArchive, saveArchive } from '../../archive';
import { delay, useTask } from '../../task';
import FilePicker, { Upload } from '../../FilePicker';
import Markdown from '../../Markdown';
import { Button, Busy, Card, Choices, Field, Notice, PageHeading, styles } from '../../ui';
import { advanceRequest, answerRequest, isOpenEnded, isTerminal } from './contracts.mjs';
import Results from './Results';
import type { AnswerResult, Document, Exam, Question, Report, SavedSession } from './types';
export default function Quiz({ userId }: { userId: string }) {
  const [tab, setTab] = useState('Practice'), [topic, setTopic] = useState(''), [difficulty, setDifficulty] = useState('adaptive'), [count, setCount] = useState('5'), [exam, setExam] = useState<Exam>('mcq'), [minutes, setMinutes] = useState('');
  const [docs, setDocs] = useState<Document[]>([]), [selected, setSelected] = useState<string[]>([]), [archive, setArchive] = useState<SavedSession[]>([]), [info, setInfo] = useState('');
  const [session, setSession] = useState<SavedSession | null>(null), [question, setQuestion] = useState<Question | null>(null), [answer, setAnswer] = useState(''), [feedback, setFeedback] = useState<AnswerResult | null>(null), [report, setReport] = useState<Report | null>(null), [reveal, setReveal] = useState<AnswerResult | null>(null), [clock, setClock] = useState(Date.now());
  const task = useTask(), started = useRef(Date.now()), sessionRef = useRef<SavedSession | null>(null);
  useEffect(() => { const timer = setInterval(() => setClock(Date.now()), 1000); return () => clearInterval(timer); }, []);
  async function remember(item: SavedSession) {
    sessionRef.current = item; setSession(item);
    try { await saveArchive('quiz', userId, item); } catch (e) { setInfo(e instanceof Error ? e.message : 'Session could not be saved locally.'); }
  }
  const loadQuestion = async (id: string, signal: AbortSignal, previousId?: string) => {
    const deadline = Date.now() + 120000;
    while (!signal.aborted && Date.now() < deadline) {
      try {
        const next = await api<Question>('quiz', `/api/v1/quiz/${encodeURIComponent(id)}/question`, undefined, { signal });
        if (next.q_id === previousId) { await delay(1500,signal); continue; }
        setQuestion(next); setAnswer(''); setFeedback(null); started.current = Date.now();
        if (sessionRef.current) await remember({ ...sessionRef.current, question: next, feedback: null });
        return;
      } catch (e) { if (!(e instanceof ApiError) || e.status !== 404) throw e; await delay(1500, signal); }
    }
    throw new Error('The next question is still being prepared. Use Resume quiz to check again.');
  };
  const loadReport = async (id: string, signal: AbortSignal) => {
    const deadline = Date.now()+90000;
    while (!signal.aborted && Date.now() < deadline) {
      try { const value = await api<Report>('quiz', `/api/v1/analytics/${encodeURIComponent(id)}/report`, undefined, { signal }); setReport(value); setQuestion(null); if (sessionRef.current) await remember({ ...sessionRef.current, complete: true, report: value }); return; }
      catch (e) { if (!(e instanceof ApiError) || e.status !== 404) throw e; await delay(1500,signal); }
    }
    throw new Error('Results are still being prepared. Use View results to retry.');
  };
  const resume = async (item: SavedSession, signal: AbortSignal) => {
    setTab('Practice'); setReveal(null); setInfo(''); sessionRef.current = item; setSession(item); setReport(null); setQuestion(null); setFeedback(null);
    if (item.complete || item.feedback?.quiz_complete) { await loadReport(item.id, signal); return; }
    const deadline = Date.now() + 240000;
    while (!signal.aborted && Date.now() < deadline) {
      const status = await api<{status:string;message:string}>('quiz', `/api/v1/session/${encodeURIComponent(item.id)}/status`, undefined, { signal });
      if (status.status === 'error') throw new Error(status.message || 'Quiz generation failed. Start a new practice session.');
      if (status.status === 'ready') {
        // A terminal answer already advanced backend state. Keep its feedback visible
        // until the learner explicitly opens the next question/results.
        if (item.question && item.feedback) { setQuestion(item.question); setFeedback(item.feedback); return; }
        await loadQuestion(item.id,signal); return;
      }
      await delay(2000,signal);
    }
    throw new Error('This session is still processing. Resume it shortly.');
  };
  const upload = (file: Upload) => task.run(async signal => { const body = new FormData(); body.append('file',file.file,file.name); const doc = await api<{document_id:string;topics:string[]}>('quiz','/api/v1/documents/upload',body,{signal}); setDocs(v => [...v.filter(d => d.document_id !== doc.document_id),{document_id:doc.document_id,filename:file.name,topics:doc.topics || [],chunk_count:0,created_at:new Date().toISOString()}]); setSelected(v => [...new Set([...v,doc.document_id])]); setInfo(`${file.name} uploaded and selected.`); });
  const next = () => task.run(async signal => {
    if (!session || !question) return;
    if (feedback?.quiz_complete) { await loadReport(session.id, signal); return; }
    if (isOpenEnded(question.q_type) && !isTerminal(question,feedback)) {
      const advanced = await api<{quiz_complete:boolean;result:AnswerResult}>('quiz',`/api/v1/quiz/${session.id}/advance`,advanceRequest(question),{signal});
      setReveal(advanced.result);
      await remember({...session,feedback:advanced.result});
      if (advanced.quiz_complete) await loadReport(session.id,signal); else await loadQuestion(session.id,signal,question.q_id);
      return;
    }
    if (!isTerminal(question,feedback)) return;
    await loadQuestion(session.id,signal,question.q_id);
  });
  const reset = () => { sessionRef.current = null; setSession(null); setQuestion(null); setFeedback(null); setReport(null); setReveal(null); setAnswer(''); };
  const remaining = session?.timeLimit ? Math.max(0,session.timeLimit*60-Math.floor((clock-session.startedAt)/1000)) : null;
  return <View style={styles.page}><PageHeading eyebrow="02 / ADAPTIVE ASSESSMENT" title="Practice with purpose." description="Independent quizzes, document-based practice, hints and learning recommendations—all in your assessment workspace." /><Choices values={['Practice','Document library','Session history']} selected={tab} onChange={v => { setTab(v); if (v === 'Session history') void task.run(async () => setArchive(await listArchive('quiz',userId))); }} /><Notice text={info} />
    {tab === 'Document library' && <Card><Text style={styles.heading}>Study documents</Text><FilePicker disabled={task.busy} accept=".pdf,.docx,.pptx,.txt,.png,.jpg,.jpeg" onPick={upload} /><Button secondary label="Refresh library" disabled={task.busy} onPress={() => task.run(async signal => setDocs(await api('quiz','/api/v1/documents/',undefined,{signal})))} />{docs.map(doc => <View key={doc.document_id} style={{ gap:8 }}><Button secondary label={`${selected.includes(doc.document_id)?'✓ ':''}${doc.filename}`} onPress={() => setSelected(v => v.includes(doc.document_id) ? v.filter(id => id !== doc.document_id) : [...v,doc.document_id])} /><Text style={styles.subtitle}>{doc.topics.join(', ')}{doc.chunk_count ? ` · ${doc.chunk_count} chunks` : ''}</Text></View>)}{!docs.length && <Text style={styles.subtitle}>Upload a document or refresh the existing library. This backend currently exposes a shared library.</Text>}<Button label="Practice with selected documents" onPress={() => setTab('Practice')} /></Card>}
    {tab === 'Session history' && <Card><Text style={styles.heading}>Your saved assessment sessions</Text><Text style={styles.subtitle}>Local to this browser and account; backend sessions remain in the assessment service.</Text><Button secondary label="Refresh sessions" disabled={task.busy} onPress={() => task.run(async () => setArchive(await listArchive('quiz',userId)))} />{archive.map(item => <View key={item.id} style={{ gap:8 }}><Text style={styles.body}>{item.title} · {item.complete?'Completed':'In progress'}</Text><Text style={styles.subtitle}>{new Date(item.createdAt).toLocaleString()}</Text><View style={styles.row}><Button label={item.complete?'View results':'Resume'} disabled={task.busy} onPress={() => task.run(signal => resume(item,signal))} /><Button secondary label="Remove local entry" disabled={task.busy} onPress={() => task.run(async () => { await removeArchive('quiz',userId,item.id); setArchive(v => v.filter(a => a.id !== item.id)); })} /></View></View>)}{!archive.length && <Text style={styles.subtitle}>No saved assessment sessions yet.</Text>}</Card>}
    {tab === 'Practice' && <>{!session && <Card><Field label="BIOLOGY TOPIC" value={topic} onChange={setTopic} placeholder="e.g. Cellular respiration" /><Text style={styles.label}>OR UPLOAD STUDY MATERIAL</Text><FilePicker disabled={task.busy} accept=".pdf,.docx,.pptx,.txt,.png,.jpg,.jpeg" onPick={upload} /><Text style={styles.subtitle}>{selected.length} study documents selected. Use Document library to review your selection.</Text><Text style={styles.label}>QUESTION FORMAT</Text><Choices values={selected.length?['mcq','fill_blank','structured','essay']:['mcq']} selected={selected.length?exam:'mcq'} onChange={v => setExam(v as Exam)} /><Text style={styles.label}>DIFFICULTY</Text><Choices values={['easy','medium','hard','adaptive']} selected={difficulty} onChange={setDifficulty} /><Text style={styles.label}>NUMBER OF QUESTIONS</Text><Choices values={['5','10','20','50']} selected={count} onChange={setCount} /><Field label="OPTIONAL TIME LIMIT (MINUTES)" value={minutes} onChange={v => setMinutes(v.replace(/\D/g,''))} placeholder="No time limit" /><Button label="Start practice ↗" disabled={task.busy || (!topic.trim()&&!selected.length) || (!!minutes && Number(minutes)<1)} onPress={() => task.run(async signal => {
      setInfo(''); const response = await api<{session_id:string}>('quiz','/api/v1/session/start',{topic:topic.trim()||null,document_ids:selected,student_id:userId,exam_type:selected.length?exam:'mcq',num_questions:Number(count),difficulty_mode:difficulty,time_limit_min:minutes?Number(minutes):null},{signal});
      const item:SavedSession = {id:response.session_id,createdAt:new Date().toISOString(),title:topic.trim()||docs.filter(d=>selected.includes(d.document_id)).map(d=>d.filename).join(', ')||'Document practice',complete:false,startedAt:Date.now(),timeLimit:minutes?Number(minutes):undefined}; await remember(item); await resume(item,signal);
    })} /></Card>}
    {session && <View style={styles.row}><Text style={styles.subtitle}>Session: {session.title}</Text>{remaining != null && <Text style={styles.subtitle}>{Math.floor(remaining/60)}:{String(remaining%60).padStart(2,'0')} remaining</Text>}<Button secondary label="New practice" disabled={task.busy} onPress={reset} /></View>}{remaining===0 && <Notice text="Your selected time limit has elapsed. Finish the current practice or start a new session; no answers are submitted automatically." />}
    {session && !question && !report && !task.busy && <Card><Text style={styles.body}>Your session is saved. Resume processing or check results.</Text><View style={styles.row}><Button label="Resume quiz" onPress={() => task.run(signal => resume(session,signal))} /><Button secondary label="View results" onPress={() => task.run(signal=>loadReport(session.id,signal))} /></View></Card>}
    {reveal && <Card><Text style={styles.heading}>Previous question · model answer</Text><Markdown text={reveal.explanation||reveal.correct_answer_text||reveal.feedback} /><Button secondary label="Dismiss" onPress={()=>setReveal(null)} /></Card>}
    {question && <Card><Text style={styles.label}>QUESTION {question.q_index+1} / {question.total_questions} · {question.topic}</Text><View style={{height:6,backgroundColor:'#E5DFD4',borderRadius:3}}><View style={{height:6,width:`${question.q_index/question.total_questions*100}%`,backgroundColor:'#BD654D'}} /></View><Markdown text={question.question} /><Text style={styles.subtitle}>{question.q_type.replace('_',' ')} · {question.bloom_level} · Difficulty {Math.round(question.difficulty*100)}%</Text><Text style={styles.subtitle}>{question.grounding_status==='topic_model'?'Topic-based question':`${question.source_file}${question.page_number>0?` · Page ${question.page_number}`:''} · Grounding ${Math.round(question.grounding_score*100)}%`}</Text>{question.is_flagged && <Notice text="Source grounding needs review for this question." />}
    {question.options ? Object.entries(question.options).map(([key,text])=><Button key={key} secondary label={`${answer===key?'●':'○'} ${key}. ${text}`} disabled={task.busy||isTerminal(question,feedback)} onPress={()=>setAnswer(key)} />):<Field label="YOUR ANSWER" value={answer} onChange={setAnswer} multiline />}
    <Button label={feedback&&!isTerminal(question,feedback)?'Retry answer':'Check answer'} disabled={task.busy||!answer.trim()||isTerminal(question,feedback)} onPress={()=>task.run(async signal=>{const value=await api<AnswerResult>('quiz',`/api/v1/quiz/${session!.id}/answer`,answerRequest(question,answer,started.current),{signal});setFeedback(value);await remember({...session!,question,feedback:value});})} />
    {feedback && <View style={{gap:12}}><Text style={styles.heading}>{feedback.is_correct?'Correct':feedback.attempts>=4?'Answer revealed':`Attempt ${feedback.attempts}/4`}</Text><Markdown text={feedback.feedback} />{feedback.hint&&!isTerminal(question,feedback)&&<Notice text={`${['Conceptual hint','Focused hint','Step-by-step hint'][Math.min(feedback.attempts-1,2)]}: ${feedback.hint}`} />}{isTerminal(question,feedback)&&<><Text style={styles.body}>Expected answer: {feedback.correct_answer_text||feedback.correct_answer||'Not returned'}</Text>{feedback.explanation&&<Markdown text={feedback.explanation} />}</>}<Text style={styles.subtitle}>Score: {Math.round(feedback.score*100)}% · Hints used: {feedback.hints_used}</Text></View>}
    {(isTerminal(question,feedback)||isOpenEnded(question.q_type))&&<Button secondary={!isTerminal(question,feedback)} label={feedback?.quiz_complete?'View results':isTerminal(question,feedback)?'Next question':feedback?'Finalize & reveal model answer':'Skip & reveal model answer'} disabled={task.busy} onPress={next} />}
    </Card>}
    {report && <Results key={report.session_id} report={report} refresh={()=>void task.run(signal=>loadReport(report.session_id,signal))} restart={reset} />}</>}
    {task.busy && <Busy text="Working with your assessment service…" />}<Notice text={task.error} error />
  </View>;
}
