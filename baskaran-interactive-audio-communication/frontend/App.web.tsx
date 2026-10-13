import { useEffect } from 'react'
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
            <Route path="/study-assistant" element={<StudyAssistantScreen />} />
            <Route path="/test" element={<Navigate to="/study-assistant" replace />} />
            <Route path="/documents" element={<DocumentsScreen />} />
            <Route path="/login" element={<LoginScreen />} />
            <Route path="/register" element={<RegisterScreen />} />
            <Route path="/dashboard" element={<DashboardScreen />} />
            <Route path="/dashboard/documents" element={<DashboardDocumentsScreen />} />
            <Route path="/dashboard/history" element={<DashboardHistoryScreen />} />
            <Route path="*" element={<main className="p-8"><h1>Page not found</h1><Link href="/study-assistant">Open Study Assistant</Link></main>} />
          </Routes>
        </BrowserRouter>
      </ThemeProvider>
    </View>
  )
}

// Preserve CSS page flow: native flex sizing must not shrink browser controls.
const styles = StyleSheet.create({ root: { display: 'contents' } })
