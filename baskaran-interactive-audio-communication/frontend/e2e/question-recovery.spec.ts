import {test,expect} from '@playwright/test'
import {mockBackend,silentWav} from './backendMock'

for(const failure of ['start','poll']) test(`mobile question resumes the same answer after ${failure} connection loss`,async({page})=>{
  test.skip(process.env.CLOUD_JOB_TEST!=='1','Requires isolated authenticated cloud export; all APIs are mocked')
  const state=await mockBackend(page)
  const user={id:'d9c5da63-1e3d-4d20-9aa3-b902cb22408d',aud:'authenticated',role:'authenticated',email:'learner@example.com'}
  const expires=Math.floor(Date.now()/1000)+3600
  const token=Buffer.from(JSON.stringify({alg:'HS256',typ:'JWT'})).toString('base64url')+'.'+Buffer.from(JSON.stringify({sub:user.id,exp:expires,aud:'authenticated'})).toString('base64url')+'.test-signature'
  await page.addInitScript(session=>localStorage.setItem('sb-example-auth-token',JSON.stringify(session)),{access_token:token,refresh_token:'mock-refresh',expires_at:expires,expires_in:3600,token_type:'bearer',user})
  const starts:string[]=[];let polls=0
  const answer={answer:'Dogs were domesticated from ancient wolves.',references:[]}
  await page.route('**/api/v1/history**',route=>route.fulfill({json:route.request().method()==='GET'?[]:{id:'11111111-1111-4111-8111-111111111111',created_at:new Date().toISOString(),question:"Tell about dog's history",answer:answer.answer,language:'english',references:[]}}))
  await page.route('**/api/v1/documents/ask-jobs**',route=>{
    if(route.request().method()==='POST'){
      starts.push(route.request().headers()['idempotency-key'])
      if(failure==='start'&&starts.length===1)return route.abort('connectionreset')
      return route.fulfill({status:202,json:{job_id:'job-1',status:'pending'}})
    }
    polls++
    if(failure==='poll'&&polls===1)return route.abort('connectionreset')
    return route.fulfill({json:polls<3?{status:'pending'}:{status:'complete',result:answer}})
  })
  await page.goto('/study-assistant')
  await page.locator('input[type=file][accept*="audio/wav"]').first().setInputFiles({name:'question.wav',mimeType:'audio/wav',buffer:silentWav(1)})
  await page.locator('#voice-submit-btn').click()
  const question=page.getByRole('textbox',{name:'Your Question',exact:true})
  await question.fill("Tell about dog's history")
  await page.getByRole('button',{name:'Ask →',exact:true}).click()
  await expect(page.getByText('The connection to the server was interrupted. Your question is kept. Check your connection, then retry.',{exact:true})).toBeVisible()
  await expect(question).toHaveValue("Tell about dog's history")
  await page.getByRole('button',{name:'Retry Answer',exact:true}).click()
  await expect(page.getByText(answer.answer,{exact:true}).first()).toBeVisible()
  expect(starts).toHaveLength(failure==='start'?2:1)
  expect(new Set(starts).size).toBe(1)
  await expect.poll(()=>state.tts).toBe(1)
})
