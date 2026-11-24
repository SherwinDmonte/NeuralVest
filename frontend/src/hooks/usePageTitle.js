import { useEffect } from 'react'

// Sets the browser tab title for a page: "Reports · NeuralVest".
export function usePageTitle(title) {
  useEffect(() => {
    document.title = title ? `${title} · NeuralVest` : 'NeuralVest: understand Indian stocks with five local AI agents'
  }, [title])
}
