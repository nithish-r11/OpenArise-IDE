import { Component, type ReactNode } from 'react';
import { OrbitMark } from './Icon';
/** Last-resort renderer fallback. Reload is always an explicit discard decision. */
export class RuntimeBoundary extends Component<{ children: ReactNode }, { failed: boolean; confirmReload: boolean }> {
  state = { failed: false, confirmReload: false };
  static getDerivedStateFromError() { return { failed: true, confirmReload: false }; }
  render() {
    if (!this.state.failed) return this.props.children;
    return <main className="runtime-fallback" aria-label="OpenArise runtime error">
      <OrbitMark large /><span className="eyebrow">OPENARISE</span>
      <h1>The interface could not continue.</h1>
      <p role="alert">An unexpected renderer error stopped this interface. No successful action or saved change can be confirmed from this screen.</p>
      <p>Saved files remain on disk. Unsaved editor buffers are not stored between launches.</p>
      {this.state.confirmReload ? <div className="runtime-confirmation">
        <p>Reloading discards unsaved in-memory edits. Any backend action already started may still be running; review its result after reopening the project.</p>
        <button className="primary-button" onClick={() => window.location.reload()}>Reload and discard unsaved edits</button>
        <button onClick={() => this.setState({ confirmReload: false })}>Keep this screen</button>
      </div> : <button className="primary-button" onClick={() => this.setState({ confirmReload: true })}>Reload OpenArise</button>}
      <small>If the problem returns, close OpenArise and launch it again. Report the steps that led to this screen.</small>
    </main>;
  }
}