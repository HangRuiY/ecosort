import { useRef, useState } from 'react'
import { App, Button, Col, Input, Row, Select, Tag } from 'antd'
import { api } from '../api/client.js'
import { agentExplain } from '../api/agentClient.js'
import { BINS, CLASSES, colorOf, REGIONS } from '../constants.js'
import { BinIcon } from '../components/Icons.jsx'

const EXAMPLES = ['喝完的易拉罐', '吃剩的果皮', '地上的烟头', '干净的快递纸箱', '碎掉的玻璃杯', '用完的牛奶盒', '用过的纸巾', '废电池', '废电脑', '废手机']
const MAX = 300

export default function TextPage({ region, setRegion }) {
  const { message } = App.useApp()
  const [text, setText] = useState('沾了油的外卖塑料餐盒')
  const [res, setRes] = useState(null)
  const [loading, setLoading] = useState(false)
  const [aiText, setAiText] = useState(null)   // DeepSeek 解读
  const [aiLoading, setAiLoading] = useState(false)
  const activeRequest = useRef(0)

  const ask = async (q = text) => {
    const v = q.trim()
    if (!v) { message.error('请先输入描述，例如“喝完的易拉罐”'); return }
    const requestId = ++activeRequest.current
    setLoading(true)
    setAiText(null)
    setAiLoading(false)
    setRes(null)
    try {
      // 后端先查本地规则，未命中时直接向大模型提问，保留完整原始语义。
      const r = await api.text(v, region)
      if (requestId !== activeRequest.current) return
      setRes(r.result)
      if (r.result.reply) {
        setAiText(r.result.reply)
        return
      }
      // 系统判定完成后，请 DeepSeek 生成一段口语化解读（服务不可用时静默跳过）
      if (r.result.advice) {
        setAiLoading(true)
        agentExplain({
          text: v,
          name_zh: r.result.top?.name_zh || r.result.disposal_item,
          bin_zh: r.result.advice.bin_zh,
          prob: r.result.top?.prob,
          contaminated: !!r.result.contaminated,
          evidence: [r.result.advice.reason, ...(r.result.evidence || []).slice(0, 2).map((e) => e.text?.slice(0, 60))],
        }).then((d) => { if (requestId === activeRequest.current) setAiText(d.result.explain) })
          .catch(() => { if (requestId === activeRequest.current) setAiText(null) })
          .finally(() => { if (requestId === activeRequest.current) setAiLoading(false) })
      }
    } catch (e) { if (requestId === activeRequest.current) message.error(e.message) }
    finally { if (requestId === activeRequest.current) setLoading(false) }
  }

  const top = res?.top
  const bin = res?.advice ? (BINS[res.advice.bin] || { color: '#B0834F' }) : null
  return (
    <section aria-labelledby="h-text">
      <div className="head">
        <div>
          <h1 id="h-text">拿不准的东西，打字问一下</h1>
          <p>描述一件物品或它的状态，系统判断最可能的材质类别和投放去向，并附上回收知识库里的依据。</p>
        </div>
      </div>
      <Row gutter={[20, 20]} align="top">
        <Col xs={24} lg={12}>
          <div className="panel"><div className="panel-b">
            <label htmlFor="q" className="hint">物品描述</label>
            <Input.TextArea id="q" value={text} onChange={(e) => setText(e.target.value)} maxLength={MAX} showCount
              autoSize={{ minRows: 4, maxRows: 8 }} placeholder="例如：喝完的塑料矿泉水瓶，瓶盖还在"
              onPressEnter={(e) => { if (!e.shiftKey) { e.preventDefault(); ask() } }} />
            <div className="chips">
              {EXAMPLES.map((q) => <button key={q} className="chip" onClick={() => { setText(q); ask(q) }}>{q}</button>)}
            </div>
            <div className="row-actions">
              <Button type="primary" shape="round" loading={loading} onClick={() => ask()}>判断类别</Button>
              <Select value={region} onChange={setRegion} options={REGIONS} aria-label="规则地区" style={{ minWidth: 170 }} />
            </div>
          </div></div>
        </Col>
        <Col xs={24} lg={12}>
          <div className="side">
            <div className="panel" aria-live="polite">
              {!res && <div className="empty">{loading ? '正在查询本地规则与 AI 建议…' : '输入描述后点“判断类别”。'}</div>}
              {res && !top && !bin && <div className="empty">{res.fallback_message || (res.reply ? '请参考下方 AI 答复，补充要处理的具体物品。' : '请补充要处理的物品描述。')}</div>}
              {bin && (
                <div className="verdict">
                  <BinIcon color={bin.color} />
                  <div>
                    <h3>{bin[region] || res.advice.bin_zh}</h3>
                    {res.source === 'deepseek' && <Tag color="blue">大模型建议</Tag>}
                    <p>{top ? `材质判断为“${top.name_zh}”。` : `物品识别为“${res.disposal_item}”。`}{res.advice.reason}{res.advice.needs_review ? '（需人工核查）' : ''}</p>
                    {res.matched_keywords.length > 0 && (
                      <div className="kw">命中关键词：{res.matched_keywords.map((k, i) => <Tag key={i} color={colorOf(k.class_id)}>{k.keyword}</Tag>)}</div>
                    )}
                  </div>
                </div>
              )}
              {top && (
                <ul className="rank">
                  {res.ranking.slice(0, 4).map((r) => (
                    <li key={r.class_id}><span>{CLASSES[r.class_id].zh}</span>
                      <span className="bar"><i style={{ width: `${r.prob * 100}%`, background: colorOf(r.class_id) }} /></span>
                      <span className="num">{(r.prob * 100).toFixed(1)}%</span></li>
                  ))}
                </ul>
              )}
            </div>
            <div className="panel">
              <div className="panel-h"><h2>{res?.source === 'deepseek' ? 'AI 问答' : 'AI 解读'}</h2><span className="hint">{res?.source === 'deepseek' ? '本地规则未覆盖 · DeepSeek 直接回答' : '基于系统判定 · DeepSeek 生成'}</span></div>
              {!res && <div className="hint" style={{ padding: '6px 2px' }}>判断后自动生成。</div>}
              {res && aiLoading && <div className="hint" style={{ padding: '6px 2px' }}>AI 解读生成中…</div>}
              {res && !res.advice && !aiText && <div className="hint" style={{ padding: '6px 2px' }}>暂未生成 AI 答复，请稍后重试或补充描述。</div>}
              {res?.advice && !aiLoading && !aiText && <div className="hint" style={{ padding: '6px 2px' }}>AI 解读暂时不可用，可先参考上方投放建议和下方依据。</div>}
              {aiText && <p className="ai-explain">{aiText}</p>}
            </div>
            <div className="panel">
              <div className="panel-h"><h2>投放依据</h2><span className="hint">{res?.source === 'deepseek' ? '回答来源：DeepSeek' : res?.rule_source ? '物品投放规则 · 知识库检索' : '知识库 · 21 条参考资料'}</span></div>
              <ul className="src">
                {res?.rule_source && <li>{res.rule_source.text}<small>物品投放规则 · <a href={res.rule_source.source_url} target="_blank" rel="noreferrer">{res.rule_source.title}</a></small></li>}
                {res?.source === 'deepseek' && <li className="hint">本次建议由大模型生成，本地知识库没有对应条目；具体投放方式请以当地规则或正规回收点要求为准。</li>}
                {res?.source !== 'deepseek' && !res?.rule_source && !res?.evidence?.length && <li className="hint">暂无匹配的条目。</li>}
                {res?.evidence?.map((e) => (
                  <li key={e.id}>{e.text}
                    <small>
                      {e.region && e.region !== '未配置' && e.region !== 'dataset' ? `${e.region} · ` : ''}
                      {e.is_synthetic ? '有来源的改写' : '原文'} · 相似度 {e.score.toFixed(2)}
                      {e.source_url && <> · <a href={e.source_url} target="_blank" rel="noreferrer">查看来源</a></>}
                    </small>
                  </li>
                ))}
              </ul>
            </div>
            <p className="hint">投放建议以所在地规定为准。电池等物品请补充具体类型；暂时无法判断时，可提供标签或图片。</p>
          </div>
        </Col>
      </Row>
    </section>
  )
}
