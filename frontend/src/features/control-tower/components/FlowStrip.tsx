export function FlowStrip({
  items,
}: {
  items: string[]
}) {
  return (
    <div className="ct-flow-strip">
      {items.map((item, index) => (
        <div
          className="ct-flow-fragment"
          key={item}
        >
          <div className="ct-flow-step">
            <span>
              {index + 1}
            </span>

            <strong>
              {item}
            </strong>
          </div>

          {index < items.length - 1 && (
            <span
              className="ct-flow-arrow"
              aria-hidden="true"
            >
              →
            </span>
          )}
        </div>
      ))}
    </div>
  )
}
