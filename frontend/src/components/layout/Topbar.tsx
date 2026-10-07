import trazaLogo from '../../assets/branding/traza-logo.jfif?url'

export function Topbar({ onLogout }: { onLogout: () => void }) {
  return (
    <header className="topbar">
      <div className="topbar-brand">
        <img className="traza-nav-logo" src={trazaLogo} alt="TRAZA" />
        <div className="topbar-copy">
          <span>Banca digital · Digital Andino</span>
        </div>
      </div>

      <button
        className="secondary-button compact"
        onClick={onLogout}
      >
        Cerrar sesión
      </button>
    </header>
  )
}
