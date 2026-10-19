/** Prevent a canvas drag from selecting page text after leaving its bounds. */
export function installDragSelectionGuard(doc: Document, win: Window) {
  const pointers = new Set<number>();
  const editable = 'input, textarea, button, [role="button"], [contenteditable="true"]';
  const targetElement = (event: Event) => {
    const target = event.target as Element | null;
    return typeof target?.closest === "function" ? target : null;
  };
  const down = (event: PointerEvent) => {
    const target = targetElement(event);
    if (!target?.closest('[data-drag-surface="true"]') || target.closest(editable)) return;
    pointers.add(event.pointerId);
    doc.documentElement.setAttribute("data-studio-dragging", "true");
  };
  const clear = () => { pointers.clear(); doc.documentElement.removeAttribute("data-studio-dragging"); };
  const up = (event: PointerEvent) => { pointers.delete(event.pointerId); if (!pointers.size) clear(); };
  const selection = (event: Event) => { if (pointers.size) event.preventDefault(); };
  const drag = (event: Event) => { if (targetElement(event)?.closest('[data-drag-surface="true"]')) event.preventDefault(); };
  doc.addEventListener("pointerdown", down, true);
  doc.addEventListener("pointerup", up, true);
  doc.addEventListener("pointercancel", up, true);
  doc.addEventListener("selectstart", selection);
  doc.addEventListener("dragstart", drag);
  win.addEventListener("blur", clear);
  return () => {
    clear();
    doc.removeEventListener("pointerdown", down, true);
    doc.removeEventListener("pointerup", up, true);
    doc.removeEventListener("pointercancel", up, true);
    doc.removeEventListener("selectstart", selection);
    doc.removeEventListener("dragstart", drag);
    win.removeEventListener("blur", clear);
  };
}
