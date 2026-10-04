import type { Section } from './Sidebar';
import { Icon, OrbitMark } from './Icon';
const descriptions: Record<Section, string> = {
  Explorer: 'A place for your project, its context, and your next idea.',
  AI: 'A dedicated space for working with your engineering agent.',
  Blueprint: 'A shared view of requirements and the plan behind your project.',
  Traceability: 'Follow the connections between requirements, implementation, and evidence.',
  Health: 'A place to understand your project environment and its health.',
  Timeline: 'A clear record of how your project evolves.',
};
export function MainWorkspace({ active }: { active: Section }) {
  return <main className="main-workspace" id="workspace" tabIndex={-1}>
    <div className="workspace-tab"><Icon name={active} /><span>{active === 'Explorer' ? 'Welcome' : active}</span><span className="tab-dot" /></div>
    <div className="workspace-content">
      <div className="page-label"><span className="small-line" /> YOUR WORKSPACE, REIMAGINED</div>
      <section className="welcome-hero">
        <div className="hero-copy"><span className="eyebrow">OPENARISE / DESKTOP FOUNDATION</span>
          <h1>{active === 'Explorer' ? <>Great ideas start <br />with a clear workspace.</> : <>{active} <br /><span className="muted">starts here.</span></>}</h1>
          <p className="hero-description">{descriptions[active]}</p>
          <div className="workspace-state"><span className="status-dot" /> {active === 'Explorer' ? 'No project connected' : 'Feature planned for a later phase'}</div>
        </div>
        <div className="orbit-scene"><div className="orbit-ring ring-one" /><div className="orbit-ring ring-two" /><div className="orbit-cross" /><OrbitMark large /><span className="orbit-caption">CONTEXT. CLARITY. CREATION.</span></div>
      </section>
      <div className="section-heading"><h2>{active === 'Explorer' ? 'Your starting point' : 'A space reserved for ' + active.toLowerCase()}</h2><span>PHASE 01</span></div>
      <section className="foundation-grid" aria-label="Foundation overview">
        <article className="foundation-card"><div className="card-icon"><Icon name="Explorer" /></div><span className="card-label">01 / WORKSPACE</span><h3>A home for your project</h3><p>Project opening and file browsing will arrive in a later phase.</p><span className="card-footer">Explorer foundation <span>PLANNED</span></span></article>
        <article className="foundation-card"><div className="card-icon violet"><Icon name="AI" /></div><span className="card-label">02 / INTELLIGENCE</span><h3>Context before action</h3><p>AI and project intelligence will connect through the existing backend.</p><span className="card-footer">Backend connection <span>NOT CONNECTED</span></span></article>
        <article className="foundation-card"><div className="card-icon"><Icon name="layers" /></div><span className="card-label">03 / FOUNDATION</span><h3>Room to build</h3><p>A focused desktop shell, ready for the next stage of OpenArise.</p><span className="card-footer">Desktop shell <span className="ready-label">AVAILABLE</span></span></article>
      </section>
      <div className="phase-note"><Icon name="lock" /><div><strong>The foundation is in place.</strong><p>This preview contains the desktop shell. Project tools and backend transport are not enabled yet.</p></div><span className="phase-number"><span>PHASE</span> 01</span></div>
      <footer className="workspace-footer"><span>Built for thoughtful engineering.</span><span>LOCAL DESKTOP · OPENARISE</span></footer>
    </div>
  </main>;
}
