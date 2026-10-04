import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import { RuntimeBoundary } from './components/RuntimeBoundary';
import './styles/globals.css';
import './styles/polish.css';
createRoot(document.getElementById('root')!).render(<StrictMode><RuntimeBoundary><App /></RuntimeBoundary></StrictMode>);
