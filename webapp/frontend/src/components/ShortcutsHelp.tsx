import { useState } from "react";

const SHORTCUTS: [string, string][] = [
  ["V", "Select tool"],
  ["C", "Connect tool (click two shapes to link them)"],
  ["Ctrl/Cmd + S", "Save the current diagram"],
  ["Ctrl/Cmd + Z", "Undo"],
  ["Ctrl/Cmd + Shift + Z, or Ctrl/Cmd + Y", "Redo"],
  ["Delete / Backspace", "Delete selected node(s) or edge"],
  ["Escape", "Clear selection"],
  ["Wheel / two-finger swipe", "Scroll the canvas"],
  ["Shift + wheel", "Scroll sideways"],
  ["Ctrl/Cmd + wheel, or pinch", "Zoom in and out"],
  ["Drag background, or middle-drag", "Pan the canvas"],
];

export default function ShortcutsHelp() {
  const [open, setOpen] = useState(false);
  return (
    <div className="shortcuts-help">
      <button className="btn" onClick={() => setOpen((o) => !o)} title="Keyboard shortcuts">
        ?
      </button>
      {open && (
        <>
          <div className="shortcuts-backdrop" onClick={() => setOpen(false)} />
          <div className="shortcuts-popover">
            <div className="shortcuts-title">Keyboard shortcuts</div>
            <table>
              <tbody>
                {SHORTCUTS.map(([key, desc]) => (
                  <tr key={key}>
                    <td className="shortcut-key">{key}</td>
                    <td>{desc}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
