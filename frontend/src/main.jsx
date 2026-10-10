import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './styles/global.css'
import './styles/components.css'
import './styles/pages.css'
// Not wrapped in React.StrictMode: in development it mounts every page twice, which sent each API
// request twice, including the slow image quality check.
ReactDOM.createRoot(document.getElementById('root')).render(<App/>)
