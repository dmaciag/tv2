import type { ChartRef } from './api/chartStateApi'
import { ChartPanel } from './components/ChartPanel'
import './App.css'

const LEFT_DEFAULT: ChartRef = { ticker: 'MSFT', interval: '1wk' }
const RIGHT_DEFAULT: ChartRef = { ticker: 'AAPL', interval: '1wk' }

function App() {
  return (
    <main>
      <h1>TradingView 2.0</h1>
      <div className="chart-grid">
        <ChartPanel panelId="left" defaultChart={LEFT_DEFAULT} />
        <ChartPanel panelId="right" defaultChart={RIGHT_DEFAULT} />
      </div>
    </main>
  )
}

export default App
