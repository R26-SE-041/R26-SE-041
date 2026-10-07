import fs from 'node:fs';
const base = 'https://agal-koji--sketch-agent-api.modal.run';
console.log('health', await (await fetch(base + '/health')).json());
const invalid = await fetch(base + '/generate/start', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({strokes:[]}) });
if (invalid.status !== 422) throw new Error(`Invalid sketch status ${invalid.status}`);
console.log('blank validation', invalid.status);
const points = Array.from({length: 81}, (_, i) => {
  const theta = i / 80 * Math.PI * 2;
  return [0.5 + 0.28 * Math.cos(theta), 0.5 + 0.23 * Math.sin(theta)];
});
const request = {strokes:[{points, width:0.006, tool:'pen'}, {points:[[0.36,0.44],[0.4,0.44]],width:0.02,tool:'pen'}, {points:[[0.6,0.44],[0.64,0.44]],width:0.02,tool:'pen'}, {points:[[0.38,0.56],[0.5,0.63],[0.62,0.56]],width:0.006,tool:'pen'}],instruction:'',seed:42};
const started = await fetch(base + '/generate/start', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(request)});
const job = await started.json();
if (!started.ok || !job.call_id) throw new Error(JSON.stringify(job));
console.log('job',job.call_id);
const deadline=Date.now()+600000;
while(Date.now()<deadline){
  await new Promise(resolve=>setTimeout(resolve,5000));
  const response=await fetch(base+'/generate/result/'+job.call_id);
  if(response.status===202) continue;
  const result=await response.json();
  if(!response.ok||!result.image_base64) throw new Error(JSON.stringify(result));
  fs.mkdirSync('output/sketch-validation',{recursive:true});
  fs.writeFileSync('output/sketch-validation/generated.png',Buffer.from(result.image_base64,'base64'));
  fs.writeFileSync('output/sketch-validation/result.json',JSON.stringify({request, ...result,image_base64:undefined},null,2));
  console.log('generation passed',result.generation_metadata);
  process.exit(0);
}
throw new Error('Generation smoke test timed out');
