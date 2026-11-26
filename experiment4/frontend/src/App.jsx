import { useEffect, useState } from 'react'
import { Alert } from 'antd'
import { useHealth } from './useHealth.js'
import DetectPage from './pages/DetectPage.jsx'
import TextPage from './pages/TextPage.jsx'
import MatchPage from './pages/MatchPage.jsx'
import TasksPage from './pages/TasksPage.jsx'
import ApiPage from './pages/ApiPage.jsx'
import AgentChat from './pages/AgentChat.jsx'
import { BrandMark, NavIcon } from './components/Icons.jsx'
import { BACKEND_LABELS } from './constants.js'

const PAGES = [
  { key: 'detect', label: '图像检测' },
  { key: 'text', label: '文本问答' },
  { key: 'match', label: '图文匹配' },
  { key: 'tasks', label: '批量任务' },
  { key: 'agent', label: '智能助手' },
  { key: 'api', label: '接口与模型' },
]

const readHash = () => {
  const k = window.location.hash.replace('#/', '')
  return PAGES.some((p) => p.key === k) ? k : 'detect'
}
const load = (k, d) => { try { return localStorage.getItem(k) || d } catch { return d } }
const save = (k, v) => { try { localStorage.setItem(k, v) } catch { /* 隐私模式 */ } }

export default function App() {
  const [page, setPage] = useState(readHash)
  const [region, setRegion] = useState(() => load('ecosort.region', 'general'))
  const [backend, setBackend] = useState(() => load('ecosort.backend', ''))
  const { health, online, refresh } = useHealth()

  useEffect(() => {
    const on = () => setPage(readHash())
    window.addEventListener('hashchange', on)
    return () => window.removeEventListener('hashchange', on)
  }, [])
  useEffect(() => save('ecosort.region', region), [region])
  useEffect(() => { if (backend) save('ecosort.backend', backend) }, [backend])

  // 默认选中后端推荐且可用的推理后端
  const available = health?.available_backends ?? []
  const effectiveBackend = available.includes(backend) ? backend
    : available.includes(health?.default_backend) ? health.default_backend : available[0] || ''

  const go = (k) => { window.location.hash = `#/${k}`; window.scrollTo(0, 0) }
  const shared = { health, online, region, setRegion, backend: effectiveBackend, setBackend, refresh }

  return (
    <div className="app">
      <aside className="rail">
        <div className="brand">
          <BrandMark />
          <div><b>循智 EcoSort</b><span>第 8 组 垃圾检测</span></div>
        </div>
        <nav className="nav" aria-label="主导航">
          {PAGES.map((p) => (
            <button key={p.key} onClick={() => go(p.key)} aria-current={page === p.key ? 'page' : undefined}>
              <NavIcon name={p.key} />{p.label}
            </button>
          ))}
        </nav>
        <div className="rail-foot">
          <div className="conn">
            <span className={`dot ${online === null ? '' : online ? 'on' : 'off'}`} />
            <span>{online === null ? '正在连接后端…' : online ? '后端已连接' : '后端未连接'}</span>
          </div>
          {online && <div>{BACKEND_LABELS[effectiveBackend] || '无可用模型'} · {health.gpu || 'CPU'}</div>}
          <div className="num">/api/v1</div>
        </div>
      </aside>

      <main>
        {online === false && (
          <Alert className="offline" type="warning" showIcon
            title="无法连接后端服务"
            description="请确认服务已经启动。连接恢复后，页面会在 10 秒内自动重连。"
          />
        )}
        {page === 'detect' && <DetectPage {...shared} />}
        {page === 'text' && <TextPage {...shared} />}
        {page === 'match' && <MatchPage {...shared} />}
        {page === 'tasks' && <TasksPage {...shared} />}
        {page === 'agent' && <AgentChat />}
        {page === 'api' && <ApiPage {...shared} />}
      </main>
    </div>
  )
}
