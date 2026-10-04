import { Component, type ReactNode } from 'react';
export class EditorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  render() {
    return this.state.failed ? <div className="error-banner" role="alert">Unable to load editor. Your open buffers are retained. Restart the application after saving or copying your work.</div> : this.props.children;
  }
}
