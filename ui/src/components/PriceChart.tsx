import { useEffect, useMemo, useRef, useState } from 'react'
import {
  CandlestickSeries,
  ColorType,
  CrosshairMode,
  createChart,
  HistogramSeries,
  LineSeries,
  LineStyle,
  MismatchDirection,
  PriceScaleMode,
  type CandlestickData,
  type IChartApi,
  type ISeriesApi,
  type Logical,
  type MouseEventParams,
  type UTCTimestamp,
} from 'lightweight-charts'
import type { ChartRef, TimeRange } from '../api/chartStateApi'
import { INTRADAY_TIMEFRAMES, type Candle, type IndicatorResult } from '../types/candle'
import { BoxesPrimitive, type PriceBox } from './boxesPrimitive'
import { publishCrosshairTime, subscribeCrosshairTime } from './crosshairSync'
import { FibPrimitive, type ChartPoint } from './fibPrimitive'

const UP = '#26a69a'
const DOWN = '#ef5350'

const LINE_COLORS: Record<string, string> = {
  'adx.adx': '#ffffff',
  'adx.plus_di': UP,
  'adx.minus_di': DOWN,
  'macd.macd': '#2962ff',
  'macd.signal': '#ff6d00',
}
const FALLBACK_COLOR = '#b2b5be'

const REFERENCE_LEVELS: Record<string, number[]> = {
  macd: [0],
}

const PRICE_PANE_STRETCH = 3

const themes = {
  dark: { background: '#131722', text: '#d1d4dc', grid: '#2a2e39', border: '#363a45' },
  light: { background: '#ffffff', text: '#191919', grid: '#f0f3fa', border: '#d6dcde' },
}

export type ChartTheme = keyof typeof themes

const PRICE_PANE_ID = 'price'

const AUTO_BY_DEFAULT: ReadonlySet<string> = new Set(['macd'])

function applyAutoScale(chart: IChartApi, paneIds: string[], autoPanes: Record<string, boolean>) {
  paneIds.forEach((id, i) => {
    if (autoPanes[id] && paneExists(chart, i)) {
      chart.priceScale('right', i).applyOptions({ autoScale: true })
    }
  })
}

function paneExists(chart: IChartApi, index: number) {
  return index < chart.panes().length
}

interface HoveredBar {
  time: string
  open: number
  high: number
  low: number
  close: number
  right: number
}

function formatBarTime(time: number, withClock: boolean) {
  return new Date(time * 1000).toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    ...(withClock && { hour: '2-digit', minute: '2-digit' }),
    timeZone: 'UTC',
  })
}

export interface ChangeBand {
  from: number
  to: number | null
}

function positionBand(chart: IChartApi, el: HTMLDivElement | null, band: ChangeBand | null) {
  if (!el) return
  const timeScale = chart.timeScale()
  const first = band && timeScale.timeToIndex(band.from as UTCTimestamp, true)
  const last = band?.to != null ? timeScale.timeToIndex(band.to as UTCTimestamp, true) : first
  if (first == null || last == null) {
    el.style.display = 'none'
    return
  }
  const width = timeScale.width()
  const clamp = (x: number | null) => Math.min(Math.max(x ?? 0, 0), width)
  const left = clamp(timeScale.logicalToCoordinate((first - 0.5) as Logical))
  const right = clamp(timeScale.logicalToCoordinate((last + 0.5) as Logical))
  el.style.display = 'block'
  el.style.left = `${left}px`
  el.style.width = `${Math.max(right - left, 2)}px`
}

function barAt(candles: Candle[], time: number): Candle | undefined {
  let lo = 0
  let hi = candles.length
  while (lo < hi) {
    const mid = (lo + hi) >> 1
    if (candles[mid].time <= time) lo = mid + 1
    else hi = mid
  }
  return candles[lo - 1]
}

export interface ChartView {
  chart: ChartRef
  range: TimeRange | null
}

interface Props {
  candles: Candle[]
  indicators: IndicatorResult[]
  view: ChartView | null
  onVisibleRangeChange: (chart: ChartRef, range: TimeRange) => void
  theme: ChartTheme
  logScale: boolean
  resetKey: number
  intraday?: boolean
  changeBand?: ChangeBand | null
  onPickTime?: (time: number) => void
  onDragPrice?: (ratio: number, done: boolean) => void
  crosshairSyncId?: string
  boxes?: PriceBox[]
  fibPoints?: ChartPoint[]
  onPickPoint?: (point: ChartPoint) => void
  onHoverPoint?: (point: ChartPoint | null) => void
}

