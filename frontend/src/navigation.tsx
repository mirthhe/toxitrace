import { createContext, useContext } from 'react'

export type TabId = 'overview' | 'predictions' | 'evidence' | 'support' | 'context' | 'trace'

// Lets any trace reference chip open the Trace tab at that entry.
export const TraceNavigation = createContext<(ref: string) => void>(() => {})

export function useGoToRef() {
  return useContext(TraceNavigation)
}
