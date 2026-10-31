export interface Symbol {
  id: number
  ticker: string
  name: string
  exchange: string
  price: number
}

export type SymbolCreate = Omit<Symbol, 'id'>

export type SymbolUpdate = Partial<Omit<Symbol, 'id' | 'ticker'>>