const NO_BOXES: PriceBox[] = []
const NO_POINTS: ChartPoint[] = []

function snappedPoint(
  series: ISeriesApi<'Candlestick'>,
  logical: number,
  y: number,
): ChartPoint | null {
  const index = Math.round(logical)
  const bar =
    series.dataByIndex(index, MismatchDirection.NearestLeft) ??
    series.dataByIndex(index, MismatchDirection.NearestRight)
  if (!bar || !('high' in bar)) return null
  const { high, low } = bar as CandlestickData
  const price = series.coordinateToPrice(y)
  const nearHigh = price !== null && Math.abs(price - high) < Math.abs(price - low)
  return { time: bar.time as number, price: nearHigh ? high : low }
}

export function PriceChart({
  crosshairSyncId,
  boxes = NO_BOXES,
  fibPoints = NO_POINTS,
  onPickPoint,
  onHoverPoint,
  candles,
  indicators,
  view,
  onVisibleRangeChange,
  theme,
  logScale,
  resetKey,
  intraday = false,
  changeBand = null,
  onPickTime,
  onDragPrice,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null)
  const volumeSeriesRef = useRef<ISeriesApi<'Histogram'> | null>(null)
  const lineSeriesRef = useRef(new Map<string, ISeriesApi<'Line'>>())
  const shownChartRef = useRef<ChartRef | null>(null)
  const onRangeChangeRef = useRef(onVisibleRangeChange)

  const onPickTimeRef = useRef(onPickTime)
  const onDragPriceRef = useRef(onDragPrice)
  const onPickPointRef = useRef(onPickPoint)
  const onHoverPointRef = useRef(onHoverPoint)
  const fibPrimitiveRef = useRef<FibPrimitive | null>(null)
  const bandRef = useRef<HTMLDivElement>(null)
  const changeBandRef = useRef(changeBand)
  const candlesRef = useRef(candles)
  const boxesPrimitiveRef = useRef<BoxesPrimitive | null>(null)

  useEffect(() => {
    onRangeChangeRef.current = onVisibleRangeChange
    onPickTimeRef.current = onPickTime
    onDragPriceRef.current = onDragPrice
    onPickPointRef.current = onPickPoint
    onHoverPointRef.current = onHoverPoint
  }, [onVisibleRangeChange, onPickTime, onDragPrice, onPickPoint, onHoverPoint])

  const panes = useMemo(
    () => [
      { id: PRICE_PANE_ID, label: 'Price' },
      ...indicators.map((ind) => ({ id: ind.id, label: ind.name })),
    ],
    [indicators],
  )
  const [autoPanes, setAutoPanes] = useState<Record<string, boolean>>({})
  const isAuto = (id: string) => autoPanes[id] ?? AUTO_BY_DEFAULT.has(id)
  const [paneTops, setPaneTops] = useState<number[]>([])
  const autoStateRef = useRef({ paneIds: [] as string[], autoPanes })
  const prevAutoPanesRef = useRef<Record<string, boolean>>({})
  const [hovered, setHovered] = useState<HoveredBar | null>(null)

  useEffect(() => {
    const chart = createChart(containerRef.current!, {
      autoSize: true,
      crosshair: { mode: CrosshairMode.Normal },
      handleScale: { axisPressedMouseMove: { time: true, price: true }, axisDoubleClickReset: true },
      timeScale: {
        rightOffset: 5,
        timeVisible: false,
        lockVisibleTimeRangeOnResize: true,
        minBarSpacing: 0.01,
      },
    })
    candleSeriesRef.current = chart.addSeries(CandlestickSeries, {
      upColor: UP,
      downColor: DOWN,
      wickUpColor: UP,
      wickDownColor: DOWN,
      borderVisible: false,
    })
    boxesPrimitiveRef.current = new BoxesPrimitive()
    candleSeriesRef.current.attachPrimitive(boxesPrimitiveRef.current)
    fibPrimitiveRef.current = new FibPrimitive()
    candleSeriesRef.current.attachPrimitive(fibPrimitiveRef.current)
    volumeSeriesRef.current = chart.addSeries(HistogramSeries, {
      priceScaleId: '',
      priceFormat: { type: 'volume' },
      lastValueVisible: false,
      priceLineVisible: false,
    })
    chart.priceScale('').applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } })
    chart.priceScale('right').applyOptions({ scaleMargins: { top: 0.1, bottom: 0.25 } })
    chartRef.current = chart

    const reapplyAutoScale = () => {
      const { paneIds, autoPanes } = autoStateRef.current
      applyAutoScale(chart, paneIds, autoPanes)
    }
    window.addEventListener('pointerup', reapplyAutoScale)

    const placeBand = () => positionBand(chart, bandRef.current, changeBandRef.current)
    chart.timeScale().subscribeVisibleLogicalRangeChange(placeBand)
    chart.timeScale().subscribeSizeChange(placeBand)

    chart.subscribeClick((param) => {
      const pickPoint = onPickPointRef.current
      const pointSeries = candleSeriesRef.current
      if (pickPoint && pointSeries && param.logical !== undefined && param.point) {
        const point = snappedPoint(pointSeries, param.logical, param.point.y)
        if (point) pickPoint(point)
      }

      const pick = onPickTimeRef.current
      const series = candleSeriesRef.current
      if (!pick || !series || param.logical === undefined) return
      const index = Math.round(param.logical)
      const bar =
        series.dataByIndex(index, MismatchDirection.NearestLeft) ??
        series.dataByIndex(index, MismatchDirection.NearestRight)
      if (bar) pick(bar.time as number)
    })

    chart.timeScale().subscribeVisibleTimeRangeChange((range) => {
      reapplyAutoScale()
      if (range && shownChartRef.current) {
        onRangeChangeRef.current(shownChartRef.current, {
          from: range.from as number,
          to: range.to as number,
        })
      }
    })

    chart.subscribeCrosshairMove((param) => {
      const hoverPoint = onHoverPointRef.current
      if (hoverPoint && candleSeriesRef.current) {
        hoverPoint(
          param.logical !== undefined && param.point
            ? snappedPoint(candleSeriesRef.current, param.logical, param.point.y)
            : null,
        )
      }

      const bar = candleSeriesRef.current && param.seriesData.get(candleSeriesRef.current)
      if (!bar || !('open' in bar)) {
        setHovered(null)
        return
      }
      const interval = shownChartRef.current?.interval
      setHovered({
        time: formatBarTime(bar.time as number, !!interval && INTRADAY_TIMEFRAMES.has(interval)),
        open: bar.open,
        high: bar.high,
        low: bar.low,
        close: bar.close,
        right: chart.priceScale('right').width() + 8,
      })
    })

    const lineSeries = lineSeriesRef.current
    return () => {
      window.removeEventListener('pointerup', reapplyAutoScale)
      chart.remove()
      chartRef.current = null
      lineSeries.clear()
    }
  }, [])

  useEffect(() => {
    const t = themes[theme]
    chartRef.current?.applyOptions({
      layout: {
        background: { type: ColorType.Solid, color: t.background },
        textColor: t.text,
        panes: { separatorColor: t.border },
      },
      grid: { vertLines: { color: t.grid }, horzLines: { color: t.grid } },
      rightPriceScale: { borderColor: t.border },
      timeScale: { borderColor: t.border },
    })
  }, [theme])

  useEffect(() => {
    chartRef.current?.applyOptions({ timeScale: { timeVisible: intraday } })
  }, [intraday])

  useEffect(() => {
    chartRef.current?.priceScale('right', 0).applyOptions({
      mode: logScale ? PriceScaleMode.Logarithmic : PriceScaleMode.Normal,
    })
  }, [logScale])

  useEffect(() => {
    shownChartRef.current = view?.chart ?? null
    candlesRef.current = candles
    candleSeriesRef.current?.setData(
      candles.map((c) => ({
        time: c.time as UTCTimestamp,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      })),
    )
    volumeSeriesRef.current?.setData(
      candles.map((c) => ({
        time: c.time as UTCTimestamp,
        value: c.volume,
        color: c.close >= c.open ? `${UP}66` : `${DOWN}66`,
      })),
    )
  }, [candles, view])

  useEffect(() => {
    boxesPrimitiveRef.current?.setBoxes(boxes)
  }, [boxes])

  useEffect(() => {
    fibPrimitiveRef.current?.setPoints(fibPoints)
  }, [fibPoints])

  useEffect(() => {
    changeBandRef.current = changeBand
    if (chartRef.current) positionBand(chartRef.current, bandRef.current, changeBand)
  }, [changeBand, candles])

  const dragEnabled = !!onDragPrice
  useEffect(() => {
    const chart = chartRef.current
    const container = containerRef.current
    if (!chart || !container || !dragEnabled) return
    const panning = (on: boolean) =>
      chart.applyOptions({
        handleScroll: { pressedMouseMove: on, horzTouchDrag: on, vertTouchDrag: on },
      })
    panning(false)

    let drag: { pointerId: number; startPrice: number; ratio: number } | null = null
    const priceAt = (e: PointerEvent) => {
      const rect = container.getBoundingClientRect()
      const x = e.clientX - rect.left
      const y = e.clientY - rect.top
      const inPricePane = x <= chart.timeScale().width() && y <= chart.panes()[0].getHeight()
      const price = candleSeriesRef.current?.coordinateToPrice(y)
      return { inPricePane, price: price != null && price > 0 ? price : null }
    }
    const down = (e: PointerEvent) => {
      const { inPricePane, price } = priceAt(e)
      if (e.button !== 0 || !inPricePane || price === null) return
      chart.priceScale('right', 0).applyOptions({ autoScale: false })
      container.setPointerCapture(e.pointerId)
      drag = { pointerId: e.pointerId, startPrice: price, ratio: 1 }
      onDragPriceRef.current?.(1, false)
    }
    const move = (e: PointerEvent) => {
      if (drag?.pointerId !== e.pointerId) return
      const { price } = priceAt(e)
      if (price === null) return
      drag.ratio = price / drag.startPrice
      onDragPriceRef.current?.(drag.ratio, false)
    }
    const up = (e: PointerEvent) => {
      if (drag?.pointerId !== e.pointerId) return
      onDragPriceRef.current?.(drag.ratio, true)
      drag = null
    }
    container.addEventListener('pointerdown', down)
    container.addEventListener('pointermove', move)
    container.addEventListener('pointerup', up)
    container.addEventListener('pointercancel', up)
    return () => {
      container.removeEventListener('pointerdown', down)
      container.removeEventListener('pointermove', move)
      container.removeEventListener('pointerup', up)
      container.removeEventListener('pointercancel', up)
      panning(true)
    }
  }, [dragEnabled])

  useEffect(() => {
    const chart = chartRef.current
    const container = containerRef.current
    if (!chart || !container || !crosshairSyncId) return
    let showingSynced = false
    const showHorzLine = (visible: boolean) =>
      chart.applyOptions({ crosshair: { horzLine: { visible, labelVisible: visible } } })
    const hideSynced = () => {
      if (!showingSynced) return
      showingSynced = false
      chart.clearCrosshairPosition()
      showHorzLine(true)
    }

    const onMove = (param: MouseEventParams) => {
      if (!param.sourceEvent) return
      if (showingSynced) {
        showingSynced = false
        showHorzLine(true)
      }
      publishCrosshairTime(crosshairSyncId, param.time === undefined ? null : (param.time as number))
    }
    const onLeave = () => publishCrosshairTime(crosshairSyncId, null)

    const unsubscribe = subscribeCrosshairTime((sourceId, time) => {
      if (sourceId === crosshairSyncId) return
      const series = candleSeriesRef.current
      const bar = time === null ? undefined : barAt(candlesRef.current, time)
      const index = bar && chart.timeScale().timeToIndex(bar.time as UTCTimestamp)
      const range = chart.timeScale().getVisibleLogicalRange()
      if (!series || !bar || index == null || !range || index < range.from || index > range.to) {
        hideSynced()
        return
      }
      if (!showingSynced) {
        showingSynced = true
        showHorzLine(false)
      }
      chart.setCrosshairPosition(bar.close, bar.time as UTCTimestamp, series)
    })

    chart.subscribeCrosshairMove(onMove)
    container.addEventListener('mouseleave', onLeave)
    return () => {
      unsubscribe()
      chart.unsubscribeCrosshairMove(onMove)
      container.removeEventListener('mouseleave', onLeave)
      hideSynced()
    }
  }, [crosshairSyncId])

  useEffect(() => {
    const chart = chartRef.current
    if (!chart) return
    const lineSeries = lineSeriesRef.current
    const current = new Set<string>()

    indicators.forEach((indicator, i) => {
      indicator.lines.forEach((line) => {
        const key = `${indicator.id}.${line.key}`
        current.add(key)
        let series = lineSeries.get(key)
        if (!series) {
          series = chart.addSeries(
            LineSeries,
            {
              color: LINE_COLORS[key] ?? FALLBACK_COLOR,
              lineWidth: 1,
              title: line.label,
              priceLineVisible: false,
            },
            i + 1,
          )
          for (const level of REFERENCE_LEVELS[indicator.id] ?? []) {
            if (line === indicator.lines[0]) {
              series.createPriceLine({
                price: level,
                color: FALLBACK_COLOR,
                lineStyle: LineStyle.Dashed,
                lineWidth: 1,
                axisLabelVisible: false,
              })
            }
          }
          lineSeries.set(key, series)
        }
        series.setData(line.values.map((p) => ({ time: p.time as UTCTimestamp, value: p.value })))
      })
    })

    for (const [key, series] of lineSeries) {
      if (!current.has(key)) {
        chart.removeSeries(series)
        lineSeries.delete(key)
      }
    }
    chart.panes().forEach((pane, i) => {
      pane.setStretchFactor(i === 0 ? PRICE_PANE_STRETCH : 1)
      if (i > 0) pane.priceScale('right').applyOptions({ mode: PriceScaleMode.Normal })
    })
  }, [indicators])

  useEffect(() => {
    const timeScale = chartRef.current?.timeScale()
    timeScale?.applyOptions({
      timeVisible: !!view && INTRADAY_TIMEFRAMES.has(view.chart.interval),
    })
    const showView = () => {
      if (view?.range) {
        timeScale?.setVisibleRange({
          from: view.range.from as UTCTimestamp,
          to: view.range.to as UTCTimestamp,
        })
      } else {
        timeScale?.fitContent()
      }
    }
    if (!timeScale || timeScale.width() > 0) {
      showView()
      return
    }
    let frame = requestAnimationFrame(function waitForWidth() {
      if (timeScale.width() > 0) showView()
      else frame = requestAnimationFrame(waitForWidth)
    })
    return () => cancelAnimationFrame(frame)
  }, [view])

  useEffect(() => {
    const resolved = Object.fromEntries(
      panes.map((p) => [p.id, autoPanes[p.id] ?? AUTO_BY_DEFAULT.has(p.id)]),
    )
    autoStateRef.current = { paneIds: panes.map((p) => p.id), autoPanes: resolved }
    const chart = chartRef.current
    if (!chart) return
    panes.forEach((pane, i) => {
      const on = resolved[pane.id]
      if (on !== !!prevAutoPanesRef.current[pane.id] && paneExists(chart, i)) {
        chart.priceScale('right', i).applyOptions({ autoScale: on })
      }
    })
    prevAutoPanesRef.current = resolved
  }, [panes, autoPanes])

  useEffect(() => {
    const chart = chartRef.current
    const container = containerRef.current
    if (!chart || !container) return
    const measure = () => {
      const base = container.getBoundingClientRect().top
      const tops = chart
        .panes()
        .map((pane) => (pane.getHTMLElement()?.getBoundingClientRect().top ?? base) - base)
      setPaneTops((prev) =>
        prev.length === tops.length && prev.every((t, i) => t === tops[i]) ? prev : tops,
      )
    }
    const observer = new ResizeObserver(measure)
    const frame = requestAnimationFrame(() => {
      observer.observe(container)
      for (const pane of chart.panes()) {
        const el = pane.getHTMLElement()
        if (el) observer.observe(el)
      }
      measure()
    })
    return () => {
      cancelAnimationFrame(frame)
      observer.disconnect()
    }
  }, [panes])

  useEffect(() => {
    if (resetKey === 0) return
    chartRef.current?.priceScale('right').applyOptions({ autoScale: true })
    chartRef.current?.timeScale().fitContent()
  }, [resetKey])

  return (
    <div
      className={`price-chart-wrap ${onPickTime || onPickPoint ? 'change-pick' : ''} ${dragEnabled ? 'change-drag' : ''}`}
    >
      <div ref={containerRef} className="price-chart" />
      <div ref={bandRef} className="change-band" />
      {hovered && (
        <div
          className={`ohlc-tooltip ${hovered.close >= hovered.open ? 'up' : 'down'}`}
          style={{ right: hovered.right }}
        >
          <div className="ohlc-time">{hovered.time}</div>
          <span>O</span>
          <b>{hovered.open.toFixed(2)}</b>
          <span>H</span>
          <b>{hovered.high.toFixed(2)}</b>
          <span>L</span>
          <b>{hovered.low.toFixed(2)}</b>
          <span>C</span>
          <b>{hovered.close.toFixed(2)}</b>
        </div>
      )}
      {panes.map((pane, i) =>
        paneTops[i] === undefined ? null : (
          <button
            key={pane.id}
            type="button"
            className={`pane-auto ${isAuto(pane.id) ? 'active' : ''}`}
            style={{ top: paneTops[i] + 6 }}
            onClick={() => setAutoPanes((prev) => ({ ...prev, [pane.id]: !isAuto(pane.id) }))}
            title="Keep this pane's price axis fitted to the visible bars"
          >
            {pane.label} · Auto
          </button>
        ),
      )}
    </div>
  )
}
