// The app ships react-dom through Expo; type the portal API used by the
// viewport renderer without adding another runtime dependency.
declare module "react-dom" {
  import type { ReactNode, ReactPortal } from "react";
  export function createPortal(children: ReactNode, container: Element | DocumentFragment, key?: string | null): ReactPortal;
}
