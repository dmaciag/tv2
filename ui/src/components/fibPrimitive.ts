import type {
  IPrimitivePaneRenderer,
  IPrimitivePaneView,
  ISeriesPrimitive,
  SeriesAttachedParameter,
  Time,
  UTCTimestamp,
} from 'lightweight-charts'

export interface ChartPoint {
  time: number
  price: number
}

const FIB_LEVELS = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1, 1.272, 1.618, 2, 2.618]
const LEVEL_COLORS: Record<number, string> = {
  0: '#787b86',
  0.236: '#f23645',
  0.382: '#ff9800',
  0.5: '#4caf50',
  0.618: '#089981',
  0.786: '#00bcd4',
  1: '#787b86',
  1.272: '#e91e63',
  1.618: '#2962ff',
  2: '#9c27b0',
  2.618: '#ff5722',
}

interface Level {
  ratio: number
  price: number
}

type DrawTarget = Parameters<IPrimitivePaneRenderer['draw']>[0]

export class FibPrimitive implements ISeriesPrimitive<Time> {
  private points: ChartPoint[] = []
  private params: SeriesAttachedParameter<Time> | null = null

  attached(params: SeriesAttachedParameter<Time>) {
    this.params = params
  }

  detached() {
    this.params = null
  }

  setPoints(points: ChartPoint[]) {
    this.points = points
    this.params?.requestUpdate()
  }

  paneViews(): IPrimitivePaneView[] {
    return [{ renderer: () => ({ draw: (target) => this.draw(target) }) }]
  }

  private draw(target: DrawTarget) {
    const [p1, p2] = this.points
    if (!this.params || !p1) return
    const { chart, series } = this.params
    const x = (p: ChartPoint) => chart.timeScale().timeToCoordinate(p.time as UTCTimestamp)
    const y = (price: number) => series.priceToCoordinate(price)

    target.useMediaCoordinateSpace(({ context: ctx, mediaSize }) => {
      const anchors = this.points.map((p) => ({ x: x(p), y: y(p.price) }))
      ctx.setLineDash([4, 4])
      ctx.strokeStyle = '#787b86'
      ctx.lineWidth = 1
      ctx.beginPath()
      anchors.forEach((a, i) => {
        if (a.x === null || a.y === null) return
        if (i === 0) ctx.moveTo(a.x, a.y)
        else ctx.lineTo(a.x, a.y)
      })
      ctx.stroke()
      ctx.setLineDash([])

      const drawLevels = (levels: Level[], from: number | null) => {
        if (from === null) return
        const width = mediaSize.width - from
        levels.forEach((level, i) => {
          const ly = y(level.price)
          if (ly === null) return
          const color = LEVEL_COLORS[level.ratio] ?? '#787b86'
          const next = levels[i + 1] && y(levels[i + 1].price)
          if (next != null) {
            ctx.fillStyle = `${color}14`
            ctx.fillRect(from, Math.min(ly, next), width, Math.abs(next - ly))
          }
          ctx.strokeStyle = color
          ctx.beginPath()
          ctx.moveTo(from, ly)
          ctx.lineTo(mediaSize.width, ly)
          ctx.stroke()
          ctx.fillStyle = color
          ctx.font = '11px sans-serif'
          ctx.textBaseline = 'bottom'
          ctx.fillText(`${level.ratio} (${level.price.toFixed(2)})`, from + 4, ly - 2)
        })
      }

      if (p2) {
        const left = Math.min(x(p1) ?? Infinity, x(p2) ?? Infinity)
        drawLevels(
          FIB_LEVELS.map((ratio) => ({ ratio, price: p2.price + (p1.price - p2.price) * ratio })),
          Number.isFinite(left) ? left : null,
        )
      }
    })
  }
}
