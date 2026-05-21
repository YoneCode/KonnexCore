/**
 * Wraps a state-setter in document.startViewTransition when available.
 * Falls back to immediate set on unsupported browsers.
 */
export function withViewTransition(fn: () => void): void {
  if (
    "startViewTransition" in document &&
    typeof document.startViewTransition === "function"
  ) {
    document.startViewTransition(fn);
  } else {
    fn();
  }
}
