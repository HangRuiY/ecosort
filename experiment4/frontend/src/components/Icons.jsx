export function BrandMark({ size = 34 }) {
  return (
    <svg className="brand-mark" width={size} height={size} viewBox="0 0 34 34" aria-hidden="true">
      <rect x="1.5" y="1.5" width="31" height="31" rx="7" fill="none" stroke="#F4C430" strokeWidth="3" />
      <rect x="8" y="8" width="11" height="11" fill="#1D5FA8" /><rect x="19" y="8" width="7" height="7" fill="#C62F2B" />
      <rect x="8" y="19" width="7" height="7" fill="#2F7D3B" /><rect x="15" y="19" width="11" height="7" fill="#9AA5A8" />
    </svg>
  )
}

const PATHS = {
  detect: <><path d="M4 8V5a1 1 0 0 1 1-1h3M16 4h3a1 1 0 0 1 1 1v3M20 16v3a1 1 0 0 1-1 1h-3M8 20H5a1 1 0 0 1-1-1v-3" /><rect x="8" y="8" width="8" height="8" /></>,
  text: <path d="M4 5h16v11H9l-5 4z" />,
  match: <><rect x="3" y="5" width="8" height="8" /><path d="M14 7h7M14 11h5M7 17v2h12v-4" /></>,
  tasks: <><path d="M4 6h16M4 12h10M4 18h7" /><circle cx="18" cy="16" r="3" /></>,
  api: <path d="M8 7l-5 5 5 5M16 7l5 5-5 5" />,
  agent: <><path d="M4 4h16v11H10l-6 5z" /><circle cx="9" cy="9.5" r="1.2" /><circle cx="15" cy="9.5" r="1.2" /></>,
}
export function NavIcon({ name }) {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">{PATHS[name]}</svg>
}

export function BinIcon({ color }) {
  return (
    <svg className="can" viewBox="0 0 56 68" aria-hidden="true">
      <rect x="4" y="8" width="48" height="8" rx="2" fill={color} />
      <path d="M8 18h40l-4 46H12z" fill={color} />
      <path d="M20 28v26M28 28v26M36 28v26" stroke="#fff" strokeOpacity=".5" strokeWidth="3" />
      <rect x="22" y="2" width="12" height="6" rx="2" fill={color} />
    </svg>
  )
}
