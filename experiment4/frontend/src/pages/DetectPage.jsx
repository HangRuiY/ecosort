import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { App, Button, Checkbox, Col, Row, Segmented, Slider, Tooltip, Upload } from 'antd'
import { UploadOutlined } from '@ant-design/icons'
import { api } from '../api/client.js'
import { BACKEND_LABELS, LATENCY_TARGET_MS, SAMPLE_NAMES } from '../constants.js'
import DetectionCanvas from '../components/DetectionCanvas.jsx'
import { BinSummary, DetectionList, JsonPanel, Thumbs } from '../components/ResultParts.jsx'
import { useSamples } from '../useSamples.js'

const MAX_MB = 10
const REQUEST_CONF = 0.05 // 一次取回低阈值结果，滑块在前端即时筛选

export function validateImage(file, maxMb, message) {
  if (!/image\/(png|jpe?g)/.test(file.type) && !/\.(png|jpe?g)$/i.test(file.name)) {
    message.error('图像格式错误，请上传 PNG/JPG')
    return false
  }
  if (file.size > maxMb * 1024 * 1024) {
    message.error(`图片 ${(file.size / 1048576).toFixed(1)} MB，超过 ${maxMb} MB 上限；高分辨率图片请到“批量任务”提交`)
    return false
  }
  return true
}

export function BackendSwitch({ health, backend, setBackend, dark }) {
  const list = health?.backends ?? []
  if (!list.length) return null
  return (
    <Segmented className={dark ? 'seg-dark' : ''} value={backend} onChange={setBackend}
      options={list.map((b) => ({
        value: b.name, disabled: !b.available,
        label: b.available ? BACKEND_LABELS[b.name] : <Tooltip title={b.error}><span>{BACKEND_LABELS[b.name]}</span></Tooltip>,
      }))} />
  )
}

