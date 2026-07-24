import { useEffect, useState } from "react";

interface Props {
  rulesText: string;
  onApply: (rulesText: string) => void;
}

const EXAMPLE = "lifecycle=active: fill=#D6F5D6, stroke=#2A7D46\ncriticality=high: stroke=#B3261E";

export default function StyleRulesPanel({ rulesText, onApply }: Props) {
  const [text, setText] = useState(rulesText);

  useEffect(() => setText(rulesText), [rulesText]);

  return (
    <div className="panel">
      <p className="hint">
        One rule per line: <code>metadata_key=value: fill=#hex, stroke=#hex</code>. Rules are a display
        overlay only — they never change the shape's stored colors.
      </p>
      <label className="field">
        <span>Style rules</span>
        <textarea rows={8} value={text} placeholder={EXAMPLE} onChange={(e) => setText(e.target.value)} spellCheck={false} />
      </label>
      <button className="btn btn-primary" onClick={() => onApply(text)}>
        Apply rules
      </button>
    </div>
  );
}
