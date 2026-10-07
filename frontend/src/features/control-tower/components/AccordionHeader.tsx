export function AccordionHeader({
  eyebrow,
  title,
  description,
  open,
  onToggle,
}: {
  eyebrow: string
  title: string
  description: string
  open: boolean
  onToggle: () => void
}) {
  return (
    <button
      type="button"
      className="ct-accordion-toggle"
      aria-expanded={open}
      onClick={onToggle}
    >
      <div>
        <span className="ct-section-kicker">
          {eyebrow}
        </span>

        <h3>
          {title}
        </h3>

        <p>
          {description}
        </p>
      </div>

      <span className="ct-accordion-action">
        <span>
          {open ? 'Ocultar' : 'Ver'}
        </span>

        <span
          className={
            open
              ? 'ct-section-chevron open'
              : 'ct-section-chevron'
          }
          aria-hidden="true"
        />
      </span>
    </button>
  )
}
