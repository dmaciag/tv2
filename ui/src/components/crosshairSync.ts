type Listener = (sourceId: string, time: number | null) => void

const listeners = new Set<Listener>()

export function publishCrosshairTime(sourceId: string, time: number | null) {
  for (const listener of listeners) listener(sourceId, time)
}

export function subscribeCrosshairTime(listener: Listener) {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}
