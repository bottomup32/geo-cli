const BASE = '/api'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) {
    const body = await res.text()
    throw new Error(`${res.status}: ${body}`)
  }
  return res.json()
}

export const api = {
  // Settings
  getSettings: () => request<any>('/settings'),
  updateSettings: (data: { api_key?: string; model?: string; chatgpt_profile_dir?: string }) =>
    request<any>('/settings', { method: 'PUT', body: JSON.stringify(data) }),
  getSelectors: () => request<Record<string, string>>('/settings/selectors'),
  updateSelectors: (selectors: Record<string, string>) =>
    request<any>('/settings/selectors', { method: 'PUT', body: JSON.stringify({ selectors }) }),

  // Prompts
  listPrompts: () => request<{ name: string; label: string }[]>('/prompts'),
  getPrompt: (name: string) => request<{ name: string; content: string; char_count: number }>(`/prompts/${name}`),
  updatePrompt: (name: string, content: string) =>
    request<any>(`/prompts/${name}`, { method: 'PUT', body: JSON.stringify({ content }) }),
  resetPrompt: (name: string) => request<any>(`/prompts/${name}/reset`, { method: 'POST' }),

  // Interview
  getInterviewState: (sessionId: string) => request<any>(`/interview/state/${sessionId}`),
  approveBrief: (data: { brief_dict: any; query_count: number }) =>
    request<any>('/interview/approve', { method: 'POST', body: JSON.stringify(data) }),
  restartInterview: (sessionId: string) =>
    request<any>(`/interview/restart/${sessionId}`, { method: 'POST' }),

  // Briefs
  listBriefs: () => request<any[]>('/briefs'),
  getBrief: (id: string) => request<any>(`/briefs/${id}`),
  deleteBrief: (id: string) => request<any>(`/briefs/${id}`, { method: 'DELETE' }),
  listArtifacts: (id: string) => request<any[]>(`/briefs/${id}/artifacts`),
  getArtifactUrl: (id: string, filename: string) => `${BASE}/briefs/${id}/artifacts/${filename}`,
  getArtifactDownloadUrl: (id: string, filename: string) =>
    `${BASE}/briefs/${id}/artifacts/${filename}?download=1`,
  getArtifactsZipUrl: (id: string) => `${BASE}/briefs/${id}/artifacts.zip`,

  // Pipeline
  runStage: (briefId: string, stage: string) =>
    request<any>(`/pipeline/run/${briefId}/${stage}`, { method: 'POST' }),
  getPipelineStatus: (briefId: string) => request<any>(`/pipeline/status/${briefId}`),
  getRunningStage: (briefId: string) => request<any>(`/pipeline/running/${briefId}`),
  getStageResult: (briefId: string, stage: string) => request<any>(`/pipeline/result/${briefId}/${stage}`),
  uploadTesting: async (briefId: string, file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    const res = await fetch(`${BASE}/pipeline/upload-testing/${briefId}`, {
      method: 'POST',
      body: formData,
    })
    if (!res.ok) throw new Error(await res.text())
    return res.json()
  },
}
