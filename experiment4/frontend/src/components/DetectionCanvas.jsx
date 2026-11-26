import { CLASSES, colorOf } from '../constants.js'

/** 图片 + 检测框。框坐标是 640×640 标准化坐标；图片以 contain 方式居中显示在正方形里，
 *  与实验一的等比缩放 + 居中灰边完全对应，所以框可以直接按百分比叠加。 */
export default function DetectionCanvas({ src, detections = [], hover = -1, onHover, showTags = true, busy = false,
  emphasize = null, children }) {
  return (
    <div className={`view${busy ? ' busy' : ''}`}>
      {src && <img src={src} alt="待检测图片" />}
      <svg className="boxes" viewBox="0 0 640 640" preserveAspectRatio="xMidYMid meet" aria-hidden="true">
        {detections.map((d, i) => {
          const b = d.box
          const dim = (hover >= 0 && hover !== i) || (emphasize !== null && d.class_id !== emphasize)
          return (
            <g key={d.id ?? i} className={`box${hover === i ? ' hl' : ''}${dim ? ' dim' : ''}`}
              onMouseEnter={() => onHover?.(i)} onMouseLeave={() => onHover?.(-1)}>
              <rect x={b.x1} y={b.y1} width={b.x2 - b.x1} height={b.y2 - b.y1} stroke={colorOf(d.class_id)} rx="2" />
            </g>
          )
        })}
      </svg>
      {showTags && detections.map((d, i) => {
        const dim = (hover >= 0 && hover !== i) || (emphasize !== null && d.class_id !== emphasize)
        return (
          <div key={`t${d.id ?? i}`} className={`tag${dim ? ' dim' : ''}`}
            style={{ background: colorOf(d.class_id), left: `${(d.box.x1 / 640) * 100}%`,
              top: `max(22px, ${(d.box.y1 / 640) * 100}%)` }}>
            {CLASSES[d.class_id].zh}<span className="num">{d.confidence.toFixed(2)}</span>
          </div>
        )
      })}
      <div className="scan" />
      {children}
    </div>
  )
}
