/** Svelte action for modal dialogs: focus moves in on open, Tab stays inside, focus returns to the opener on close. */
export function focusTrap(node: HTMLElement) {
  const opener = document.activeElement as HTMLElement | null;
  node.focus();

  function onKeydown(e: KeyboardEvent) {
    if (e.key !== "Tab") return;
    const focusable = [
      ...node.querySelectorAll<HTMLElement>("a[href], button:not([disabled]), input:not([disabled]), select, [tabindex]:not([tabindex='-1'])"),
    ];
    const first = focusable[0];
    const last = focusable.at(-1);
    if (e.shiftKey && (document.activeElement === first || document.activeElement === node)) {
      e.preventDefault();
      last?.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first?.focus();
    }
  }

  node.addEventListener("keydown", onKeydown);
  return {
    destroy() {
      node.removeEventListener("keydown", onKeydown);
      if (opener?.isConnected) opener.focus();
    },
  };
}
