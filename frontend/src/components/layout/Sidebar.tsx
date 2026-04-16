import { NavLink, useNavigate } from 'react-router-dom'
import { t } from '../../i18n/ko'
import { useAppStore } from '../../stores/appStore'

const NAV_ITEMS = [
  { to: '/', label: t.interview, icon: '💬' },
  { to: '/pipeline', label: t.pipeline, icon: '▶' },
  { to: '/data', label: t.data, icon: '📂' },
  { to: '/prompts', label: t.promptEditor, icon: '🔧' },
  { to: '/settings', label: t.settings, icon: '⚙️' },
]

const STAGE_KEYS = ['brief', 'queries', 'testing', 'analysis', 'report']

export default function Sidebar() {
  const navigate = useNavigate()
  const activeBrief = useAppStore((s) => s.activeBrief)
  const resetInterview = useAppStore((s) => s.resetInterview)
  const setActiveBrief = useAppStore((s) => s.setActiveBrief)

  const stages = activeBrief?.pipeline_stages ?? {}

  return (
    <aside className="w-60 min-h-screen bg-slate-900 text-slate-300 flex flex-col">
      {/* Logo */}
      <div className="px-5 py-6">
        <h1 className="text-lg font-bold text-white tracking-tight">🎯 {t.appName}</h1>
        <p className="text-xs text-slate-500 mt-1">{t.appVersion}</p>
      </div>

      <div className="h-px bg-slate-700 mx-4" />

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
                isActive
                  ? 'bg-blue-600 text-white font-medium'
                  : 'hover:bg-slate-800 text-slate-400 hover:text-slate-200'
              }`
            }
          >
            <span className="text-base">{item.icon}</span>
            {item.label}
          </NavLink>
        ))}
      </nav>

      <div className="h-px bg-slate-700 mx-4" />

      {/* Pipeline Status */}
      <div className="px-5 py-4">
        <p className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-3">
          {t.pipelineStatus}
        </p>
        <div className="space-y-1.5">
          {STAGE_KEYS.map((key) => {
            const done = stages[key] === 'complete'
            return (
              <div key={key} className="flex items-center gap-2 text-xs">
                <span>{done ? '✅' : '⬜'}</span>
                <span className={done ? 'text-slate-300' : 'text-slate-500'}>
                  {t.stages[key] || key}
                </span>
              </div>
            )
          })}
        </div>

        {activeBrief && (
          <div className="mt-3 text-xs text-slate-500">
            <p>📌 {activeBrief.brief_dict?.subject?.name}</p>
            <p className="font-mono text-[10px] mt-0.5 text-slate-600">{activeBrief.id}</p>
          </div>
        )}
      </div>

      <div className="h-px bg-slate-700 mx-4" />

      {/* New Analysis */}
      <div className="px-4 py-4">
        <button
          onClick={() => {
            resetInterview()
            setActiveBrief(null)
            navigate('/')
          }}
          className="w-full px-3 py-2 text-sm rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors"
        >
          🔄 {t.newAnalysis}
        </button>
      </div>
    </aside>
  )
}
