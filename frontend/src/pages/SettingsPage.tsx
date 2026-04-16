import { useEffect, useState } from 'react'
import { t } from '../i18n/ko'
import { api } from '../api/client'
import type { Settings } from '../types'

const MODELS = ['claude-sonnet-4-6', 'claude-opus-4-6', 'claude-haiku-4-5-20251001']

export default function SettingsPage() {
  const [settings, setSettings] = useState<Settings | null>(null)
  const [apiKey, setApiKey] = useState('')
  const [model, setModel] = useState('')
  const [selectors, setSelectors] = useState<Record<string, string>>({})
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  useEffect(() => {
    api.getSettings().then((data) => {
      setSettings(data)
      setModel(data.model)
      setSelectors(data.selectors)
    })
  }, [])

  const handleSaveApi = async () => {
    setMessage(null)
    try {
      const updates: { api_key?: string; model?: string } = { model }
      if (apiKey) updates.api_key = apiKey
      await api.updateSettings(updates)
      setMessage({ type: 'success', text: '✅ 저장 완료. 앱 재시작 후 적용됩니다.' })
      // Refresh settings
      const data = await api.getSettings()
      setSettings(data)
      setApiKey('')
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message })
    }
  }

  const handleSaveSelectors = async () => {
    setMessage(null)
    try {
      await api.updateSelectors(selectors)
      setMessage({ type: 'success', text: '✅ 셀렉터 저장 완료.' })
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message })
    }
  }

  if (!settings) {
    return <div className="p-8 text-slate-400">{t.loading}</div>
  }

  return (
    <div className="p-8 max-w-3xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">⚙️ {t.settings}</h1>

      {/* API Settings */}
      <section className="bg-white border border-slate-200 rounded-xl p-6 mb-6">
        <h2 className="text-lg font-semibold mb-4">🔑 API 설정</h2>

        <div className="grid grid-cols-2 gap-4 mb-4">
          <div>
            <label className="block text-sm font-medium text-slate-600 mb-1.5">{t.apiKey}</label>
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder={settings.api_key_set ? `현재: ${settings.api_key_preview}` : '키를 입력하세요'}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            {!settings.api_key_set && (
              <p className="text-xs text-red-500 mt-1">⚠️ {t.apiKeyNotSet}</p>
            )}
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-600 mb-1.5">{t.model}</label>
            <select
              value={model}
              onChange={(e) => setModel(e.target.value)}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {MODELS.map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
          </div>
        </div>

        <div className="mb-4">
          <label className="block text-sm font-medium text-slate-600 mb-1.5">{t.dataDir}</label>
          <input
            type="text"
            value={settings.data_dir}
            disabled
            className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm bg-slate-50 text-slate-500"
          />
        </div>

        <button
          onClick={handleSaveApi}
          className="px-5 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors"
        >
          💾 {t.save}
        </button>
      </section>

      {/* DOM Selectors */}
      <section className="bg-white border border-slate-200 rounded-xl p-6 mb-6">
        <h2 className="text-lg font-semibold mb-1">🤖 {t.domSelectors}</h2>
        <p className="text-xs text-slate-500 mb-4">{t.domSelectorsDesc}</p>

        <div className="space-y-3">
          {Object.entries(selectors).map(([label, value]) => (
            <div key={label} className="flex items-center gap-3">
              <label className="w-28 text-sm text-slate-600 shrink-0">{label}</label>
              <input
                type="text"
                value={value}
                onChange={(e) => setSelectors({ ...selectors, [label]: e.target.value })}
                className="flex-1 px-3 py-2 border border-slate-300 rounded-lg text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          ))}
        </div>

        <button
          onClick={handleSaveSelectors}
          className="mt-4 px-5 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors"
        >
          💾 {t.save}
        </button>
      </section>

      {/* Message */}
      {message && (
        <div className={`px-4 py-3 rounded-lg text-sm ${
          message.type === 'success' ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'
        }`}>
          {message.text}
        </div>
      )}
    </div>
  )
}
