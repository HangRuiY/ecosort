import axios from 'axios'

// 统一返回格式 {code, result, msg}；非 200 一律转成 ApiError，页面只需展示 err.message
export const API_BASE = (import.meta.env.VITE_API_BASE || '/api/v1').replace(/\/$/, '')
export const API_ORIGIN = API_BASE.startsWith('http') ? new URL(API_BASE).origin : ''

export class ApiError extends Error {
  constructor(message, code, result) {
    super(message)
    this.code = code
    this.result = result
  }
}

const http = axios.create({ baseURL: API_BASE, timeout: 60000 })

http.interceptors.response.use(
  (res) => {
    const body = res.data
    if (body && typeof body === 'object' && 'code' in body && 'msg' in body) {
      if (body.code !== 200) throw new ApiError(body.msg, body.code, body.result)
      return body
    }
    return body
  },
  (err) => {
    const body = err.response?.data
    if (body && typeof body === 'object' && body.msg) throw new ApiError(body.msg, body.code ?? err.response.status, body.result)
    if (err.code === 'ECONNABORTED') throw new ApiError('请求超时：后端可能还在加载模型，请稍后再试', 408)
    if (!err.response) throw new ApiError('无法连接后端服务，请确认已在 8000 端口启动 uvicorn', 0)
    if (err.response.status >= 500) throw new ApiError(`服务器错误（${err.response.status}），请查看后端日志`, err.response.status)
    throw new ApiError(`请求失败（${err.response.status}）`, err.response.status)
  },
)

const form = (obj) => {
  const fd = new FormData()
  Object.entries(obj).forEach(([k, v]) => {
    if (v === undefined || v === null) return
    if (Array.isArray(v)) v.forEach((x) => fd.append(k, x))
    else fd.append(k, v)
  })
  return fd
}

export const sampleUrl = (id) => `${API_BASE}/samples/${id}.png`

export const api = {
  health: () => http.get('/health', { timeout: 4000 }),
  samples: () => http.get('/samples'),
  sampleFile: async (id) => {
    const blob = await http.get(`/samples/${id}.png`, { responseType: 'blob' })
    return new File([blob], `${id}.png`, { type: 'image/png' })
  },
  detect: (file, { conf, backend, region }) => http.post('/detect', form({ file, conf, backend, region })),
  text: (text, region) => http.post('/text', { text, region }),
  match: (file, text, { conf, backend, region }) => http.post('/match', form({ file, text, conf, backend, region })),
  createTask: (fields) => http.post('/tasks', form(fields)),
  listTasks: () => http.get('/tasks'),
  task: (id) => http.get(`/tasks/${id}`),
  taskResult: (id) => http.get(`/tasks/${id}/result`),
}
