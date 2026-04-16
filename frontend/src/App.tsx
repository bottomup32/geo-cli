import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/layout/Layout'
import InterviewPage from './pages/InterviewPage'
import PipelinePage from './pages/PipelinePage'
import DataPage from './pages/DataPage'
import PromptEditorPage from './pages/PromptEditorPage'
import SettingsPage from './pages/SettingsPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<InterviewPage />} />
          <Route path="/pipeline" element={<PipelinePage />} />
          <Route path="/data" element={<DataPage />} />
          <Route path="/prompts" element={<PromptEditorPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
