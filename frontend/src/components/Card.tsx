import type { ReactNode } from "react";

interface CardProps {
  children: ReactNode;
  className?: string;
  title?: string;
  titleIcon?: ReactNode;
  trailing?: ReactNode;
}
export function Card({ children, className = "", title, titleIcon, trailing }: CardProps) {
  return (
    <section className={`card ${className}`}>
      {title ? (
        <header className="card-header">
          <div className="flex items-center gap-2">
            {titleIcon}
            <h2>{title}</h2>
          </div>
          {trailing}
        </header>
      ) : null}
      {children}
    </section>
  );
}
