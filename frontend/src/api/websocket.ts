type MessageHandler = (data: any) => void

export function createWebSocket(path: string, onMessage: MessageHandler): WebSocket {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.host
  const ws = new WebSocket(`${protocol}//${host}${path}`)

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      onMessage(data)
    } catch {
      console.error('Failed to parse WS message:', event.data)
    }
  }

  ws.onerror = (event) => {
    console.error('WebSocket error:', event)
  }

  return ws
}
