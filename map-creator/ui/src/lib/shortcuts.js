// Customizable keyboard shortcut dispatcher driven by config/app.toml [shortcuts]

export function attachShortcuts(getShortcuts, handlers) {
  let chordPrefix = null;
  let chordTimer = null;

  function onKeyDown(e) {
    const tag = (e.target && e.target.tagName) || '';
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || e.target?.isContentEditable) {
      return;
    }

    const shortcuts = getShortcuts() || {};
    const combo = formatCombo(e);

    // Check direct combo match (e.g., Ctrl+Shift+V)
    for (const [action, binding] of Object.entries(shortcuts)) {
      if (binding.toLowerCase() === combo.toLowerCase() && handlers[action]) {
        e.preventDefault();
        handlers[action]();
        return;
      }
    }

    // Check 2-key chord (e.g., "g p")
    if (!e.ctrlKey && !e.metaKey && !e.altKey && e.key.length === 1) {
      const k = e.key.toLowerCase();
      if (chordPrefix) {
        const chord = `${chordPrefix} ${k}`;
        clearTimeout(chordTimer);
        chordPrefix = null;
        for (const [action, binding] of Object.entries(shortcuts)) {
          if (binding.toLowerCase() === chord && handlers[action]) {
            e.preventDefault();
            handlers[action]();
            return;
          }
        }
      } else {
        const startsChord = Object.values(shortcuts).some((b) =>
          b.toLowerCase().startsWith(`${k} `)
        );
        if (startsChord) {
          chordPrefix = k;
          chordTimer = setTimeout(() => {
            chordPrefix = null;
          }, 900);
        }
      }
    }
  }

  window.addEventListener('keydown', onKeyDown);
  return () => window.removeEventListener('keydown', onKeyDown);
}

function formatCombo(e) {
  const parts = [];
  if (e.ctrlKey || e.metaKey) parts.push('Ctrl');
  if (e.shiftKey) parts.push('Shift');
  if (e.altKey) parts.push('Alt');
  if (!['Control', 'Shift', 'Alt', 'Meta'].includes(e.key)) {
    parts.push(e.key.length === 1 ? e.key.toUpperCase() : e.key);
  }
  return parts.join('+');
}
