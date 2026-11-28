import React, { useEffect } from 'react'
import { createRoot } from 'react-dom/client'
import Home from './Home.jsx'
import Room from './Room.jsx'
import DebugStudio from './DebugStudio.jsx'
import './index.css'
import './components/TableUx.css'

// Lỗi render phải hiện lên màn hình thay vì để trang trắng im lặng
class Boundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { err: null }
  }

  static getDerivedStateFromError(err) {
    return { err }
  }

  componentDidCatch(err, info) {
    console.error('[Exploding Kitty] Render error:', err, info?.componentStack)
  }

  render() {
    if (!this.state.err) return this.props.children
    return (
      <div className="crash" role="alert">
        <h2>Đã có lỗi hiển thị 😿</h2>
        <pre>{String(this.state.err.stack || this.state.err)}</pre>
        <div className="crash-actions">
          <button className="primary" onClick={() => location.reload()}>Tải lại</button>
          <button onClick={() => { location.href = '/' }}>Về trang chủ</button>
        </div>
      </div>
    )
  }
}

const CONTEXT_ALLOW_SELECTOR = 'input, textarea, select, [contenteditable="true"], [data-allow-context="true"]'

function App() {
  useEffect(() => {
    function handleContextMenu(e) {
      const el = e.target instanceof Element ? e.target : e.target?.parentElement
      if (el?.closest(CONTEXT_ALLOW_SELECTOR) || el?.isContentEditable) return
      e.preventDefault()
    }
    document.addEventListener('contextmenu', handleContextMenu)
    return () => document.removeEventListener('contextmenu', handleContextMenu)
  }, [])

  const params = new URLSearchParams(location.search)
  const code = (params.get('room') || '').trim().toUpperCase()
  const isDebug = location.pathname === '/debug' || params.get('debug') === '1'
  if (isDebug) return <DebugStudio initialCode={code} />
  return code ? <Room code={code} /> : <Home />
}

createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <Boundary>
      <App />
    </Boundary>
  </React.StrictMode>,
)
