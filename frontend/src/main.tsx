import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import { IdentityGate } from './Identity'
import './workspace.css'

createRoot(document.getElementById('root')!).render(<StrictMode><IdentityGate><App /></IdentityGate></StrictMode>)