export default function DetectPage({ health, online, region, setRegion, backend, setBackend }) {
  const { message } = App.useApp()
  const samples = useSamples(online)
  const [source, setSource] = useState(null) // {file, url, name, sampleId}
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [conf, setConf] = useState(0.40) // 实验二交接后新模型的默认筛选阈值（仍可拖动调整）
  const [showTags, setShowTags] = useState(true)
  const [hover, setHover] = useState(-1)
  const [roundTrip, setRoundTrip] = useState(null)
  const [drag, setDrag] = useState(false)
  const reqId = useRef(0)

  const run = useCallback(async (src) => {
    if (!src) return
    if (!backend) {
      message.error(online === false ? '无法连接后端服务，请确认已在 8000 端口启动 uvicorn' : '后端没有可用的推理模型，请查看“接口与模型”页')
      return
    }
    const id = ++reqId.current
    setBusy(true); setHover(-1)
    const t0 = performance.now()
    try {
      const r = await api.detect(src.file, { conf: REQUEST_CONF, backend, region })
      if (id !== reqId.current) return
      setResult(r.result)
      if (r.msg !== 'ok') message.warning(r.msg)
      requestAnimationFrame(() => {
        const ms = performance.now() - t0
        setRoundTrip(ms)
        if (ms > LATENCY_TARGET_MS) message.warning(`本次从上传到显示用了 ${(ms / 1000).toFixed(1)} 秒，超过 2 秒目标`)
      })
    } catch (e) {
      if (id === reqId.current) { message.error(e.message); setResult(null) }
    } finally {
      if (id === reqId.current) setBusy(false)
    }
  }, [backend, region, message, online])

  const pickSample = async (sampleId) => {
    try {
      const file = await api.sampleFile(sampleId)
      const s = { file, url: URL.createObjectURL(file), name: `示例图片 ${sampleId}.png`, sampleId }
      setSource(s); run(s)
    } catch (e) { message.error(e.message) }
  }
  const pickFile = (file) => {
    if (!validateImage(file, MAX_MB, message)) return
    const s = { file, url: URL.createObjectURL(file), name: file.name }
    setSource(s); run(s)
  }

  // 首次进入自动用第一张示例
  useEffect(() => { if (!source && samples.length && backend) pickSample(samples[0].id) }, [samples, backend]) // eslint-disable-line
  // 切换后端或地区时重跑当前图片
  useEffect(() => { if (source) run(source) }, [backend, region]) // eslint-disable-line

  const dets = useMemo(() => (result?.detections ?? []).filter((d) => d.confidence >= conf), [result, conf])
  const t = result?.timing_ms
  const onDrop = (e) => { e.preventDefault(); setDrag(false); const f = e.dataTransfer.files?.[0]; if (f) pickFile(f) }

  return (
    <section aria-labelledby="h-detect">
      <div className="head">
        <div>
          <h1 id="h-detect">一张照片，逐个认出里面的垃圾</h1>
          <p>上传含多个垃圾的照片，模型框出每个目标并判断材质，再按通用规则给出投放建议。</p>
        </div>
      </div>
      <Row gutter={[20, 20]} align="top">
        <Col xs={24} xl={14}>
          <div className="stage" onDragOver={(e) => { e.preventDefault(); setDrag(true) }}
            onDragLeave={() => setDrag(false)} onDrop={onDrop}>
            <div className="stage-bar">
              <span className="file">{source?.name || '未选择图片'}</span>
              <BackendSwitch health={health} backend={backend} setBackend={setBackend} dark />
            </div>
            <DetectionCanvas src={source?.url} detections={dets} hover={hover} onHover={setHover}
              showTags={showTags} busy={busy}>
              {(!source || drag) && (
                <div className={`drop${drag ? ' on' : ''}`}>
                  <UploadOutlined style={{ fontSize: 36 }} />
                  <strong>把照片拖到这里</strong>
                  <span>支持 JPG / PNG，单张不超过 {MAX_MB} MB</span>
                </div>
              )}
            </DetectionCanvas>
            <div className="samples">
              <span>示例图片</span>
              <Thumbs samples={samples} selected={source?.sampleId} onPick={pickSample} dark />
              <Upload accept="image/png,image/jpeg" showUploadList={false} beforeUpload={(f) => { pickFile(f); return false }}>
                <Button className="btn-sig" shape="round" icon={<UploadOutlined />}>上传照片</Button>
              </Upload>
            </div>
            <div className="ctl">
              <label className="slider">置信度阈值
                <Slider min={0.05} max={0.9} step={0.05} value={conf} onChange={setConf} tooltip={{ open: false }} />
                <output className="num">{conf.toFixed(2)}</output>
              </label>
              <Checkbox checked={showTags} onChange={(e) => setShowTags(e.target.checked)}>显示标签</Checkbox>
            </div>
          </div>
        </Col>

        <Col xs={24} xl={10}>
          <div className="side">
            <div className="panel metrics" aria-live="polite">
              <div><b className="num">{result ? dets.length : '–'}</b><small>检出目标</small></div>
              <div><Tooltip title="模型推理（不含预处理和 NMS）"><b className="num">{t?.model_inference?.toFixed(1) ?? '–'}</b></Tooltip><small>推理 ms</small></div>
              <div><Tooltip title="从上传到结果显示的总耗时，目标不超过 2 秒">
                <b className={`num${roundTrip > LATENCY_TARGET_MS ? ' over' : ''}`}>{roundTrip ? Math.round(roundTrip) : '–'}</b></Tooltip><small>端到端 ms</small></div>
            </div>
            {result && <div className="runinfo">
              {BACKEND_LABELS[result.backend_used]} · {result.device === 'cpu' ? 'CPU' : `GPU ${health?.gpu ?? ''}`} · 原图 {result.image.width}×{result.image.height}
              {source?.sampleId && SAMPLE_NAMES[source.sampleId] ? ` · ${SAMPLE_NAMES[source.sampleId]}` : ''}
            </div>}
            <div className="panel">
              <div className="panel-h"><h2>检测结果</h2><span className="hint">悬停查看对应框</span></div>
              <DetectionList detections={dets} hover={hover} onHover={setHover} region={region}
                emptyText={!result ? '选择示例或上传照片后显示结果。'
                  : result.count ? '当前阈值下没有目标，试着把置信度阈值调低。'
                    : '没有检出垃圾目标。换一张更近、光线更好的照片再试。'} />
            </div>
            <BinSummary detections={dets} region={region} setRegion={setRegion} />
            <JsonPanel title="接口返回 POST /api/v1/detect" data={result && { ...result, detections: dets, filtered_by_conf: conf }} />
          </div>
        </Col>
      </Row>
    </section>
  )
}
