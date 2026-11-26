// 实验二交接（五类体系）：塑料 / 纸及纸板 / 金属 / 玻璃 / 食物残余，id 与新模型 data.yaml 一致
export const CLASSES = [
  { id: 0, key: 'plastic', zh: '塑料', color: '#3B82C4' },
  { id: 1, key: 'paper_cardboard', zh: '纸及纸板', color: '#B0834F' },
  { id: 2, key: 'metal', zh: '金属', color: '#9B6FD0' },
  { id: 3, key: 'glass', zh: '玻璃', color: '#3BB39A' },
  { id: 4, key: 'food_waste', zh: '食物残余', color: '#5E9E3A' },
]
export const colorOf = (id) => CLASSES[id]?.color ?? '#888'

export const BINS = {
  recyclable: { general: '可回收物', shanghai: '可回收物', color: '#1D5FA8', tip: '清洁干燥后投放' },
  kitchen: { general: '厨余垃圾', shanghai: '湿垃圾', color: '#2F7D3B', tip: '沥干水分，去除包装' },
  hazardous: { general: '有害垃圾', shanghai: '有害垃圾', color: '#C62F2B', tip: '需人工确认后投放' },
  other: { general: '其他垃圾', shanghai: '干垃圾', color: '#4A524E', tip: '无法回收或已被污染' },
}

export const REGIONS = [
  { value: 'general', label: '通用（GB/T 19095）' },
  { value: 'shanghai', label: '上海' },
]

export const BACKEND_LABELS = { tensorrt_fp16: 'TensorRT FP16', pytorch_fp32: 'PyTorch FP32', onnx_fp32: 'ONNX Runtime' }

export const SAMPLE_NAMES = { 'taco_011368': '铝罐堆（挑战集）', 'taco_ea9381dbc1515bddb3': '罐瓶纸混合', 'taco_e688938a3563e96ed6': '街头散落垃圾', 'taco_c523abee7055731f00': '瓶罐纸板' }

export const LATENCY_TARGET_MS = 2000
