const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');

function loadModule(file, globals = {}, cache = new Map()) {
  const resolved = path.resolve(__dirname, '..', file);
  if (cache.has(resolved)) return cache.get(resolved);
  const source = fs.readFileSync(resolved, 'utf8');
  const code = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  const module = { exports: {} };
  cache.set(resolved, module.exports);
  const context = {
    module, exports: module.exports, process, console, setTimeout, clearTimeout, crypto: global.crypto,
    atob, ...globals,
    require: name => name.startsWith('.') ?
      loadModule(path.relative(path.resolve(__dirname, '..'), path.resolve(path.dirname(resolved), name + '.ts')), globals, cache) : require(name),
  };
  vm.runInNewContext(code, context, { filename: resolved });
  return module.exports;
}

const {createAuthActions,validateEmail,validateNewPassword,authMessage,authErrorCode}=loadModule('authActions.ts');
const redirect='https://studio.example/auth/callback';
function fixture(session=null){
 const calls=[];
 const auth=Object.fromEntries(['signInWithPassword','signUp','resetPasswordForEmail','resend','updateUser','signOut'].map(method=>[method,async(...args)=>{calls.push({method,args});return{data:{session},error:null};}]));
 return{auth,calls,actions:createAuthActions(auth,redirect)};
}

test('email changes update the existing authenticated user and request confirmation without creating an account',async()=>{
 const {auth,actions,calls}=fixture({user:{id:'same-owner'},access_token:'session'});
 auth.getUser=async()=>({data:{user:{id:'same-owner',email:'old@example.com'}},error:null});
 await actions.changeEmail('new@example.com','current-password');
 assert.deepEqual(JSON.parse(JSON.stringify(calls)),[
  {method:'signInWithPassword',args:[{email:'old@example.com',password:'current-password'}]},
  {method:'updateUser',args:[{email:'new@example.com'},{emailRedirectTo:redirect}]},
 ]);
});

test('email changes reject invalid addresses and a changed authenticated owner',async()=>{
 const {auth,actions,calls}=fixture({user:{id:'different-owner'}});
 auth.getUser=async()=>({data:{user:{id:'same-owner',email:'old@example.com'}},error:null});
 await assert.rejects(actions.changeEmail('invalid','current-password'),/valid email/);
 await assert.rejects(actions.changeEmail('new@example.com','current-password'),/Sign in again/);
 assert.equal(calls.filter(call=>call.method==='updateUser').length,0);
});
test('invalid inputs never send credentials to Supabase',async()=>{
 const {actions,calls}=fixture();
 await assert.rejects(actions.signIn('invalid','password'),/valid email/);
 await assert.rejects(actions.signUp('Koji','a@example.com','short','short'),/8 characters/);
 await assert.rejects(actions.signUp('Koji','a@example.com','abcdefgh','different'),/match/);
 await assert.rejects(actions.signUp('','a@example.com','abcdefgh','abcdefgh'),/name/);
 assert.equal(calls.length,0);
});
test('signup awaits email confirmation and sends name and component callback',async()=>{
 const {actions,calls}=fixture();
 assert.equal((await actions.signUp(' Koji ',' a@example.com ','abcdefgh','abcdefgh')).confirmationRequired,true);
 assert.equal(calls[0].args[0].email,'a@example.com');
 assert.equal(calls[0].args[0].options.data.full_name,'Koji');
 assert.equal(calls[0].args[0].options.emailRedirectTo,redirect);
 const immediate=fixture({access_token:'session'});
 assert.equal((await immediate.actions.signUp('Koji','a@example.com','abcdefgh','abcdefgh')).confirmationRequired,false);
});
test('recovery and resend links return to this component',async()=>{
 const {actions,calls}=fixture();
 await actions.resetPassword('a@example.com');await actions.resendVerification('a@example.com');
 assert.equal(calls[0].args[1].redirectTo,redirect);
 assert.equal(calls[1].args[0].type,'signup');
 assert.equal(calls[1].args[0].options.emailRedirectTo,redirect);
});
test('password update validates confirmation and signout is device scoped',async()=>{
 const {actions,calls}=fixture();
 await assert.rejects(actions.updatePassword('abcdefgh','mismatch'),/match/);
 await actions.updatePassword('abcdefgh','abcdefgh');await actions.signOut();
 assert.equal(calls[0].args[0].password,'abcdefgh');assert.equal(calls[1].args[0].scope,'local');
});
test('auth failures remain actionable without claiming sign-in succeeded',async()=>{
 const {auth,actions}=fixture();
 auth.signInWithPassword=async()=>({data:{session:null},error:{code:'invalid_credentials'}});
 await assert.rejects(actions.signIn('a@example.com','wrong'),/incorrect/);
 assert.match(authMessage({status:429}),/wait/);
 assert.match(authMessage({code:'email_not_confirmed'}),/Confirm your email/);
 assert.match(authMessage({message:'Failed to fetch'}),/internet/);
});

