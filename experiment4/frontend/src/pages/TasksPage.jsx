import { useCallback, useEffect, useRef, useState } from 'react'
import { Alert, App, Button, InputNumber, Progress, Space, Table, Tag, Upload } from 'antd'
import { DownloadOutlined, UploadOutlined } from '@ant-design/icons'
import { api } from '../api/client.js'
import { BACKEND_LABELS } from '../constants.js'

const DONE = ['SUCCESS', 'FAILURE']
const MODE = { celery: 'Celery + Redis', local: '本地线程池' }

export default function TasksPage({ backend, region }) {
  const { message, notification } = App.useApp()
  const [tasks, setTasks] = useState([])
  const [mode, setMode] = useState(null)
  const [files, setFiles] = useState([])
  const [count, setCount] = useState(32)
  const [submitting, setSubmitting] = useState(false)
  const known = useRef({})

  const poll = useCallback(async () => {
    try {
      const r = await api.listTasks()
      setTasks(r.result.tasks); setMode(r.result.mode)
      r.result.tasks.forEach((t) => {
        const prev = known.current[t.task_id]
        if (prev && !DONE.includes(prev) && DONE.includes(t.state)) {
          if (t.state === 'SUCCESS') notification.success({ title: '任务完成', description: `${t.task_id}：${t.total} 张图片，共检出 ${t.objects} 个目标` })
          else notification.error({ title: '任务失败', description: `${t.task_id}：${t.error}` })
        }
        known.current[t.task_id] = t.state
      })
    } catch { /* 后端离线时由顶部横幅提示 */ }
  }, [notification])

  const running = tasks.some((t) => !DONE.includes(t.state))
  useEffect(() => {
    poll()
    const id = setInterval(poll, running ? 1000 : 5000) // 有任务在跑时每秒轮询
    return () => clearInterval(id)
  }, [poll, running])

  const submit = async (fields) => {
    setSubmitting(true)
    try {
      const r = await api.createTask({ ...fields, backend, region, conf: 0.25 })
      known.current[r.result.task_id] = r.result.state
      message.success(`已提交 ${r.result.task_id}，进入${MODE[r.result.mode]}，可以离开此页`)
      setFiles([]); poll()
    } catch (e) { message.error(e.message) } finally { setSubmitting(false) }
  }

  const download = async (id) => {
    try {
      const r = await api.taskResult(id)
      const url = URL.createObjectURL(new Blob([JSON.stringify(r.result, null, 2)], { type: 'application/json' }))
      const a = Object.assign(document.createElement('a'), { href: url, download: `ecosort_task_${id}.json` })
      a.click(); URL.revokeObjectURL(url)
    } catch (e) { message.error(e.message) }
  }

  const columns = [
    { title: '任务 ID', dataIndex: 'task_id', render: (v) => <b className="num">{v}</b> },
    { title: '内容', dataIndex: 'label', render: (v, t) => <>{v}<div className="hint">{BACKEND_LABELS[t.backend_used || t.backend]}</div></> },
    { title: '执行方', dataIndex: 'mode', responsive: ['md'], render: (v) => <Tag>{MODE[v]}</Tag> },
    { title: '状态', dataIndex: 'state', render: (v) => <span className={`state ${v}`}>{v}</span> },
    { title: '进度', dataIndex: 'progress', width: 180,
      render: (v, t) => <Progress percent={Math.round(v)} size="small" strokeColor={t.state === 'FAILURE' ? '#C62F2B' : '#14201B'}
        status={t.state === 'FAILURE' ? 'exception' : undefined} format={() => `${t.done}/${t.total}`} /> },
    { title: '目标数', dataIndex: 'objects', responsive: ['lg'], render: (v) => <span className="num">{v}</span> },
    { title: '提交时间', dataIndex: 'created_at', responsive: ['md'], render: (v) => <span className="num">{v?.slice(11, 19)}</span> },
    { title: '', key: 'op', render: (_, t) => t.state === 'SUCCESS'
      ? <Button size="small" shape="round" icon={<DownloadOutlined />} onClick={() => download(t.task_id)}>下载结果</Button>
      : t.state === 'FAILURE' ? <span className="hint">{t.error}</span> : null },
  ]

  return (
    <section aria-labelledby="h-tasks">
      <div className="head">
        <div>
          <h1 id="h-tasks">批量照片交给后台处理</h1>
          <p>一次提交多张或高分辨率图片时，任务进入后台队列，页面每秒查询一次进度，完成后可下载结果。</p>
        </div>
      </div>
      {mode && <Alert className="mode-alert" type={mode === 'celery' ? 'success' : 'info'} showIcon
        title={`当前由${MODE[mode]}执行`}
        description={mode === 'celery' ? 'Redis 与 Celery worker 在线，任务在 worker 进程中执行。'
          : '没有检测到 Redis 或 Celery worker，任务在后端进程内执行，接口和状态与 Celery 相同。启动 Redis 和 worker 后自动切换。'} />}
      <div className="panel task-form">
        <div className="tf-block">
          <h3>上传图片</h3>
          <p className="hint">最多 64 张，单张 ≤30 MB</p>
          <Space wrap>
            <Upload multiple accept="image/png,image/jpeg" fileList={files} showUploadList={false}
              beforeUpload={(f, list) => { setFiles((old) => [...old, f].slice(0, 64)); return false }}>
              <Button shape="round" icon={<UploadOutlined />}>选择图片</Button>
            </Upload>
            <Button type="primary" shape="round" disabled={!files.length} loading={submitting}
              onClick={() => submit({ files })}>{files.length ? `提交 ${files.length} 张` : '提交'}</Button>
            {files.length > 0 && <Button type="link" onClick={() => setFiles([])}>清空</Button>}
          </Space>
        </div>
        <div className="tf-block">
          <h3>使用示例图片</h3>
          <p className="hint">从内置示例图片中按顺序取图，快速体验批量处理</p>
          <Space wrap>
            <InputNumber min={1} max={64} value={count} onChange={(v) => setCount(v || 1)} suffix="张" style={{ width: 110 }} />
            <Button className="btn-sig" shape="round" loading={submitting} onClick={() => submit({ source: 'validation', count })}>提交示例图片</Button>
          </Space>
        </div>
      </div>
      <div className="panel tbl-wrap">
        <Table rowKey="task_id" columns={columns} dataSource={tasks} pagination={false} size="middle"
          locale={{ emptyText: '还没有任务。上传图片或提交示例图片试一下。' }} />
      </div>
      <p className="hint" style={{ marginTop: 12 }}>轮询接口：GET /api/v1/tasks/{'{task_id}'}。状态沿用 Celery：PENDING → STARTED → SUCCESS / FAILURE</p>
    </section>
  )
}
