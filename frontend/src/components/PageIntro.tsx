import type { ReactNode } from "react";

interface PageIntroProps {
  title: string;
  description: string;
  action?: ReactNode;
}
export function PageIntro({ title, description, action }: PageIntroProps) {
  return (
    <div className="page-intro">
      <div>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {action}
    </div>
  );
}
