import { useMemo } from 'react'
import {
  AllCommunityModule,
  colorSchemeDarkBlue,
  ModuleRegistry,
  themeQuartz,
  type ColDef,
  type ICellRendererParams,
} from 'ag-grid-community'
import { AgGridReact } from 'ag-grid-react'
import type { SavedView } from '../api/savedViewApi'
import {
  INTERVAL_LABELS,
  INTRADAY_TIMEFRAMES,
  isSynthetic,
  SYNTHETIC_BY_VALUE,
  type ChartTimeframe,
} from '../types/candle'
import './SavedViewsGrid.css'

ModuleRegistry.registerModules([AllCommunityModule])

const darkQuery = window.matchMedia('(prefers-color-scheme: dark)')

function timeframeLabel(tf: ChartTimeframe) {
  return isSynthetic(tf) ? `${SYNTHETIC_BY_VALUE[tf].label} (synthetic)` : INTERVAL_LABELS[tf]
}

function hasClock(tf: ChartTimeframe) {
  return INTRADAY_TIMEFRAMES.has(isSynthetic(tf) ? SYNTHETIC_BY_VALUE[tf].base : tf)
}

function formatTime(seconds: number, withClock: boolean) {
  return new Date(seconds * 1000).toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    ...(withClock && { hour: '2-digit', minute: '2-digit' }),
    timeZone: 'UTC',
  })
}

interface Props {
  views: SavedView[]
  panels: { id: string; label: string }[]
  onOpen: (view: SavedView, panelId: string) => void
  onDelete: (view: SavedView) => void
}

export function SavedViewsGrid({ views, panels, onOpen, onDelete }: Props) {
  const columnDefs = useMemo<ColDef<SavedView>[]>(
    () => [
      { field: 'ticker', headerName: 'Ticker', flex: 1.4, minWidth: 120 },
      {
        field: 'interval',
        headerName: 'Timeframe',
        flex: 1,
        minWidth: 110,
        valueFormatter: (p) => (p.value ? timeframeLabel(p.value) : ''),
      },
      {
        field: 'from',
        headerName: 'From',
        flex: 1.2,
        minWidth: 130,
        valueFormatter: (p) => (p.data ? formatTime(p.data.from, hasClock(p.data.interval)) : ''),
      },
      {
        field: 'to',
        headerName: 'To',
        flex: 1.2,
        minWidth: 130,
        valueFormatter: (p) => (p.data ? formatTime(p.data.to, hasClock(p.data.interval)) : ''),
      },
      {
        field: 'updated_at',
        headerName: 'Saved',
        flex: 1.4,
        minWidth: 160,
        sort: 'desc',
        valueFormatter: (p) =>
          p.value
            ? new Date(/Z|[+-]\d\d:?\d\d$/.test(p.value) ? p.value : `${p.value}Z`).toLocaleString()
            : '',
      },
      {
        headerName: '',
        colId: 'actions',
        sortable: false,
        filter: false,
        resizable: false,
        minWidth: 220,
        flex: 1.6,
        cellRenderer: (p: ICellRendererParams<SavedView>) =>
          p.data && (
            <div className="saved-view-actions">
              {panels.map((panel) => (
                <button key={panel.id} type="button" onClick={() => onOpen(p.data!, panel.id)}>
                  {panel.label}
                </button>
              ))}
              <button type="button" className="danger" onClick={() => onDelete(p.data!)}>
                Delete
              </button>
            </div>
          ),
      },
    ],
    [panels, onOpen, onDelete],
  )

  const theme = useMemo(
    () => (darkQuery.matches ? themeQuartz.withPart(colorSchemeDarkBlue) : themeQuartz),
    [],
  )

  return (
    <section className="saved-views">
      <h2>Saved views</h2>
      <AgGridReact<SavedView>
        theme={theme}
        rowData={views}
        columnDefs={columnDefs}
        getRowId={(p) => String(p.data.id)}
        defaultColDef={{ sortable: true, filter: true, resizable: true }}
        domLayout="autoHeight"
        overlayNoRowsTemplate="No saved views yet. Press Add on a chart to save its ticker, timeframe and window."
      />
    </section>
  )
}
