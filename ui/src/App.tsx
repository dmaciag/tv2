import { useCallback, useEffect, useState } from 'react'
import type { ChartRef } from './api/chartStateApi'
import { savedViewApi, type SavedView, type SavedViewInput } from './api/savedViewApi'
import { ChartPanel, type OpenRequest } from './components/ChartPanel'
import { SavedViewsGrid } from './components/SavedViewsGrid'
import './App.css'

const LEFT_DEFAULT: ChartRef = { ticker: 'MSFT', interval: '1wk' }
const RIGHT_DEFAULT: ChartRef = { ticker: 'AAPL', interval: '1wk' }

const PANELS = [
  { id: 'left', label: 'Open 1', defaultChart: LEFT_DEFAULT },
  { id: 'right', label: 'Open 2', defaultChart: RIGHT_DEFAULT },
]

function App() {
  const [views, setViews] = useState<SavedView[]>([])
  const [openRequests, setOpenRequests] = useState<Record<string, OpenRequest>>({})

  const refreshViews = useCallback(
    () =>
      savedViewApi
        .list()
        .then(setViews)
        .catch(() => {}),
    [],
  )

  useEffect(() => {
    refreshViews()
  }, [refreshViews])

  const saveView = useCallback(
    (view: SavedViewInput) => savedViewApi.save(view).then(refreshViews),
    [refreshViews],
  )

  const openView = useCallback((view: SavedView, panelId: string) => {
    setOpenRequests((prev) => ({
      ...prev,
      [panelId]: { view, nonce: (prev[panelId]?.nonce ?? 0) + 1 },
    }))
  }, [])

  const deleteView = useCallback(
    (view: SavedView) => {
      setViews((prev) => prev.filter((v) => v.id !== view.id))
      savedViewApi.remove(view.id).catch(refreshViews)
    },
    [refreshViews],
  )

  return (
    <main>
      <h1>TradingView 2.0</h1>
      <div className="chart-grid">
        {PANELS.map((panel) => (
          <ChartPanel
            key={panel.id}
            panelId={panel.id}
            label={panel.label}
            defaultChart={panel.defaultChart}
            openRequest={openRequests[panel.id] ?? null}
            onSaveView={saveView}
          />
        ))}
      </div>
      <SavedViewsGrid views={views} panels={PANELS} onOpen={openView} onDelete={deleteView} />
    </main>
  )
}

export default App
