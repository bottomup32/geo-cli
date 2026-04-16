import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { t } from '../i18n/ko'
import { useAppStore } from '../stores/appStore'
import { api } from '../api/client'
import type { BriefSummary, ArtifactInfo } from '../types'

const STAGE_KEYS = ['brief', 'queries', 'testing', 'analysis', 'report']

export default function DataPage() {
  const navigate = useNavigate()
  const { setActiveBrief } = useAppStore()
  const [briefs, setBriefs] = useState<BriefSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [expanded, setExpanded] = useState<string | null>(null)
  const [artifacts, setArtifacts] = useState<Record<string, ArtifactInfo[]>>({})
  const [preview, setPreview] = useState<{ filename: string; content: string } | null>(null)

  useEffect(() => {
    loadBriefs()
  }, [])

  const loadBriefs = async () => {
    try {
      const data = await api.listBriefs()
      setBriefs(data)
    } catch (err: any) {
      console.error('Failed to load briefs:', err)
    } finally {
      setLoading(false)
    }
  }

  const toggleExpand = async (id: string) => {
    if (expanded === id) {
      setExpanded(null)
      return
    }
    setExpanded(id)
    if (!artifacts[id]) {
      try {
        const arts = await api.listArtifacts(id)
        setArtifacts((prev) => ({ ...prev, [id]: arts }))
      } catch { /* ignore */ }
    }
  }

  const handleResume = async (id: string) => {
    try {
      const detail = await api.getBrief(id)
      setActiveBrief(detail)
      navigate('/pipeline')
    } catch (err: any) {
      alert(`오류: ${err.message}`)
    }
  }

  const handleDelete = async (id: string) => {
    if (!confirm(`정말 삭제하시겠습니까? (${id})`)) return
    try {
      await api.deleteBrief(id)
      setBriefs((prev) => prev.filter((b) => b.id !== id))
    } catch (err: any) {
      alert(`삭제 오류: ${err.message}`)
    }
  }

  const handlePreview = async (briefId: string, filename: string) => {
    try {
      const url = api.getArtifactUrl(briefId, filename)
      const res = await fetch(url)
      const text = await res.text()
      setPreview({ filename, content: text })
    } catch { /* ignore */ }
  }

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center">
        <div className="text-slate-400">{t.loading}</div>
      </div>
    )
  }

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <h1 className="text-2xl font-bold mb-2">📂 {t.savedData}</h1>
      {briefs.length > 0 && (
        <p className="text-sm text-slate-500 mb-6">
          {t.totalAnalyses.replace('{count}', String(briefs.length))}
        </p>
      )}

      {briefs.length === 0 ? (
        <div className="bg-slate-50 border border-slate-200 rounded-xl p-8 text-center text-slate-400">
          {t.noData}
        </div>
      ) : (
        <div className="space-y-3">
          {briefs.map((brief) => {
            const doneCount = STAGE_KEYS.filter((k) => brief.pipeline_stages[k] === 'complete').length
            const isOpen = expanded === brief.id

            return (
              <div key={brief.id} className="border border-slate-200 rounded-xl bg-white overflow-hidden">
                {/* Header */}
                <div
                  className="flex items-center gap-4 px-5 py-4 cursor-pointer hover:bg-slate-50 transition-colors"
                  onClick={() => toggleExpand(brief.id)}
                >
                  <span className="text-lg">{isOpen ? '▼' : '▶'}</span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <h3 className="font-medium text-sm truncate">{brief.subject_name}</h3>
                      <span className="text-xs text-slate-400">({doneCount}/{STAGE_KEYS.length})</span>
                    </div>
                    <p className="text-xs text-slate-400 font-mono mt-0.5">{brief.id}</p>
                  </div>
                  {/* Stage badges */}
                  <div className="flex gap-1">
                    {STAGE_KEYS.map((k) => (
                      <span
                        key={k}
                        className={`w-2 h-2 rounded-full ${
                          brief.pipeline_stages[k] === 'complete' ? 'bg-green-400' : 'bg-slate-200'
                        }`}
                        title={`${t.stages[k]}: ${brief.pipeline_stages[k] || 'pending'}`}
                      />
                    ))}
                  </div>
                </div>

                {/* Expanded content */}
                {isOpen && (
                  <div className="border-t border-slate-100 px-5 py-4">
                    {/* Stage status */}
                    <div className="flex gap-3 mb-4">
                      {STAGE_KEYS.map((k) => (
                        <span
                          key={k}
                          className={`text-xs px-2 py-1 rounded ${
                            brief.pipeline_stages[k] === 'complete'
                              ? 'bg-green-100 text-green-700'
                              : 'bg-slate-100 text-slate-400'
                          }`}
                        >
                          {brief.pipeline_stages[k] === 'complete' ? '✅' : '⬜'} {t.stages[k]}
                        </span>
                      ))}
                    </div>

                    {/* Actions */}
                    <div className="flex gap-2 mb-4">
                      <button
                        onClick={() => handleResume(brief.id)}
                        className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700"
                      >
                        📂 {t.resumeWork}
                      </button>
                      <button
                        onClick={() => handleDelete(brief.id)}
                        className="px-4 py-2 bg-red-50 text-red-600 text-sm rounded-lg hover:bg-red-100"
                      >
                        🗑️ {t.deleteBrief}
                      </button>
                    </div>

                    {/* Artifacts */}
                    <h4 className="text-xs font-medium text-slate-500 uppercase mb-2">{t.artifacts}</h4>
                    {(!artifacts[brief.id] || artifacts[brief.id].length === 0) ? (
                      <p className="text-xs text-slate-400">{t.noArtifacts}</p>
                    ) : (
                      <div className="space-y-1.5">
                        {artifacts[brief.id].map((art) => (
                          <div key={art.filename} className="flex items-center gap-3 text-xs">
                            <span className="flex-1 truncate font-mono">{art.filename}</span>
                            <span className="text-slate-400">{(art.size / 1024).toFixed(1)} KB</span>
                            <button
                              onClick={(e) => { e.stopPropagation(); handlePreview(brief.id, art.filename) }}
                              className="px-2 py-1 bg-slate-100 rounded hover:bg-slate-200"
                            >
                              👁 {t.preview}
                            </button>
                            <a
                              href={api.getArtifactUrl(brief.id, art.filename)}
                              download={art.filename}
                              className="px-2 py-1 bg-slate-100 rounded hover:bg-slate-200"
                              onClick={(e) => e.stopPropagation()}
                            >
                              ⬇️
                            </a>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}

      {/* Preview modal */}
      {preview && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-8" onClick={() => setPreview(null)}>
          <div className="bg-white rounded-xl max-w-4xl w-full max-h-[80vh] overflow-auto p-6" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-mono text-sm">{preview.filename}</h3>
              <button onClick={() => setPreview(null)} className="text-slate-400 hover:text-slate-600">✕</button>
            </div>
            <pre className="text-xs bg-slate-50 p-4 rounded-lg overflow-auto max-h-[60vh] whitespace-pre-wrap">
              {preview.content}
            </pre>
          </div>
        </div>
      )}
    </div>
  )
}
