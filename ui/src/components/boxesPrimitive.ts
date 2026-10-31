import type {
  IPrimitivePaneRenderer,
  IPrimitivePaneView,
  ISeriesPrimitive,
  Logical,
  SeriesAttachedParameter,
  Time,
  UTCTimestamp,
} from 'lightweight-charts'

export interface PriceBox {
  start: number
  end: number
  low: number
  high: number
  label: string
}

const BOX_COLOR = '#f5c518'

type DrawTarget = Parameters<IPrimitivePaneRenderer['draw']>[0]

export class BoxesPrimitive implements ISeriesPrimitive<Time> {
  private boxes: PriceBox[] = []
  private params: SeriesAttachedParameter<Time> | null = null

  attached(params: SeriesAttachedParameter<Time>) {
    this.params = params
  }

  detached() {
    this.params = null
  }

  setBoxes(boxes: PriceBox[]) {
    this.boxes = boxes
    this.params?.requestUpdate()
  }

  paneViews(): IPrimitivePaneView[] {
    return [{ renderer: () => ({ draw: (target) => this.draw(target) }) }]
  }

  private draw(target: DrawTarget) {
    if (!this.params || this.boxes.length === 0) return
    const { chart, series } = this.params
    const timeScale = chart.timeScale()
    target.useMediaCoordinateSpace(({ context: ctx }) => {
      for (const box of this.boxes) {
        const first = timeScale.timeToIndex(box.start as UTCTimestamp, true)
        const last = timeScale.timeToIndex(box.end as UTCTimestamp, true)
        if (first === null || last === null) continue
        const left = timeScale.logicalToCoordinate((first - 0.5) as Logical)
        const right = timeScale.logicalToCoordinate((last + 0.5) as Logical)
        const top = series.priceToCoordinate(box.high)
        const bottom = series.priceToCoordinate(box.low)
        if (left === null || right === null || top === null || bottom === null) continue

        ctx.fillStyle = `${BOX_COLOR}1a`
        ctx.fillRect(left, top, right - left, bottom - top)
        ctx.strokeStyle = BOX_COLOR
        ctx.lineWidth = 2
        ctx.strokeRect(left, top, right - left, bottom - top)
        ctx.fillStyle = BOX_COLOR
        ctx.font = '12px sans-serif'
        ctx.textBaseline = 'bottom'
        ctx.fillText(box.label, left + 2, top - 3)
      }
    })
  }
}
