export function ChatPanelPlaceholder() {
  return (
    <button
      type="button"
      disabled
      title="Research assistant coming soon"
      className="ml-1 cursor-not-allowed rounded-lg border border-border-soft px-3 py-2 text-sm font-medium text-ink-500 opacity-60"
      aria-disabled="true"
    >
      Assistant
    </button>
  );
}
