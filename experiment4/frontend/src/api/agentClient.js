import axios from 'axios'
import { ApiError } from './client.js'

// 实验5：Agent 服务（8001）。开发时经 Vite 代理 /agent-api → localhost:8001，浏览器只访问 5173。
const http = axios.create({ baseURL: '/agent-api/api/v1/agent', timeout: 120000 })

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
    if (err.code === 'ECONNABORTED') throw new ApiError('助手思考超时，请稍后重试', 408)
    if (!err.response) throw new ApiError('无法连接助手服务（8001），请先启动 agent_api', 0)
    throw new ApiError(`助手服务错误（${err.response.status}），请稍后重试`, err.response.status)
  },
)

export const agentHealth = () => http.get('/health', { timeout: 5000 })

// file 存在时走 multipart（图片上传），否则走 JSON
export const agentChatMessage = (message, history = [], file = null) => {
  if (!file) return http.post('/chat', { message, history })
  const fd = new FormData()
  fd.append('message', message)
  fd.append('history', JSON.stringify(history))
  fd.append('file', file)
  return http.post('/chat', fd)
}

// 文本问答页的 AI 解读：把系统判定结果交给 DeepSeek 生成口语化说明
export const agentExplain = (payload) => http.post('/explain', payload)

// 语义归一化：口语/品牌描述 → 系统词表可匹配的物品名词（如 农夫山泉 → 塑料矿泉水瓶）
export const agentInterpret = (text) => http.post('/interpret', { text }, { timeout: 30000 })
