import { useEffect, useState, type RefObject } from "react";
import { Platform, type ScrollView } from "react-native";

/** Refresh only an idle, saved workspace; never discard a prompt or drawing. */
export default function usePullToRefresh(ref: RefObject<ScrollView | null>, enabled: boolean) {
  const [distance, setDistance] = useState(0);
  useEffect(() => {
    if (Platform.OS !== "web") return;
    const node = ref.current?.getScrollableNode() as HTMLElement | undefined;
    if (!node?.addEventListener) return;
    let start: { x: number; y: number } | null = null;
    let pulled = 0;
    const begin = (event: TouchEvent) => {
      const target = event.target as Element;
      if (!enabled || node.scrollTop > 0 || event.touches.length !== 1 || target.closest('input, textarea, button, [role="button"], [aria-label="Drawing canvas"], [aria-label="Label editing canvas"]')) return;
      start = { x: event.touches[0].clientX, y: event.touches[0].clientY };
    };
    const move = (event: TouchEvent) => {
      if (!start || event.touches.length !== 1) return;
      const touch = event.touches[0];
      const vertical = touch.clientY - start.y;
      if (Math.abs(touch.clientX - start.x) > Math.abs(vertical) || node.scrollTop > 0) { start = null; pulled = 0; setDistance(0); return; }
      pulled = Math.max(0, Math.min(100, vertical));
      if (pulled > 8 && event.cancelable) event.preventDefault();
      setDistance(pulled);
    };
    const finish = () => { const refresh = Boolean(start && pulled >= 72 && enabled); start = null; pulled = 0; setDistance(0); if (refresh) window.location.reload(); };
    const cancel = () => { start = null; pulled = 0; setDistance(0); };
    const original = node.style.overscrollBehaviorY;
    node.style.overscrollBehaviorY = "contain";
    node.addEventListener("touchstart", begin, { passive: true });
    node.addEventListener("touchmove", move, { passive: false });
    node.addEventListener("touchend", finish);
    node.addEventListener("touchcancel", cancel);
    return () => { node.style.overscrollBehaviorY = original; node.removeEventListener("touchstart", begin); node.removeEventListener("touchmove", move); node.removeEventListener("touchend", finish); node.removeEventListener("touchcancel", cancel); };
  }, [ref, enabled]);
  return distance;
}
