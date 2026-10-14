import { Fragment, useEffect, type ReactNode } from 'react'
import { View, StyleSheet } from 'react-native'
import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { ThemeProvider } from '@/components/ui/ThemeProvider'
import Link from '@/web/navigation'
import HomeScreen from '@/screens/Home.web'
import StudyAssistantScreen from '@/screens/StudyAssistant.web'
import DocumentsScreen from '@/screens/Documents.web'
import LoginScreen from '@/screens/Login.web'
import RegisterScreen from '@/screens/Register.web'
import DashboardScreen from '@/screens/Dashboard.web'
import DashboardDocumentsScreen from '@/screens/DashboardDocuments.web'
import DashboardHistoryScreen from '@/screens/DashboardHistory.web'
import { AUTH_REQUIRED } from '@/lib/config'
import { useSession } from '@/hooks/useSession'
import './src/styles/generated.css'

function NavigationEffects() {
  const { pathname } = useLocation()
  useEffect(() => {
    document.title = 'VoiceLearn AI — Voice-Powered Study Assistant'
    window.scrollTo(0, 0)
  }, [pathname])
  return null
}

export default function App() {
  return (
    <View style={styles.root} testID="expo-web-root">
      <ThemeProvider>
        <BrowserRouter>
          <NavigationEffects />
          <Routes>
            <Route path="/" element={<HomeScreen />} />
            <Route path="/study-assistant" element={<RequireSession><StudyAssistantScreen /></RequireSession>} />
            <Route path="/test" element={<Navigate to="/study-assistant" replace />} />
            <Route path="/documents" element={<RequireSession><DocumentsScreen /></RequireSession>} />
            <Route path="/login" element={<LoginScreen />} />
            <Route path="/register" element={<RegisterScreen />} />
            <Route path="/dashboard" element={<RequireSession><DashboardScreen /></RequireSession>} />
            <Route path="/dashboard/documents" element={<RequireSession><DashboardDocumentsScreen /></RequireSession>} />
            <Route path="/dashboard/history" element={<RequireSession><DashboardHistoryScreen /></RequireSession>} />
            <Route path="*" element={<main className="p-8"><h1>Page not found</h1><Link href="/study-assistant">Open Study Assistant</Link></main>} />
          </Routes>
        </BrowserRouter>
      </ThemeProvider>
    </View>
  )
}

function RequireSession({ children }: { children: ReactNode }) {
  const { user, loading } = useSession()
  if (!AUTH_REQUIRED) return children
  if (loading) return <main className="p-8">Checking your session...</main>
  if (!user) return <Navigate to="/login" replace />
  return <Fragment key={user?.id ?? 'demo'}>{children}</Fragment>
}

// Preserve CSS page flow: native flex sizing must not shrink browser controls.
const styles = StyleSheet.create({ root: { display: 'contents' } })
