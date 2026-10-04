import { Icon, OrbitMark } from './Icon';
export const sections = ['Explorer', 'AI', 'Blueprint', 'Traceability', 'Health', 'Timeline'] as const;
export type Section = typeof sections[number];
export function Sidebar({ active, onSelect }: { active: Section; onSelect: (section: Section) => void }) {
  return <aside className="sidebar">
    <div className="sidebar-heading">WORKSPACE <span>01</span></div>
    <nav aria-label="Workspace sections">{sections.map((section) =>
      <button key={section} className={active === section ? 'nav-item selected' : 'nav-item'} aria-current={active === section ? 'page' : undefined} onClick={() => onSelect(section)}>
        <Icon name={section} /><span>{section}</span>{section === 'AI' && <span className="nav-tag" aria-hidden="true">AI</span>}
      </button>
    )}</nav>
    <div className="sidebar-bottom"><OrbitMark /><div><strong>A foundation for what's next.</strong><p>Desktop preview · Phase 1</p></div></div>
  </aside>;
}
