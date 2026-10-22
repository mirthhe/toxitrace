import { createContext, useContext } from 'react'

// Opens the rules guide, optionally scrolled to one rule (e.g. "R6").
export const RulesGuideContext = createContext<(ruleId?: string) => void>(() => {})

export function useOpenRulesGuide() {
  return useContext(RulesGuideContext)
}
