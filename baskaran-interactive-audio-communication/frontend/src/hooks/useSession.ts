'use client'

import { useEffect, useState } from 'react'
import { createClient } from '@/lib/supabase'

type SupabaseUser = { id: string } | null

export function useSession() {
  const [user, setUser] = useState<SupabaseUser>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const supabase = createClient()
    supabase.auth.getSession().then(({ data }) => {
      setUser(data.session?.user ?? null)
      setLoading(false)
    })
  }, [])

  const signOut = async () => {
    const supabase = createClient()
    await supabase.auth.signOut()
  }

  return { user, loading, signOut }
}