test('unconfirmed login preserves its code for conditional verification controls',async()=>{
 const {auth,actions}=fixture();
 auth.signInWithPassword=async()=>({data:{session:null},error:{code:'email_not_confirmed',message:'Email not confirmed'}});
 try { await actions.signIn('a@example.com','password'); assert.fail('expected rejection'); }
 catch(error){ assert.equal(authErrorCode(error),'email_not_confirmed'); assert.match(error.message,/Confirm your email/); }
 assert.equal(authErrorCode(new Error('network failure')),null);
});

test('reset email delivery failures reject with actionable errors and preserve provider codes',async()=>{
 for (const [error,message] of [
  [{code:'email_address_not_authorized',status:400},/Email delivery is unavailable/],
  [{code:'over_email_send_rate_limit',status:429},/email sending limit/],
  [{code:'unexpected_failure',status:500,message:'Error sending recovery email'},/couldn't send the email/],
 ]) {
  const {auth,actions}=fixture();
  auth.resetPasswordForEmail=async()=>({data:null,error});
  await assert.rejects(actions.resetPassword('a@example.com'),failure=>message.test(failure.message)&&authErrorCode(failure)===error.code);
 }
});

test('signed-in password changes verify the authenticated account before updating without email or signout',async()=>{
 const {auth,actions,calls}=fixture({access_token:'session'});
 auth.getUser=async()=>({data:{user:{email:'signed-in@example.com'}},error:null});
 await actions.changePassword('old-password','new-password','new-password');
 assert.deepEqual(JSON.parse(JSON.stringify(calls)),[
  {method:'signInWithPassword',args:[{email:'signed-in@example.com',password:'old-password'}]},
  {method:'updateUser',args:[{password:'new-password',current_password:'old-password'}]},
 ]);
});

test('invalid password-change inputs never reach Auth',async()=>{
 const {actions,calls}=fixture();
 await assert.rejects(actions.changePassword('','new-password','new-password'),/current password/);
 await assert.rejects(actions.changePassword('old-password','new-password','different'),/match/);
 await assert.rejects(actions.changePassword('old-password','short','short'),/8 characters/);
 await assert.rejects(actions.changePassword('old-password','old-password','old-password'),/different password/);
 assert.equal(calls.length,0);
});

test('missing sessions and incorrect current passwords never update a password',async()=>{
 const {auth,actions,calls}=fixture();
 auth.getUser=async()=>({data:{user:null},error:null});
 await assert.rejects(actions.changePassword('old-password','new-password','new-password'),/Sign in again/);
 assert.equal(calls.length,0);
 auth.getUser=async()=>({data:{user:{email:'signed-in@example.com'}},error:null});
 auth.signInWithPassword=async()=>({data:{session:null},error:{code:'invalid_credentials'}});
 await assert.rejects(actions.changePassword('wrong-password','new-password','new-password'),/current password is incorrect/);
 assert.equal(calls.length,0);
 auth.signInWithPassword=async()=>({data:{session:null},error:null});
 await assert.rejects(actions.changePassword('old-password','new-password','new-password'),/Sign in again/);
 assert.equal(calls.length,0);
});

test('password update failures are surfaced after successful current-password verification',async()=>{
 const {auth,actions}=fixture({access_token:'session'});
 auth.getUser=async()=>({data:{user:{email:'signed-in@example.com'}},error:null});
 auth.updateUser=async()=>({data:null,error:{code:'weak_password',message:'Password is too weak'}});
 await assert.rejects(actions.changePassword('old-password','new-password','new-password'),failure=>authErrorCode(failure)==='weak_password');
});
