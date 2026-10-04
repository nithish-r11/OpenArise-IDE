import logo from '../assets/openarise-logo.jpeg';
export function Icon({ name, className = '' }: { name: string; className?: string }) {
  const paths: Record<string, string> = {
    Explorer: 'M3 7h7l2 2h9v11H3z M3 7V4h7l2 3',
    AI: 'm12 3 2.4 6.6L21 12l-6.6 2.4L12 21l-2.4-6.6L3 12l6.6-2.4Z',
    Blueprint: 'M4 3h12l4 4v14H4z M8 11h8 M8 15h8 M8 7h4',
    Traceability: 'M6 6h12 M6 6v12h12 M18 6v12 M3 3h6v6H3z M15 15h6v6h-6z',
    Health: 'M3 12h4l3-7 4 14 3-7h4',
    Timeline: 'M5 3v18 M5 6h13 M5 12h9 M5 18h13',
    arrow: 'M5 12h14 m-5-5 5 5-5 5',
    layers: 'm12 3 9 5-9 5-9-5z M3 12l9 5 9-5 M3 16l9 5 9-5',
    lock: 'M6 10h12v11H6z M8 10V7a4 4 0 0 1 8 0v3',
  };
  return <svg className={className} width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name] ?? paths.layers} /></svg>;
}
export function OrbitMark({ large = false }: { large?: boolean }) {
  return <img className={large ? 'orbit-mark orbit-large' : 'orbit-mark'} src={logo} alt='OpenArise IDE' draggable={false} />;
}
