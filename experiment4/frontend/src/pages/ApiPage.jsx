import { Button, Col, Row, Tag } from 'antd'
import { API_ORIGIN } from '../api/client.js'
import { BACKEND_LABELS } from '../constants.js'

const ENDPOINTS = [
  ['POST', '/api/v1/detect', 'multipart/form-data：file、conf、backend、region。返回每个目标的类别、置信度、框坐标与投放建议。'],
  ['POST', '/api/v1/text', 'application/json：{"text","region"}。返回材质判断、投放建议和知识库依据；本地未覆盖时由 AI 回答。'],
  ['POST', '/api/v1/match', 'multipart：file、text。依赖注入串联检测与文本分类，返回是否一致。'],
  ['POST', '/api/v1/tasks', '上传多张图片，或 source=validation&count=N。返回 task_id。'],
  ['GET', '/api/v1/tasks/{id}', '查询异步任务状态与进度；/result 下载结果。'],
  ['GET', '/api/v1/health', '设备、各推理后端加载情况、知识库与任务队列状态。'],
  ['GET', '/api/v1/classes', '五类材质及默认投放规则。'],
]
const CODES = [
  ['400', '参数错误：文件不是 JPG/PNG、图片损坏、文本为空或超过 300 字、置信度超出范围'],
  ['403', '设置了 ECOSORT_API_KEY 但请求未带正确的 X-API-Key'],
  ['404', '接口路径或任务 ID 不存在'],
  ['413', '单张图片超过 10 MB，或批量任务超过 64 张'],
  ['500', '模型推理失败或没有可用模型'],
  ['503', '强制 Celery 模式下 Redis / worker 不可用'],
]
const BENCH = [
  ['单图模型推理', '18.587 ms', '2.485 ms'],
  ['单图完整流程', '24.074 ms', '8.406 ms'],
  ['Batch 32 流程', '176.871 ms', '175.202 ms'],
  ['测试集 mAP50-95', '17.528%', '17.516%'],
]

export default function ApiPage({ health, refresh }) {
  return (
    <section aria-labelledby="h-api">
      <div className="head">
        <div>
          <h1 id="h-api">接口与模型</h1>
          <p>前后端约定的接口、统一返回格式和错误码，以及当前服务实际加载的模型。</p>
        </div>
        <Button shape="round" href={`${API_ORIGIN}/docs`} target="_blank">打开 Swagger 文档</Button>
      </div>
      <Row gutter={[20, 20]} align="top">
        <Col xs={24} lg={12}>
          <div className="side">
            <div className="panel">
              <div className="panel-h"><h2>当前服务</h2><Button size="small" type="link" onClick={refresh}>刷新</Button></div>
              {!health ? <div className="empty">后端未连接。</div> : (
                <>
                  <div className="kv">
                    <div><span>设备</span><b>{health.device === 'cpu' ? 'CPU' : `GPU ${health.gpu}`}</b></div>
                    <div><span>知识库</span><b>{health.knowledge_base.documents} 条</b></div>
                    <div><span>任务队列</span><b>{health.tasks.mode === 'celery' ? 'Celery + Redis' : '本地线程池'}</b></div>
                    <div><span>图像预处理</span><b>等比缩放 · 边界校正</b></div>
                  </div>
                  <table className="be">
                    <tbody>
                      {health.backends.map((b) => (
                        <tr key={b.name}>
                          <td><b>{BACKEND_LABELS[b.name]}</b><div className="hint path">{b.path.split(/[\\/]/).pop()}</div></td>
                          <td>{b.available ? <Tag color="green">已加载</Tag> : <Tag color="red">不可用</Tag>}</td>
                          <td className="hint">{b.available ? `加载 ${b.load_ms} ms · 预热 ${b.warmup_ms} ms` : b.error}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </>
              )}
            </div>
            <div className="panel">
              <div className="panel-h"><h2>接口</h2><span className="hint">RESTful · 版本 v1</span></div>
              {ENDPOINTS.map(([m, p, d]) => (
                <div className="ep" key={p}><span className={`m ${m.toLowerCase()}`}>{m}</span><code>{p}</code><p>{d}</p></div>
              ))}
            </div>
          </div>
        </Col>
        <Col xs={24} lg={12}>
          <div className="side">
            <div className="panel">
              <div className="panel-h"><h2>统一返回格式</h2></div>
              <pre className="pre-panel">{`{
  "code": 200,
  "result": { "detections": [ … ], "timing_ms": { … } },
  "msg": "ok"
}`}</pre>
            </div>
            <div className="panel">
              <div className="panel-h"><h2>错误码</h2></div>
              <table className="codes"><tbody>{CODES.map(([c, d]) => <tr key={c}><td className="num">{c}</td><td>{d}</td></tr>)}</tbody></table>
            </div>
            <div className="panel">
              <div className="panel-h"><h2>历史性能基准</h2><span className="hint">RTX 4070 SUPER · 640×640</span></div>
              <table className="cmp">
                <thead><tr><th>指标</th><th className="r">PyTorch FP32</th><th className="r">TensorRT FP16</th></tr></thead>
                <tbody>{BENCH.map((r) => <tr key={r[0]}><td>{r[0]}</td><td className="num">{r[1]}</td><td className="num">{r[2]}</td></tr>)}</tbody>
              </table>
              <div className="note">评测基于历史十分类模型与独立测试集（1,053 张图片），用于对比推理优化效果。当前模型以服务加载信息为准。</div>
            </div>
          </div>
        </Col>
      </Row>
    </section>
  )
}
