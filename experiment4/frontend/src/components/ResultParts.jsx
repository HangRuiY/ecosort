import { Select } from 'antd'
import { BINS, CLASSES, colorOf, REGIONS } from '../constants.js'

export function DetectionList({ detections, hover, onHover, region, emptyText }) {
  if (!detections.length) return <div className="empty">{emptyText}</div>
  return (
    <ul className="det-list">
      {detections.map((d, i) => (
        <li key={d.id ?? i} className={hover === i ? 'hl' : ''} onMouseEnter={() => onHover(i)} onMouseLeave={() => onHover(-1)}>
          <span className="sw" style={{ background: colorOf(d.class_id) }} />
          <span className="nm">{CLASSES[d.class_id].zh}
            <small>{BINS[d.advice.bin][region]}{d.advice.needs_review ? ' · 需核查' : ''}</small></span>
          <span className="cf num">{(d.confidence * 100).toFixed(1)}%</span>
          <span className="bar"><i style={{ width: `${d.confidence * 100}%`, background: colorOf(d.class_id) }} /></span>
        </li>
      ))}
    </ul>
  )
}

export function BinSummary({ detections, region, setRegion }) {
  const counts = { recyclable: 0, kitchen: 0, hazardous: 0, other: 0 }
  let review = 0
  detections.forEach((d) => { counts[d.advice.bin] += 1; review += d.advice.needs_review ? 1 : 0 })
  const reasons = [...new Set(detections.filter((d) => d.advice.needs_review).map((d) => `${CLASSES[d.class_id].zh}：${d.advice.reason}`))]
  return (
    <div className="panel">
      <div className="panel-h">
        <h2>投放建议</h2>
        <Select size="small" value={region} onChange={setRegion} options={REGIONS} popupMatchSelectWidth={false}
          aria-label="规则地区" />
      </div>
      <div className="bins">
        {Object.entries(BINS).map(([k, v]) => (
          <div key={k} className={`bin${counts[k] ? '' : ' zero'}`} style={{ borderTopColor: v.color }}>
            <h3>{v[region]}</h3>
            <div className="ct num">{counts[k]}</div>
            <p>{v.tip}</p>
          </div>
        ))}
      </div>
      {review > 0 && (
        <div className="review"><b>{review} 个目标需要人工核查</b>{reasons.map((r) => <div key={r}>{r}</div>)}</div>
      )}
      <div className="note">模型识别的是材质。沾满油污或食物的包装通常应投其他垃圾，最终以所在城市的规定为准。</div>
    </div>
  )
}

export function JsonPanel({ title, data }) {
  return (
    <div className="panel">
      <details className="json">
        <summary>{title}</summary>
        <pre>{JSON.stringify(data ?? {}, null, 2)}</pre>
      </details>
    </div>
  )
}

export function Thumbs({ samples, selected, onPick, dark = false }) {
  return samples.map((s) => (
    <button key={s.id} className={`thumb${dark ? '' : ' light'}`} aria-pressed={selected === s.id}
      aria-label={`示例 ${s.id}`} onClick={() => onPick(s.id)}>
      <img src={s.src} alt="" />
    </button>
  ))
}
