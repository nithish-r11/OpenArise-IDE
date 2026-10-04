import { OrbitMark } from './Icon';
export function TopBar() {
  return <header className="top-bar">
    <div className="wordmark"><OrbitMark /><span>Open<span className="wordmark-accent">Arise</span></span></div>
    <div className="project-label"><span className="project-symbol">O</span> No project open <span className="muted">/</span> <span className="muted">Workspace</span></div>
    <span className="preview-badge">DESKTOP PREVIEW</span>
  </header>;
}
