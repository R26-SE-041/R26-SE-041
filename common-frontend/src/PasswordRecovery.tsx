import React, { useState } from 'react';
import { View, Text } from 'react-native';
import { auth } from './auth';
import { Button, Card, colors, Field, Notice, styles } from './ui';
export default function PasswordRecovery({ done }: { done: () => void }) {
  const [password,setPassword]=useState(''),[confirmation,setConfirmation]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState(''),[saved,setSaved]=useState(false);
  return <View style={{flex:1,backgroundColor:colors.bg,padding:24,justifyContent:'center',alignItems:'center'}}><Card style={{width:'100%',maxWidth:420}}><Text style={styles.heading}>Choose your new password</Text>{saved?<><Notice text="Your password has been updated." /><Button label="Continue to workspace" onPress={done} /></>:<><Field label="NEW PASSWORD" value={password} onChange={setPassword} secure /><Field label="CONFIRM PASSWORD" value={confirmation} onChange={setConfirmation} secure /><Button label={busy?'Updating…':'Update password'} disabled={busy||password.length<6||password!==confirmation} onPress={async()=>{if(!auth)return;setBusy(true);setError('');try{const{error}=await auth.auth.updateUser({password});if(error)throw error;setSaved(true);}catch(e){setError(e instanceof Error?e.message:'Password update failed.');}finally{setBusy(false);}}} /><Notice text={error} error /></>}</Card></View>;
}
