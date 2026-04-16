import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { t } from '../i18n/ko'
import { useAppStore } from '../stores/appStore'
import { api } from '../api/client'
import { createWebSocket } from '../api/websocket'
import type { GeoMetrics } from '../types'

const STAGES = [
  { key: 'query', label: '📝 Step 2 — Query Agent', run: t.runQuery },
  { key: 'testing', label: '🤖 Step 3 — Testing Agent', run: t.runTesting },
  { key: 'analysis', label: '📊 Step 4 — Analysis Agent', run: t.runAnalysis },
  { key: 'report', label: '📄 Step 5 — Report Agent', run: t.runReport },
]

export default function PipelinePage() {
  const navigate = useNavigate()
  const {
    activeBrief, pipelineLogs, runningStage,
    addLog, clearLogs, setRunningStage,
  } = useAppStore()

  const [stageStatuses, setStageStatuses] = useState<Record<string, string>>({})
  const [metrics, setMetrics] = useState<GeoMetrics | null>(null)

  const [uploadFile, setUploadFile] = useState<File | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const logEndRef = useRef<HTMLDivElement>(null)

  const briefId = activeBrief?.id

  // Auto-scroll logs
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [pipelineLogs])

  // Load pipeline status
  const loadStatus = useCallback(async () => {
    if (!briefId) return
    try {
      const res = await api.getPipelineStatus(briefId)
      const map: Record<string, string> = {}
      res.stages?.forEach((s: any) => { map[s.stage] = s.status })
      setStageStatuses(map)
    } catch { /* ignore */ }
  }, [briefId])

  useEffect(() => { loadStatus() }, [loadStatus])

  // Connect WebSocket for logs
  useEffect(() => {
    if (!briefId) return
    const ws = createWebSocket(`/api/pipeline/ws/${briefId}`, (data: any) => {
      if (data.type === 'log') addLog(data.line)
      if (data.type === 'stage_complete') {
        setRunningStage(null)
        loadStatus()
      }
    })
    wsRef.current = ws
    return () => { ws.close() }
  }, [briefId])

  // Poll for running stage completion
  useEffect(() => {
    if (!briefId || !runningStage) return
    const interval = setInterval(async () => {
      try {
        const res = await api.getRunningStage(briefId)
        if (!res.running) {
          setRunningStage(null)
          await loadStatus()
          // Try to load result
          try {
            const result = await api.getStageResult(briefId, runningStage)
            if (runningStage === 'analysis' && result.metrics) {
              setMetrics(result.metrics)
            }
          } catch { /* not available */ }
        }
      } catch { /* ignore */ }
    }, 2000)
    return () => clearInterval(interval)
  }, [briefId, runningStage])

  if (!activeBrief) {
    return (
      <div className="p-8 max-w-3xl mx-auto">
        <h1 className="text-2xl font-bold mb-4">▶ {t.pipeline}</h1>
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-6 text-amber-800">
          <p>먼저 <strong>💬 인터뷰</strong> 메뉴에서 브리프를 완성하거나, <strong>📂 데이터</strong> 메뉴에서 기존 브리프를 불러오세요.</p>
          <div className="flex gap-3 mt-4">
            <button onClick={() => navigate('/')} className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm">
              💬 인터뷰 시작하기
            </button>
            <button onClick={() => navigate('/data')} className="px-4 py-2 bg-slate-200 text-slate-700 rounded-lg text-sm">
              📂 데이터에서 불러오기
            </button>
          </div>
        </div>
      </div>
    )
  }

  const runStage = async (stage: string) => {
    if (runningStage) return
    try {
      clearLogs()
      setRunningStage(stage)
      await api.runStage(briefId!, stage)
    } catch (err: any) {
      setRunningStage(null)
      alert(`오류: ${err.message}`)
    }
  }

  const handleUpload = async () => {
    if (!uploadFile || !briefId) return
    try {
      const res = await api.uploadTesting(briefId, uploadFile)
      alert(`✅ 업로드 완료 — ${res.success}/${res.total}건 성공`)
      setUploadFile(null)
      await loadStatus()
    } catch (err: any) {
      alert(`오류: ${err.message}`)
    }
  }

  const canRun = (stage: string) => {
    if (runningStage) return false
    if (stage === 'query') return true
    if (stage === 'testing') return stageStatuses.query === 'complete'
    if (stage === 'analysis') return stageStatuses.testing === 'complete'
    if (stage === 'report') return stageStatuses.analysis === 'complete'
    return false
  }

  const subjectName = activeBrief.brief_dict?.subject?.name

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">▶ {t.pipeline}</h1>
        <div className="text-sm text-slate-500">
          📋 <strong>{subjectName}</strong> — <span className="font-mono text-xs">{briefId}</span>
        </div>
      </div>

      <div className="grid grid-cols-5 gap-6">
        {/* Left: Stages (3 cols) */}
        <div className="col-span-3 space-y-4">
          {STAGES.map(({ key, label, run }) => {
            const status = stageStatuses[key] || 'pending'
            const isRunning = runningStage === key
            const isDone = status === 'complete'
            const isError = status === 'error'

            return (
              <div
                key={key}
                className={`rounded-xl border p-5 ${
                  isDone ? 'bg-green-50 border-green-200' :
                  isRunning ? 'bg-blue-50 border-blue-200' :
                  isError ? 'bg-red-50 border-red-200' :
                  'bg-white border-slate-200'
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <h3 className="font-semibold text-sm">{label}</h3>
                  <span className={`text-xs px-2 py-0.5 rounded-full ${
                    isDone ? 'bg-green-100 text-green-700' :
                    isRunning ? 'bg-blue-100 text-blue-700 animate-pulse' :
                    isError ? 'bg-red-100 text-red-700' :
                    'bg-slate-100 text-slate-500'
                  }`}>
                    {isDone ? t.complete : isRunning ? t.running : isError ? t.error : t.pending}
                  </span>
                </div>

                {!isDone && !isRunning && (
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => runStage(key)}
                      disabled={!canRun(key)}
                      className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 disabled:bg-slate-300 disabled:cursor-not-allowed transition-colors"
                    >
                      ▶ {run}
                    </button>
                    {key === 'testing' && (
                      <div className="flex items-center gap-2 ml-2">
                        <input
                          type="file"
                          accept=".json"
                          onChange={(e) => setUploadFile(e.target.files?.[0] ?? null)}
                          className="text-xs"
                        />
                        {uploadFile && (
                          <button onClick={handleUpload} className="px-3 py-1.5 bg-slate-200 text-sm rounded-lg">
                            📤 업로드
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                )}

                {isRunning && (
                  <div className="flex items-center gap-2 text-sm text-blue-600">
                    <div className="w-4 h-4 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
                    {t.running}
                  </div>
                )}

                {isDone && key === 'query' && (
                  <button onClick={() => runStage(key)} className="text-xs text-blue-600 hover:underline">
                    🔄 {t.rerun}
                  </button>
                )}
              </div>
            )
          })}

          {/* Metrics display */}
          {metrics && (
            <div className="rounded-xl border border-slate-200 bg-white p-5">
              <h3 className="font-semibold text-sm mb-4">📊 GEO 분석 결과</h3>
              <div className="grid grid-cols-4 gap-4 text-center">
                <div className="bg-slate-50 rounded-lg p-3">
                  <div className="text-2xl font-bold text-blue-600">{(metrics.visibility * 100).toFixed(1)}%</div>
                  <div className="text-xs text-slate-500 mt-1">{t.visibility}</div>
                </div>
                <div className="bg-slate-50 rounded-lg p-3">
                  <div className="text-2xl font-bold text-blue-600">{(metrics.sov * 100).toFixed(1)}%</div>
                  <div className="text-xs text-slate-500 mt-1">{t.shareOfVoice}</div>
                </div>
                <div className="bg-slate-50 rounded-lg p-3">
                  <div className="text-2xl font-bold text-blue-600">{metrics.avg_rank ? metrics.avg_rank.toFixed(1) : 'N/A'}</div>
                  <div className="text-xs text-slate-500 mt-1">{t.avgRank}</div>
                </div>
                <div className="bg-slate-50 rounded-lg p-3">
                  <div className="text-2xl font-bold text-blue-600">{metrics.rank_1_count}</div>
                  <div className="text-xs text-slate-500 mt-1">{t.rank1Count}</div>
                </div>
              </div>

              {/* Sentiment */}
              <div className="mt-4 grid grid-cols-2 gap-4">
                <div>
                  <h4 className="text-xs font-medium text-slate-500 mb-2">{t.sentimentDist}</h4>
                  <div className="space-y-1.5">
                    {[
                      { label: t.positive, value: metrics.sentiment_positive, color: 'bg-green-400' },
                      { label: t.negative, value: metrics.sentiment_negative, color: 'bg-red-400' },
                      { label: t.neutral, value: metrics.sentiment_neutral, color: 'bg-slate-400' },
                    ].map(({ label, value, color }) => {
                      const total = metrics.sentiment_positive + metrics.sentiment_negative + metrics.sentiment_neutral
                      const pct = total > 0 ? (value / total) * 100 : 0
                      return (
                        <div key={label} className="flex items-center gap-2 text-xs">
                          <span className="w-12 text-right text-slate-500">{label}</span>
                          <div className="flex-1 bg-slate-100 rounded-full h-4 overflow-hidden">
                            <div className={`h-full ${color} rounded-full`} style={{ width: `${pct}%` }} />
                          </div>
                          <span className="w-8 text-slate-600">{value}</span>
                        </div>
                      )
                    })}
                  </div>
                </div>
                {metrics.competitor_metrics?.length > 0 && (
                  <div>
                    <h4 className="text-xs font-medium text-slate-500 mb-2">{t.competitorMentions}</h4>
                    <table className="w-full text-xs">
                      <tbody>
                        {metrics.competitor_metrics.map((c) => (
                          <tr key={c.name} className="border-b border-slate-100">
                            <td className="py-1">{c.name}</td>
                            <td className="py-1 text-right">{c.mention_count}회</td>
                            <td className="py-1 text-right text-slate-500">{(c.sov * 100).toFixed(1)}%</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Right: Logs (2 cols) */}
        <div className="col-span-2">
          <div className="sticky top-8">
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-semibold text-sm">📋 {t.liveLogs}</h3>
              <button onClick={clearLogs} className="text-xs text-slate-400 hover:text-slate-600">
                🗑️ {t.clearLogs}
              </button>
            </div>
            <div className="bg-slate-900 rounded-xl p-4 h-[calc(100vh-200px)] overflow-y-auto log-viewer text-slate-300">
              {pipelineLogs.length === 0 ? (
                <p className="text-slate-500 text-xs">{t.noLogs}</p>
              ) : (
                pipelineLogs.map((line, i) => (
                  <div key={i} className="whitespace-pre-wrap">{line}</div>
                ))
              )}
              <div ref={logEndRef} />
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
