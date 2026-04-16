import { useEffect, useState } from 'react'
import { t } from '../i18n/ko'
import { api } from '../api/client'

export default function PromptEditorPage() {
  const [prompts, setPrompts] = useState<{ name: string; label: string }[]>([])
  const [selected, setSelected] = useState('')
  const [content, setContent] = useState('')
  const [original, setOriginal] = useState('')
  const [, setCharCount] = useState(0)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  useEffect(() => {
    api.listPrompts().then((list) => {
      setPrompts(list)
      if (list.length > 0 && !selected) {
        setSelected(list[0].name)
      }
    })
  }, [])

  useEffect(() => {
    if (!selected) return
    api.getPrompt(selected).then((data) => {
      setContent(data.content)
      setOriginal(data.content)
      setCharCount(data.char_count)
    })
  }, [selected])

  const handleSave = async () => {
    setSaving(true)
    setMessage(null)
    try {
      await api.updatePrompt(selected, content)
      setOriginal(content)
      setCharCount(content.length)
      setMessage({ type: 'success', text: t.saved })
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message })
    } finally {
      setSaving(false)
    }
  }

  const handleReset = async () => {
    if (!confirm(t.resetDefault + '?')) return
    try {
      await api.resetPrompt(selected)
      const data = await api.getPrompt(selected)
      setContent(data.content)
      setOriginal(data.content)
      setCharCount(data.char_count)
      setMessage({ type: 'success', text: t.resetDone })
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message })
    }
  }

  const hasChanges = content !== original
  const diff = Math.abs(content.length - original.length)

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <h1 className="text-2xl font-bold mb-1">🔧 {t.promptEditor}</h1>
      <p className="text-sm text-slate-500 mb-6">변경 후 저장하면 이후 실행부터 즉시 적용됩니다.</p>

      {/* Prompt selector */}
      <div className="flex items-center gap-4 mb-4">
        <label className="text-sm font-medium text-slate-600">{t.editPrompt}:</label>
        <select
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
          className="px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          {prompts.map((p) => (
            <option key={p.name} value={p.name}>{p.label}</option>
          ))}
        </select>
        <span className="text-xs text-slate-400 font-mono">prompts/{selected}.txt — {content.length.toLocaleString()}자</span>
      </div>

      {/* Editor */}
      <textarea
        value={content}
        onChange={(e) => setContent(e.target.value)}
        className="w-full h-[520px] p-4 border border-slate-300 rounded-xl text-sm font-mono leading-relaxed bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
        spellCheck={false}
      />

      {/* Actions */}
      <div className="flex items-center gap-3 mt-4">
        <button
          onClick={handleSave}
          disabled={saving || !hasChanges}
          className="px-5 py-2.5 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:bg-slate-300 disabled:cursor-not-allowed transition-colors"
        >
          💾 {t.save}
        </button>
        <button
          onClick={handleReset}
          className="px-4 py-2.5 bg-slate-100 text-slate-600 text-sm rounded-lg hover:bg-slate-200 transition-colors"
        >
          ↩️ {t.resetDefault}
        </button>

        {hasChanges && (
          <span className="text-xs text-amber-600 bg-amber-50 px-3 py-1.5 rounded-lg">
            ⚠️ {t.unsavedChanges} ({diff}자 차이)
          </span>
        )}

        {message && (
          <span className={`text-xs px-3 py-1.5 rounded-lg ${
            message.type === 'success' ? 'text-green-700 bg-green-50' : 'text-red-700 bg-red-50'
          }`}>
            {message.text}
          </span>
        )}
      </div>
    </div>
  )
}
