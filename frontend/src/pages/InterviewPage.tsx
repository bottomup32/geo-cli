import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { t } from '../i18n/ko'
import { useAppStore } from '../stores/appStore'
import { createWebSocket } from '../api/websocket'
import { api } from '../api/client'
import type { InterviewEvent } from '../types'

export default function InterviewPage() {
  const navigate = useNavigate()
  const {
    sessionId, chatMessages, interviewDone, briefDict, streamingText,
    addChatMessage, setChatMessages, setStreamingText, appendStreamingText,
    setInterviewDone, activeBrief, setActiveBrief,
  } = useAppStore()

  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [queryCount, setQueryCount] = useState(75)
  const wsRef = useRef<WebSocket | null>(null)
  const chatEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // Auto-scroll
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [chatMessages, streamingText])

  // Connect WebSocket
  const connectWs = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    const ws = createWebSocket(`/api/interview/ws/${sessionId}`, (data: InterviewEvent) => {
      switch (data.type) {
        case 'history':
          setChatMessages(data.messages)
          if (data.interview_done) {
            setInterviewDone(true, data.brief_dict)
          }
          break
        case 'opening':
          addChatMessage({ role: 'assistant', content: data.content })
          break
        case 'token':
          appendStreamingText(data.content)
          break
        case 'complete':
          addChatMessage({ role: 'assistant', content: data.content })
          setStreamingText('')
          setSending(false)
          break
        case 'interview_complete':
          setInterviewDone(true, data.brief_dict)
          setQueryCount(data.brief_dict?.query_settings?.target_count ?? 75)
          break
        case 'error':
          setStreamingText('')
          setSending(false)
          alert(data.message)
          break
      }
    })
    wsRef.current = ws
  }, [sessionId])

  useEffect(() => {
    connectWs()
    return () => { wsRef.current?.close() }
  }, [connectWs])

  const send = () => {
    const text = input.trim()
    if (!text || sending) return
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      connectWs()
      setTimeout(() => send(), 500)
      return
    }

    addChatMessage({ role: 'user', content: text })
    setInput('')
    setSending(true)
    setStreamingText('')
    wsRef.current.send(JSON.stringify({ type: 'message', content: text }))
  }

  const handleApprove = async () => {
    if (!briefDict) return
    try {
      const res = await api.approveBrief({ brief_dict: briefDict, query_count: queryCount })
      const detail = await api.getBrief(res.brief_id)
      setActiveBrief(detail)
      setInterviewDone(false, null)
      navigate('/pipeline')
    } catch (err: any) {
      alert(`오류: ${err.message}`)
    }
  }

  // If brief already approved, show summary
  if (activeBrief && activeBrief.status === 'approved' && !interviewDone) {
    return (
      <div className="p-8 max-w-3xl mx-auto">
        <h1 className="text-2xl font-bold mb-4">💬 GEO {t.interview}</h1>
        <div className="bg-green-50 border border-green-200 rounded-xl p-6">
          <p className="text-green-800 font-medium">
            ✅ {t.briefComplete}: <strong>{activeBrief.brief_dict?.subject?.name}</strong>
          </p>
          <p className="text-sm text-green-600 font-mono mt-1">{activeBrief.id}</p>
          <button
            onClick={() => navigate('/pipeline')}
            className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            ▶ {t.goToPipeline}
          </button>
        </div>
      </div>
    )
  }

  const subj = briefDict?.subject ?? {}
  const purpose = briefDict?.analysis_purpose ?? {}
  const qs = briefDict?.query_settings ?? {}
  const rs = briefDict?.report_settings ?? {}

  return (
    <div className="flex flex-col h-screen">
      {/* Header */}
      <div className="px-8 py-5 border-b border-slate-200">
        <h1 className="text-2xl font-bold">💬 GEO {t.interview}</h1>
      </div>

      {/* Chat area */}
      <div className="flex-1 overflow-y-auto px-8 py-6 space-y-4">
        {chatMessages.length === 0 && (
          <div className="text-center text-slate-400 py-12">
            <p className="text-lg">{t.chatWelcome}</p>
            <p className="text-sm mt-2 italic">{t.chatExample}</p>
          </div>
        )}

        {chatMessages.map((msg, i) => (
          <div
            key={i}
            className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            {msg.role === 'assistant' && (
              <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center text-sm shrink-0">
                🎯
              </div>
            )}
            <div
              className={`max-w-[70%] rounded-2xl px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap ${
                msg.role === 'user'
                  ? 'bg-blue-600 text-white rounded-br-md'
                  : 'bg-white border border-slate-200 text-slate-800 rounded-bl-md shadow-sm'
              }`}
            >
              {msg.content}
            </div>
            {msg.role === 'user' && (
              <div className="w-8 h-8 rounded-full bg-slate-200 flex items-center justify-center text-sm shrink-0">
                👤
              </div>
            )}
          </div>
        ))}

        {/* Streaming indicator */}
        {streamingText && (
          <div className="flex gap-3 justify-start">
            <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center text-sm shrink-0">
              🎯
            </div>
            <div className="max-w-[70%] rounded-2xl rounded-bl-md px-4 py-3 text-sm leading-relaxed bg-white border border-slate-200 shadow-sm whitespace-pre-wrap">
              {streamingText}
              <span className="animate-pulse">▌</span>
            </div>
          </div>
        )}

        <div ref={chatEndRef} />
      </div>

      {/* Brief confirmation */}
      {interviewDone && briefDict && (
        <div className="border-t border-slate-200 bg-slate-50 px-8 py-6">
          <h2 className="text-lg font-bold mb-4">📋 {t.confirmTitle}</h2>
          <div className="grid grid-cols-2 gap-4 text-sm mb-4">
            <div className="space-y-1.5">
              <p><strong>{t.subject}:</strong> {subj.name} ({subj.type})</p>
              <p><strong>{t.industry}:</strong> {subj.industry} | <strong>{t.market}:</strong> {subj.primary_market}</p>
              {subj.website && <p><strong>{t.website}:</strong> {subj.website}</p>}
              <p><strong>{t.purpose}:</strong> {t.purposeMap[purpose.type] || purpose.type}</p>
            </div>
            <div className="space-y-1.5">
              {briefDict.competitors?.length > 0 && (
                <p><strong>{t.competitors}:</strong> {briefDict.competitors.map((c: any) => c.name).join(', ')}</p>
              )}
              {briefDict.target_platforms?.filter((p: any) => p.enabled).length > 0 && (
                <p><strong>{t.platforms}:</strong> {briefDict.target_platforms.filter((p: any) => p.enabled).map((p: any) => p.name).join(', ')}</p>
              )}
              <div className="flex items-center gap-2">
                <label className="font-medium">{t.queryCount}:</label>
                <input
                  type="number" min={5} max={500} step={5}
                  value={queryCount}
                  onChange={(e) => setQueryCount(Number(e.target.value))}
                  className="w-24 px-2 py-1 border rounded text-sm"
                />
              </div>
              <p className="text-slate-500">
                {t.language}: {qs.query_languages?.map((l: string) => t.langMap[l] || l).join(', ')}
              </p>
              {qs.products?.length > 0 && <p><strong>{t.products}:</strong> {qs.products.join(', ')}</p>}
              {qs.keywords?.length > 0 && <p><strong>{t.keywords}:</strong> {qs.keywords.join(', ')}</p>}
              <p><strong>{t.reportLang}:</strong> {t.audienceMap[rs.audience_level] || ''} / {t.langMap[rs.language] || rs.language}</p>
            </div>
          </div>

          {briefDict.personas?.length > 0 && (
            <div className="mb-4 text-sm">
              <strong>{t.personas} ({briefDict.personas.length}개):</strong>
              <ul className="mt-1 space-y-0.5 text-slate-600">
                {briefDict.personas.map((p: any, i: number) => (
                  <li key={i}>• <strong>{p.name}</strong> [{p.source === 'user_defined' ? '사용자 정의' : 'AI 추론'}]: {p.description}</li>
                ))}
              </ul>
            </div>
          )}

          <div className="flex gap-3">
            <button
              onClick={handleApprove}
              className="flex-1 px-4 py-2.5 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 transition-colors"
            >
              ✅ {t.approve}
            </button>
            <button
              onClick={() => {
                setInterviewDone(false, null)
                setChatMessages([])
              }}
              className="px-4 py-2.5 bg-slate-200 text-slate-700 rounded-lg hover:bg-slate-300 transition-colors"
            >
              🔄 {t.restart}
            </button>
          </div>
        </div>
      )}

      {/* Chat input */}
      {!interviewDone && (
        <div className="border-t border-slate-200 px-8 py-4 bg-white">
          <div className="flex gap-3 max-w-4xl mx-auto">
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && send()}
              placeholder={t.chatPlaceholder}
              disabled={sending}
              className="flex-1 px-4 py-3 border border-slate-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-slate-50"
            />
            <button
              onClick={send}
              disabled={!input.trim() || sending}
              className="px-5 py-3 bg-blue-600 text-white rounded-xl text-sm font-medium hover:bg-blue-700 disabled:bg-slate-300 disabled:cursor-not-allowed transition-colors"
            >
              {sending ? '...' : '전송'}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
