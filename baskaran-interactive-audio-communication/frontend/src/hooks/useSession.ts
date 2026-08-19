'use client'

import { useEffect, useState } from 'react'
import { createClient } from '@/lib/supabase'

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type SupabaseUser = { id: string } | any | null

export function useSession() {
  const [user, setUser] = useState<SupabaseUser>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const supabase = createClient()
    supabase.auth.getSession().then(({ data }) => {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      setUser((data.session as any)?.user ?? null)
      setLoading(false)
    })
  }, [])

  const signOut = async () => {
    const supabase = createClient()
    await supabase.auth.signOut()
  }

  return { user, loading, signOut }
}
