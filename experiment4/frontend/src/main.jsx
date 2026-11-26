import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { App as AntApp, ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import App from './App.jsx'
import './styles.css'

const theme = {
  token: {
    colorPrimary: '#14201B',
    colorInfo: '#1D5FA8',
    colorSuccess: '#2F7D3B',
    colorError: '#C62F2B',
    colorWarning: '#C99400',
    colorBgLayout: '#E4E8E2',
    colorBgContainer: '#F6F7F3',
    colorBorder: '#C5CCC4',
    colorBorderSecondary: '#DCE1DA',
    colorText: '#14201B',
    colorTextSecondary: '#5C6862',
    borderRadius: 10,
    fontFamily: '"Noto Sans SC","PingFang SC","Microsoft YaHei",system-ui,sans-serif',
    fontSize: 15,
  },
  components: {
    Button: { primaryShadow: 'none', defaultShadow: 'none', fontWeight: 700 },
    Segmented: { itemSelectedBg: '#14201B', itemSelectedColor: '#fff' },
    Table: { headerBg: 'transparent', headerColor: '#5C6862', headerSplitColor: 'transparent' },
  },
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ConfigProvider locale={zhCN} theme={theme}>
      <AntApp>
        <App />
      </AntApp>
    </ConfigProvider>
  </StrictMode>,
)
