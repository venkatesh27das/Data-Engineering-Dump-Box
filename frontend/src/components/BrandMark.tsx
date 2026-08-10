export function BrandMark() {
  return (
    <svg
      aria-hidden="true"
      className="h-9 w-9 shrink-0"
      fill="none"
      viewBox="0 0 40 40"
    >
      <path
        d="M9 8 5 26l12 6 15-7-3-16L9 8Zm0 0 8 24m12-23L17 32M5 26l27-1M9 8l20 1"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.8"
      />
      {[
        [9, 8],
        [29, 9],
        [32, 25],
        [17, 32],
        [5, 26],
      ].map(([cx, cy]) => (
        <circle key={`${cx}-${cy}`} cx={cx} cy={cy} fill="white" r="2.5" stroke="currentColor" strokeWidth="1.8" />
      ))}
    </svg>
  );
}
