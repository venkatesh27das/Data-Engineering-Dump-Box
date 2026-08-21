export function BrandMark({ small = false }: { small?: boolean }) {
  return (
    <span className={`excel-mark ${small ? 'excel-mark--small' : ''}`} aria-hidden="true">
      <span>X</span><i>⋮</i>
    </span>
  )
}

