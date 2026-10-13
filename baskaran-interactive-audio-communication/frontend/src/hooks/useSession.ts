'use client'

import { useEffect, useState } from 'react'
import { createClient } from '@/lib/supabase'

type SupabaseUser = { id: string } | null

export function useSession() {
  const [user, setUser] = useState<SupabaseUser>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const supabase = createClient()
    let active = true
    supabase.auth.getSession().then(({ data }) => {
      if (!active) return
      setUser(data.session?.user ?? null)
      setLoading(false)
    }).catch(() => { if (active) { setUser(null); setLoading(false) } })
    const { data } = supabase.auth.onAuthStateChange((_event, session) => {
      if (active) { setUser(session?.user ?? null); setLoading(false) }
    })
    return () => { active = false; data.subscription.unsubscribe() }
  }, [])

  const signOut = async () => {
    const supabase = createClient()
    await supabase.auth.signOut()
  }

  return { user, loading, signOut }
}
