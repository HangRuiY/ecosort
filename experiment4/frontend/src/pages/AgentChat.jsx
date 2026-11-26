import { useEffect, useRef, useState } from 'react'
import { App, Button, Input, Tag, Upload } from 'antd'
import { PictureOutlined } from '@ant-design/icons'
import { agentChatMessage, agentHealth } from '../api/agentClient.js'
import { BINS, colorOf, SAMPLE_NAMES } from '../constants.js'
import DetectionCanvas from '../components/DetectionCanvas.jsx'
import { sampleUrl } from '../api/client.js'

const EXAMPLES = [
  '沾了油的外卖塑料餐盒应该扔哪个垃圾桶？',
  '帮我看看这张图里有什么垃圾，点图片按钮上传试试',
  '碎玻璃和旧报纸能放一起吗？',
]
const MAX_IMAGE_MB = 10

// 轻量加粗渲染：把 **x** 转成 <strong>，其余按原样保留换行
function renderRich(text) {
  const parts = String(text).split('**')
  return parts.map((seg, i) => (i % 2 === 1 ? <strong key={i}>{seg}</strong> : seg))
}

const pct = (v) => `${Math.round((Number(v) || 0) * 100)}%`

// 结构化结果卡片：detect = 画框图 + 多目标列表；classify = 单条结论
function ResultCard({ results, image }) {
  if (!Array.isArray(results)) return null
  const det = results.find((r) => r && r.ok && Array.isArray(r.detections))
  const txt = results.find((r) => r && r.ok && r.recognized && 'bin_key' in r)
  if (det) {
    // 画框图来源：上传图用本地预览 URL；路径查询命中实验4示例集则用后端样例图
    const imgSrc = image || (det.source && SAMPLE_NAMES[det.source] !== undefined ? sampleUrl(det.source) : null)
    return (
      <div className="det-card">
        <div className="det-head">
          共 <b>{det.count}</b> 个目标
          {det.backend && <span className="det-sub"> · {det.backend}</span>}
          {det.total_ms != null && <span className="det-sub"> · {det.total_ms} ms</span>}
          {det.truncated && <span className="det-sub"> · 仅展示前 {det.detections.length} 个</span>}
        </div>
        {imgSrc && (
          <div className="chat-canvas">
            <DetectionCanvas src={imgSrc} detections={det.detections} />
          </div>
        )}
        {det.detections.map((d, i) => (
          <div key={i} className="det-row">
            <span className="det-dot" style={{ background: colorOf(d.class_id) }} />
            <span className="det-name">{d.name_zh}</span>
            <span className="det-bar"><span style={{ width: pct(d.confidence), background: colorOf(d.class_id) }} /></span>
            <span className="det-conf">{pct(d.confidence)}</span>
            <Tag className="det-bin" color={BINS[d.bin_key]?.color}>
              {d.bin_zh}{d.needs_review ? ' · 待核查' : ''}
            </Tag>
          </div>
        ))}
      </div>
    )
  }
  if (txt) {
    return (
      <div className="det-card">
        <div className="det-row det-single">
          <span className="det-dot" style={{ background: colorOf(txt.class_id) }} />
          <span className="det-name">{txt.name_zh}</span>
          {txt.prob != null && <span className="det-conf">{pct(txt.prob)}</span>}
          <Tag className="det-bin" color={BINS[txt.bin_key]?.color}>
            {txt.bin_zh}{txt.needs_review ? ' · 待核查' : ''}
          </Tag>
        </div>
        {txt.reason && <div className="det-note">{txt.reason}</div>}
        {txt.contaminated && <div className="det-note">描述中提到污染，可回收材质已按其他垃圾处理。</div>}
        {txt.evidence?.length > 0 && <div className="det-note">知识库依据：{txt.evidence.join('、')}</div>}
      </div>
    )
  }
  return null
}

// 聊天历史：浏览器 localStorage 级持久化（刷新/重开浏览器保留；清空对话即清除）
const HISTORY_KEY = 'ecosort.agentChat.history'
const HISTORY_MAX = 100

function loadHistory() {
  try {
    const saved = JSON.parse(localStorage.getItem(HISTORY_KEY))
    return Array.isArray(saved) ? saved.filter((m) => m?.role && m?.content) : []
  } catch { return [] }
}
function saveHistory(msgs) {
  try {
    // 图片是 blob URL，刷新后失效，只持久化文本与结构化结果
    const slim = msgs.slice(-HISTORY_MAX).map(({ image, ...rest }) => rest)
    localStorage.setItem(HISTORY_KEY, JSON.stringify(slim))
  } catch { /* 隐私模式/容量满时忽略 */ }
}

