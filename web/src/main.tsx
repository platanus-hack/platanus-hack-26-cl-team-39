import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './lib/tema'
import './index.css'
import App from './App'
// al final: el modo oscuro pisa los estilos de index.css y de cada componente
import './tema.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
