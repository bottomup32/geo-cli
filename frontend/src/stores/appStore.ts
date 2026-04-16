import { create } from 'zustand'
import type { ChatMessage, BriefDetail } from '../types'

interface AppState {
  // Interview
  sessionId: string
  chatMessages: ChatMessage[]
  interviewDone: boolean
  briefDict: Record<string, any> | null
  streamingText: string

  // Active brief
  activeBrief: BriefDetail | null
  activeBriefId: string | null

  // Pipeline
  pipelineLogs: string[]
  runningStage: string | null

  // Actions
  setSessionId: (id: string) => void
  addChatMessage: (msg: ChatMessage) => void
  setChatMessages: (msgs: ChatMessage[]) => void
  setStreamingText: (text: string) => void
  appendStreamingText: (chunk: string) => void
  setInterviewDone: (done: boolean, briefDict?: Record<string, any> | null) => void
  resetInterview: () => void
  setActiveBrief: (brief: BriefDetail | null) => void
  setActiveBriefId: (id: string | null) => void
  addLog: (line: string) => void
  clearLogs: () => void
  setRunningStage: (stage: string | null) => void
}

export const useAppStore = create<AppState>((set) => ({
  sessionId: crypto.randomUUID().slice(0, 12),
  chatMessages: [],
  interviewDone: false,
  briefDict: null,
  streamingText: '',

  activeBrief: null,
  activeBriefId: null,

  pipelineLogs: [],
  runningStage: null,

  setSessionId: (id) => set({ sessionId: id }),
  addChatMessage: (msg) => set((s) => ({ chatMessages: [...s.chatMessages, msg] })),
  setChatMessages: (msgs) => set({ chatMessages: msgs }),
  setStreamingText: (text) => set({ streamingText: text }),
  appendStreamingText: (chunk) => set((s) => ({ streamingText: s.streamingText + chunk })),
  setInterviewDone: (done, briefDict) => set({ interviewDone: done, briefDict: briefDict ?? null }),
  resetInterview: () =>
    set({
      sessionId: crypto.randomUUID().slice(0, 12),
      chatMessages: [],
      interviewDone: false,
      briefDict: null,
      streamingText: '',
    }),
  setActiveBrief: (brief) => set({ activeBrief: brief, activeBriefId: brief?.id ?? null }),
  setActiveBriefId: (id) => set({ activeBriefId: id }),
  addLog: (line) => set((s) => ({ pipelineLogs: [...s.pipelineLogs, line] })),
  clearLogs: () => set({ pipelineLogs: [] }),
  setRunningStage: (stage) => set({ runningStage: stage }),
}))