export default function AgentChat() {
  const { message } = App.useApp()
  const [msgs, setMsgs] = useState(loadHistory)   // {role, content, toolCalls?, toolResults?, latencyMs?, image?, error?}
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [pending, setPending] = useState(null) // {file, url, name}
  const [upstream, setUpstream] = useState(null) // null=检测中, true/false
  const boxRef = useRef(null)

  useEffect(() => { saveHistory(msgs) }, [msgs])

  useEffect(() => {
    let timer
    const check = async () => {
      try {
        const d = await agentHealth()
        if (d.result?.upstream_backend === 'ok') { setUpstream(true); clearInterval(timer); return }
        setUpstream(false)
      } catch { setUpstream(false) }
    }
    check()
    timer = setInterval(check, 5000) // 离线时每 5 秒重试，在线后停止
    return () => clearInterval(timer)
  }, [])
  useEffect(() => {
    boxRef.current?.scrollTo({ top: boxRef.current.scrollHeight, behavior: 'smooth' })
  }, [msgs, loading, pending])

  const pickFile = (file) => {
    if (!/image\/(jpeg|png)/.test(file.type)) { message.error('仅支持 JPG/PNG 图片'); return false }
    if (file.size > MAX_IMAGE_MB * 1024 * 1024) {
      message.error(`图片 ${(file.size / 1048576).toFixed(1)} MB，超过 ${MAX_IMAGE_MB} MB 上限`); return false
    }
    setPending({ file, url: URL.createObjectURL(file), name: file.name })
    return false // 阻止 antd 自动上传，改由发送时随消息一起提交
  }
  const clearPending = () => setPending(null) // URL 保留给消息气泡引用，不立刻回收

  const send = async (raw) => {
    const text = (raw ?? input).trim()
    if (!text && !pending) { message.error('请输入问题或上传图片'); return }
    if (loading) return
    const file = pending?.file
    const imageUrl = pending?.url
    setInput('')
    clearPending()
    const history = msgs.map(({ role, content }) => ({ role, content }))
    setMsgs((m) => [...m, { role: 'user', content: text || '（上传了一张图片）', image: imageUrl }])
    setLoading(true)
    try {
      const r = await agentChatMessage(text || '请识别这张图片里的垃圾', history, file)
      const { reply, tool_calls: toolCalls, tool_results: toolResults, latency_ms: latencyMs } = r.result
      setMsgs((m) => [...m, { role: 'assistant', content: reply, toolCalls, toolResults, latencyMs, image: imageUrl }])
    } catch (e) {
      setMsgs((m) => [...m, { role: 'assistant', content: e.message, error: true }])
    } finally { setLoading(false) }
  }

  return (
    <section aria-labelledby="h-agent" className="page-agent">
      <div className="head">
        <div>
          <h1 id="h-agent">和分类助手聊一聊</h1>
          <p>直接提问或上传照片，助手会自动选择图像检测或文本问答工具，结合上下文给出投放建议。</p>
        </div>
        <div className="agent-status">
          {upstream === null && <Tag>检查服务中…</Tag>}
          {upstream === true && <Tag color="success">助手在线</Tag>}
          {upstream === false && <Tag color="error">助手离线（需启动 8001 服务与 8000 后端）</Tag>}
        </div>
      </div>

      <div className="panel chat-panel">
        <div className="chat-box" ref={boxRef} aria-live="polite">
          {msgs.length === 0 && !pending && (
            <div className="chat-empty">
              <p>试试下面的问题，或点 📷 上传一张照片：</p>
              <div className="chips">
                {EXAMPLES.map((q) => <button key={q} className="chip" onClick={() => send(q)}>{q}</button>)}
              </div>
            </div>
          )}
          {msgs.map((m, i) => (
            <div key={i} className={`chat-msg ${m.role} ${m.error ? 'is-error' : ''}`}>
              <div className="chat-bubble">
                {m.role === 'user' && m.image && <img className="chat-img" src={m.image} alt="上传的图片" />}
                {m.role === 'assistant' && m.toolCalls?.length > 0 && (
                  <details className="chat-trace">
                    <summary>思考过程（{m.toolCalls.filter((t) => !t.startsWith('  ↳')).length} 次工具调用）</summary>
                    {m.toolCalls.map((t, j) => <div key={j} className="trace-line">{t}</div>)}
                  </details>
                )}
                {m.role === 'assistant' && <ResultCard results={m.toolResults} image={m.image} />}
                <div className="chat-text">{renderRich(m.content)}</div>
                {m.role === 'assistant' && m.latencyMs != null && !m.error && (
                  <div className="chat-meta">耗时 {m.latencyMs} ms</div>
                )}
              </div>
            </div>
          ))}
          {loading && <div className="chat-msg assistant"><div className="chat-bubble chat-typing">正在思考，可能需要调用检测或问答工具…</div></div>}
        </div>

        {pending && (
          <div className="chat-attach">
            <img src={pending.url} alt="待发送图片" />
            <span className="attach-name">{pending.name}</span>
            <button className="attach-del" onClick={clearPending} aria-label="移除图片">✕</button>
          </div>
        )}

        <div className="chat-input">
          <Input.TextArea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="输入问题，或点右侧 📷 上传图片"
            autoSize={{ minRows: 1, maxRows: 4 }}
            onPressEnter={(e) => { if (!e.shiftKey) { e.preventDefault(); send() } }}
            maxLength={1000}
          />
          <Upload
            accept=".jpg,.jpeg,.png,image/jpeg,image/png"
            showUploadList={false}
            beforeUpload={pickFile}
            disabled={loading}
          >
            <Button shape="round" icon={<PictureOutlined />} title="上传图片（JPG/PNG，≤10MB）" disabled={loading}>
              图片
            </Button>
          </Upload>
          <Button type="primary" shape="round" loading={loading} onClick={() => send()}>发送</Button>
          {msgs.length > 0 && (
            <Button shape="round" onClick={() => setMsgs([])} disabled={loading}>清空对话</Button>
          )}
        </div>
      </div>
    </section>
  )
}
