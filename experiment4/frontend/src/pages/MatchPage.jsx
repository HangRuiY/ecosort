import { useEffect, useState } from 'react'
import { App, Button, Col, Input, Row, Steps, Upload } from 'antd'
import { UploadOutlined } from '@ant-design/icons'
import { api } from '../api/client.js'
import { CLASSES, colorOf } from '../constants.js'
import DetectionCanvas from '../components/DetectionCanvas.jsx'
import { Thumbs } from '../components/ResultParts.jsx'
import { useSamples } from '../useSamples.js'
import { validateImage } from './DetectPage.jsx'

const VERDICT = {
  consistent: { cls: 'okc', title: '一致' },
  partial: { cls: 'partc', title: '部分一致' },
  inconsistent: { cls: 'badc', title: '不一致' },
  unknown: { cls: 'idle', title: '无法判断' },
}

const Pill = ({ id, extra }) => <span className="pill"><i style={{ background: colorOf(id) }} />{CLASSES[id].zh}{extra}</span>

export default function MatchPage({ online, backend, region }) {
  const { message } = App.useApp()
  const samples = useSamples(online)
  const [src, setSrc] = useState(null)
  const [text, setText] = useState('两个吃完的金属罐头')
  const [res, setRes] = useState(null)
  const [step, setStep] = useState(-1)

  useEffect(() => { if (!src && samples.length) pickSample(samples[0].id) }, [samples]) // eslint-disable-line

  const pickSample = async (id) => {
    try { const f = await api.sampleFile(id); setSrc({ file: f, url: URL.createObjectURL(f), sampleId: id }); setRes(null) }
    catch (e) { message.error(e.message) }
  }
  const pickFile = (f) => {
    if (!validateImage(f, 10, message)) return
    setSrc({ file: f, url: URL.createObjectURL(f) }); setRes(null)
  }
  const run = async () => {
    if (!src) { message.error('请先选择或上传一张图片'); return }
    if (!text.trim()) { message.error('请填写文字描述，比对需要图片和文字两部分'); return }
    setStep(0); setRes(null)
    try {
      const r = await api.match(src.file, text.trim(), { backend, region, conf: 0.25 })
      setRes(r.result); setStep(3)
    } catch (e) { message.error(e.message); setStep(-1) }
  }

  const v = res ? VERDICT[res.verdict] : null
  const wf = res?.workflow
  const target = res?.text?.top?.class_id ?? null
  return (
    <section aria-labelledby="h-match">
      <div className="head">
        <div>
          <h1 id="h-match">照片和文字说的是同一件东西吗</h1>
          <p>后端先检测图片，再分类文字，最后比对两边的材质类别。可用于核对用户上报的投放记录。</p>
        </div>
      </div>
      <Row gutter={[20, 20]} align="stretch">
        <Col xs={24} lg={9}>
          <div className="panel step-card">
            <h3>图片</h3>
            <DetectionCanvas src={src?.url} detections={res?.image?.detections ?? []} showTags={false}
              busy={step === 0} emphasize={res?.verdict === 'consistent' ? target : null} />
            <div className="samples light">
              <Thumbs samples={samples} selected={src?.sampleId} onPick={pickSample} />
              <Upload accept="image/png,image/jpeg" showUploadList={false} beforeUpload={(f) => { pickFile(f); return false }}>
                <Button shape="round" icon={<UploadOutlined />}>上传</Button>
              </Upload>
            </div>
            <div className="tagrow">{res?.image?.classes?.map((c) => <Pill key={c.class_id} id={c.class_id} extra={<span className="num">×{c.count} {c.confidence.toFixed(2)}</span>} />)}
              {res && !res.image.classes.length && <span className="hint">图片中没有检出目标</span>}</div>
          </div>
        </Col>
        <Col xs={24} lg={8}>
          <div className="panel step-card">
            <h3>文字</h3>
            <Input.TextArea value={text} onChange={(e) => setText(e.target.value)} maxLength={300} showCount
              autoSize={{ minRows: 4, maxRows: 6 }} placeholder="例如：一个塑料饮料瓶" />
            <div className="tagrow">{res?.text?.top && <Pill id={res.text.top.class_id} extra={<span className="num">{res.text.top.prob.toFixed(2)}</span>} />}</div>
          </div>
        </Col>
        <Col xs={24} lg={7}>
          <div className="panel step-card">
            <h3>工作流</h3>
            <Steps orientation="vertical" size="small" current={step < 0 ? -1 : Math.min(step, 2)}
              status={step === 3 ? 'finish' : 'process'}
              items={[
                { title: '图像检测', content: wf ? `/api/v1/detect · ${wf[0].ms.toFixed(0)} ms` : '/api/v1/detect' },
                { title: '文本分类', content: wf ? `/api/v1/text · ${wf[1].ms.toFixed(1)} ms` : '/api/v1/text' },
                { title: '类别比对', content: '文字类别出现在图片检出结果中即为一致' },
              ]} />
            <Button type="primary" shape="round" loading={step === 0} onClick={run}>开始比对</Button>
          </div>
        </Col>
      </Row>
      <div className={`result-big ${v ? v.cls : 'idle'}`} aria-live="polite">
        <div><h3>{v ? v.title : '等待比对'}</h3><p>{res ? res.reason : '选一张图片，写一句描述，然后开始比对。'}</p></div>
        {res && <div className="sc"><b className="num">{res.score.toFixed(2)}</b><div>一致度</div></div>}
      </div>
    </section>
  )
}
