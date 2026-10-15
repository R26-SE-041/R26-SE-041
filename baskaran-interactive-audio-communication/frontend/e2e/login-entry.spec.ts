import {test,expect} from '@playwright/test'
import {mockBackend} from './backendMock'

test('home shortcuts always open sign-in first',async({page})=>{
  await page.goto('/')
  await page.getByRole('link',{name:/Voice Studio/}).click()
  await expect(page).toHaveURL(/\/login\?next=%2Fstudy-assistant$/)
  await expect(page.getByLabel('Password',{exact:true})).toBeVisible()
  await expect(page.getByRole('heading',{name:'Learn with your voice'})).toHaveCount(0)
  await page.goto('/')
  await page.getByRole('link',{name:/Document Library/}).click()
  await expect(page).toHaveURL(/\/login\?next=%2Fdocuments$/)
})

test('remembered session still requires a new successful sign-in from home',async({page})=>{
  test.skip(process.env.SIGNUP_AUTH_TEST!=='1','Requires Supabase-configured export; auth is mocked')
  await mockBackend(page)
  const user={id:'d9c5da63-1e3d-4d20-9aa3-b902cb22408d',aud:'authenticated',role:'authenticated',email:'learner@example.com'}
  const payload={sub:user.id,exp:Math.floor(Date.now()/1000)+3600,iss:'https://example.supabase.co/auth/v1',aud:'authenticated'}
  const token=Buffer.from(JSON.stringify({alg:'HS256',typ:'JWT'})).toString('base64url')+'.'+Buffer.from(JSON.stringify(payload)).toString('base64url')+'.test-signature'
  const session={access_token:token,refresh_token:'mock-refresh',token_type:'bearer',expires_at:payload.exp,expires_in:3600,user}
  await page.addInitScript(value=>localStorage.setItem('sb-example-auth-token',JSON.stringify(value)),session)
  let attempts=0
  await page.route('**/auth/v1/token**',route=>{
    attempts++
    return attempts===1?route.fulfill({status:400,json:{error:'invalid_grant',error_description:'Invalid login credentials'}}):route.fulfill({json:session})
  })
  await page.goto('/')
  await page.getByRole('link',{name:/Voice Studio/}).click()
  await expect(page.getByLabel('Password',{exact:true})).toBeVisible()
  expect(attempts).toBe(0)
  await page.getByLabel('Email',{exact:true}).fill(user.email)
  await page.getByLabel('Password',{exact:true}).fill('a test password')
  await page.locator('#login-submit').click()
  await expect(page.getByRole('alert')).toBeVisible()
  await expect(page).toHaveURL(/\/login\?/)
  await page.locator('#login-submit').click()
  await expect(page).toHaveURL(/\/study-assistant$/)
  await expect(page.getByRole('heading',{name:'Learn with your voice'})).toBeVisible()
  await page.goto('/')
  await page.getByRole('link',{name:/Document Library/}).click()
  await page.getByLabel('Email',{exact:true}).fill(user.email)
  await page.getByLabel('Password',{exact:true}).fill('a test password')
  await page.locator('#login-submit').click()
  await expect(page).toHaveURL(/\/documents$/)
  await page.goto('/login?next=https%3A%2F%2Foutside.example.invalid')
  await page.getByLabel('Email',{exact:true}).fill(user.email)
  await page.getByLabel('Password',{exact:true}).fill('a test password')
  await page.locator('#login-submit').click()
  await expect(page).toHaveURL(/\/study-assistant$/)
})
