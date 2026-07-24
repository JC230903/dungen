import { useEffect, useRef, useState } from "react";
import { listSamples } from "../api";

interface Props {
  onUpload: (file: File) => void;
  onSample: (name: string) => void;
  title: string | null;
  loading: boolean;
  error: string | null;
}

export default function UploadBar({ onUpload, onSample, title, loading, error }: Props) {
  const [samples, setSamples] = useState<string[]>([]);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    listSamples().then(setSamples).catch(() => setSamples([]));
  }, []);

  return (
    <div className="topbar">
      <div className="brand">diagen</div>
      <button className="btn" onClick={() => fileRef.current?.click()} disabled={loading}>
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
      <select
        defaultValue=""
        disabled={loading}
        onChange={(e) => {
          if (e.target.value) onSample(e.target.value);
        }}
      >
        <option value="" disabled>
          Load a sample…
        </option>
        {samples.map((s) => (
          <option key={s} value={s}>
            {s}
          </option>
        ))}
      </select>
      <div className="title">{loading ? "Loading…" : title || ""}</div>
      {error && <div className="error">{error}</div>}
    </div>
  );
}
