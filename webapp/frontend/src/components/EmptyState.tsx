import { useEffect, useRef, useState } from "react";
import { listSamples } from "../api";

interface Props {
  onBlank: () => void;
  onSample: (name: string) => void;
  onUpload: (file: File) => void;
}

export default function EmptyState({ onBlank, onSample, onUpload }: Props) {
  const [samples, setSamples] = useState<string[]>([]);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    listSamples().then(setSamples).catch(() => setSamples([]));
  }, []);

  return (
    <div className="empty-state">
      <div className="empty-card">
        <h2>Start a diagram</h2>
        <p className="hint">Pick a starting point — you can switch approaches any time.</p>

        <div className="empty-actions">
          <button className="btn btn-primary" onClick={onBlank}>
            + Blank canvas
          </button>
          <button className="btn" onClick={() => fileRef.current?.click()}>
            Upload .xlsx
          </button>
          <input
            ref={fileRef}
            type="file"
            accept=".xlsx"
            hidden
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) onUpload(f);
              e.target.value = "";
            }}
          />
        </div>

        {samples.length > 0 && (
          <label className="field">
            <span>Or load a sample workbook</span>
            <select
              defaultValue=""
              onChange={(e) => {
                if (e.target.value) onSample(e.target.value);
                e.target.value = "";
              }}
            >
              <option value="" disabled>
                Choose a sample…
              </option>
              {samples.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </label>
        )}

        <p className="hint empty-tip">
          Once a diagram's open, the sidebar also has Templates (parameterized generators) and
          Outline (turn indented text into a mind map) as other starting points.
        </p>
      </div>
    </div>
  );
}
