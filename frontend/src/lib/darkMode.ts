import { useEffect, useState } from 'react'

const KEY = 'uni-hub-theme'

function getInitial(): boolean {
  // The inline script in index.html already applied the theme to <html>;
  // read it back so React state matches without a flash.
  return document.documentElement.dataset.theme === 'dark'
}

export function useDarkMode(): [boolean, () => void] {
  const [dark, setDark] = useState(getInitial)

  useEffect(() => {
    document.documentElement.dataset.theme = dark ? 'dark' : 'light'
    localStorage.setItem(KEY, dark ? 'dark' : 'light')
  }, [dark])

  return [dark, () => setDark(d => !d)]
}
