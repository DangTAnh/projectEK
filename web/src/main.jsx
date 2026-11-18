import React from 'react'
import { createRoot } from 'react-dom/client'
import Home from './Home.jsx'
import Room from './Room.jsx'
import './index.css'

// Lỗi render phải hiện lên màn hình thay vì để trang trắng im lặng
class Boundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { err: null }
  }

  static getDerivedStateFromError(err) {
    return { err }
  }

  render() {
    if (!this.state.err) return this.props.children
    return (
      <div className="crash">
        <h2>Đã có lỗi hiển thị 😿</h2>
        <pre>{String(this.state.err.stack || this.state.err)}</pre>
        <button onClick={() => location.reload()}>Tải lại</button>
      </div>
    )
  }
}

function App() {
  const params = new URLSearchParams(location.search)
  const code = (params.get('room') || '').toUpperCase()
  return code ? <Room code={code} /> : <Home />
}

createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <Boundary>
      <App />
    </Boundary>
  </React.StrictMode>,
)
