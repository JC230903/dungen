import { useEffect, useState } from "react";
import type { TemplatesResponse } from "../api";
import { listTemplates } from "../api";

interface Props {
  onGenerate: (templateName: string, params: Record<string, string>) => void;
}

export default function TemplatesPanel({ onGenerate }: Props) {
  const [templates, setTemplates] = useState<TemplatesResponse>({});
  const [name, setName] = useState("");
  const [values, setValues] = useState<Record<string, string>>({});

  useEffect(() => {
    listTemplates().then((t) => {
      setTemplates(t);
      const first = Object.keys(t)[0];
      if (first) {
        setName(first);
        setValues(Object.fromEntries(t[first].fields.map((f) => [f.key, f.default])));
      }
    });
  }, []);

  const onPick = (n: string) => {
    setName(n);
    setValues(Object.fromEntries((templates[n]?.fields || []).map((f) => [f.key, f.default])));
  };

  const tpl = templates[name];

  return (
    <div className="panel">
      <p className="hint">Generate a starter diagram from a parameterized template.</p>
      <label className="field">
        <span>Template</span>
        <select value={name} onChange={(e) => onPick(e.target.value)}>
          {Object.keys(templates).map((n) => (
            <option key={n} value={n}>
              {n}
            </option>
          ))}
        </select>
      </label>
      {tpl && <p className="hint">{tpl.description}</p>}
      {tpl?.fields.map((f) => (
        <label className="field" key={f.key}>
          <span>{f.label}</span>
          <input
            value={values[f.key] ?? ""}
            placeholder={f.default}
            onChange={(e) => setValues((v) => ({ ...v, [f.key]: e.target.value }))}
          />
        </label>
      ))}
      <button className="btn btn-primary" disabled={!name} onClick={() => onGenerate(name, values)}>
        Generate diagram
      </button>
    </div>
  );
}
