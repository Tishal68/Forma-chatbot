import { useEffect, useState, useRef } from "react";
import { Download, Upload, Archive, Tag, Check, Filter } from "lucide-react";
import { api } from "../services/api";

type Memory = {
  id: number;
  key: string;
  value: string;
  category?: string;
  confidence?: number;
  created_at?: string;
  updated_at?: string;
};

type Profile = {
  memory_enabled: boolean;
  preferences: Record<string, string>;
  custom_instructions: string;
  memories: Memory[];
};

const fields = [
  ["name", "Preferred name"],
  ["language", "Preferred language"],
  ["tone", "Tone", "Friendly, professional, casual…"],
  ["response_length", "Response length", "Concise, detailed, adapt to the task…"],
  ["explanation_level", "Explanation level", "Beginner, college student, advanced…"],
  ["interests", "Interests", "Optional interests that help tailor examples"],
];

const categories = [
  { id: "all", label: "All" },
  { id: "profile", label: "Profile" },
  { id: "project", label: "Project" },
  { id: "episodic", label: "Episodic" },
  { id: "semantic", label: "Semantic" },
  { id: "conversation", label: "Conversation" },
];

export function PersonalizationSettings() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [memory, setMemory] = useState({ key: "", value: "", category: "profile" });
  const [editingId, setEditingId] = useState<number | null>(null);
  const [confirmClear, setConfirmClear] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState("all");
  const importFileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    let current = true;
    api<Profile>("/personalization").then(data => {
      if (current) setProfile(data);
    }).catch(e => { if (current) setError(e.message); });
    return () => { current = false; };
  }, []);

  async function mutate(path: string, method: string, body?: unknown, success = "Saved.") {
    setPending(true); setError(""); setNotice("");
    try {
      const updated = await api<Profile>("/personalization" + path, {
        method, ...(body === undefined ? {} : { body: JSON.stringify(body) }),
      });
      setProfile(updated); setNotice(success);
      return true;
    } catch (e) { setError((e as Error).message); return false; }
    finally { setPending(false); }
  }

  async function handleExportMemories() {
    setError(""); setNotice("");
    try {
      const res = await fetch("/api/personalization/export");
      if (!res.ok) throw new Error("Failed to export memories.");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `forma_memories_${new Date().toISOString().slice(0, 10)}.json`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      setNotice("Memories exported successfully.");
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function handleImportMemories(file: File) {
    setError(""); setNotice(""); setPending(true);
    try {
      const text = await file.text();
      const parsed = JSON.parse(text);
      const res = await api<{ status: string; imported: number; skipped: number }>(
        "/personalization/import",
        {
          method: "POST",
          body: JSON.stringify(parsed),
        }
      );
      setNotice(`Import complete: ${res.imported} memories imported, ${res.skipped} skipped.`);
      const updated = await api<Profile>("/personalization");
      setProfile(updated);
    } catch (e) {
      setError("Import failed: " + (e as Error).message);
    } finally {
      setPending(false);
    }
  }

  async function handleWorkspaceBackup() {
    setError(""); setNotice("");
    try {
      const res = await fetch("/api/backup");
      if (!res.ok) throw new Error("Failed to export workspace backup.");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `forma_full_backup_${new Date().toISOString().slice(0, 10)}.json`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      setNotice("Complete workspace backup downloaded.");
    } catch (e) {
      setError((e as Error).message);
    }
  }

  const filteredMemories = profile?.memories.filter(item =>
    selectedCategory === "all" || (item.category || "profile") === selectedCategory
  ) || [];

  return <div className="tab-pane personalization-pane">
    <p>Saved preferences and memories apply across chats in this browser. Clearing cookies changes your identity. Chat history is separate from saved personalization.</p>
    {error && <p role="alert" className="personalization-error">{error}</p>}
    {notice && <p role="status">{notice}</p>}
    {!profile ? <p>{error ? "Close and reopen Personalization to retry." : "Loading personalization…"}</p> : <>
      <form onSubmit={async e => {
        e.preventDefault();
        await mutate("", "PATCH", {
          memory_enabled: profile.memory_enabled,
          preferences: profile.preferences,
          custom_instructions: profile.custom_instructions,
        }, "Preferences saved. They will apply to your next message.");
      }}>
        <fieldset disabled={pending}>
          <label className="personalization-toggle">
            <input type="checkbox" checked={profile.memory_enabled}
              onChange={e => setProfile({ ...profile, memory_enabled: e.target.checked })} />
            Use and save personalization
          </label>
          <p className="setting-help">Turn off and save to stop using or capturing preferences and memories. Existing chat messages remain part of their conversations.</p>
          <div className="personalization-fields">
            {fields.map(([key, label, placeholder]) => <label className="setting" key={key}>
              {label}
              <input maxLength={200} placeholder={placeholder} value={profile.preferences[key] || ""}
                onChange={e => setProfile({ ...profile, preferences: { ...profile.preferences, [key]: e.target.value } })} />
            </label>)}
          </div>
          <label className="setting">Custom instructions
            <textarea aria-label="Custom instructions" maxLength={2000} rows={4} value={profile.custom_instructions}
              placeholder="How would you like Forma to respond?"
              onChange={e => setProfile({ ...profile, custom_instructions: e.target.value })} />
          </label>
          <button className="quiet" type="submit">Save preferences</button>
        </fieldset>
      </form>

      <div className="memory-section-header">
        <h3>Saved memories</h3>
        <div className="memory-toolbar">
          <input
            type="file"
            ref={importFileRef}
            style={{ display: "none" }}
            accept=".json,application/json"
            onChange={e => {
              if (e.target.files?.[0]) {
                handleImportMemories(e.target.files[0]);
                e.target.value = "";
              }
            }}
          />
          <button
            type="button"
            className="quiet small-btn"
            title="Export memories as JSON"
            onClick={handleExportMemories}
            disabled={pending}
          >
            <Download size={13} />
            <span>Export</span>
          </button>
          <button
            type="button"
            className="quiet small-btn"
            title="Import memories from JSON"
            onClick={() => importFileRef.current?.click()}
            disabled={pending}
          >
            <Upload size={13} />
            <span>Import</span>
          </button>
          <button
            type="button"
            className="quiet small-btn"
            title="Export full workspace data backup"
            onClick={handleWorkspaceBackup}
            disabled={pending}
          >
            <Archive size={13} />
            <span>Full Backup</span>
          </button>
        </div>
      </div>

      <p className="setting-help">Say “Remember this: my project name is Cedar”, or add a fact below. Use the same label to update a fact. Memories are categorized and isolated to your private session. Avoid storing credentials.</p>

      {/* Category Filter Pills */}
      <div className="memory-category-filter">
        {categories.map(c => (
          <button
            key={c.id}
            type="button"
            className={`memory-filter-pill ${selectedCategory === c.id ? "active" : ""}`}
            onClick={() => setSelectedCategory(c.id)}
          >
            {c.label}
            {c.id !== "all" && profile.memories.filter(m => (m.category || "profile") === c.id).length > 0 && (
              <span className="pill-count">
                {profile.memories.filter(m => (m.category || "profile") === c.id).length}
              </span>
            )}
          </button>
        ))}
      </div>

      {!filteredMemories.length && (
        <p className="no-memories">
          {profile.memories.length === 0
            ? "No saved memories yet."
            : `No memories in the "${selectedCategory}" category.`}
        </p>
      )}

      <ul className="memory-list">
        {filteredMemories.map(item => <li key={item.id}>
          <div className="memory-item-top">
            <strong>{item.key}</strong>
            <span className={`memory-category-tag category-${item.category || "profile"}`}>
              {item.category || "profile"}
            </span>
          </div>
          <p>{item.value}</p>
          <div className="memory-actions">
            <button type="button" className="quiet" disabled={pending} aria-label={`Edit memory ${item.key}`}
              onClick={() => {
                setEditingId(item.id);
                setMemory({
                  key: item.key,
                  value: item.value,
                  category: item.category || "profile",
                });
              }}>Edit</button>
            <button type="button" className="quiet" disabled={pending} aria-label={`Delete memory ${item.key}`}
              onClick={async () => {
                if (await mutate(`/memories/${item.id}`, "DELETE", undefined, "Memory deleted.")) {
                  if (editingId === item.id) {
                    setEditingId(null);
                    setMemory({ key: "", value: "", category: "profile" });
                  }
                }
              }}>Delete</button>
          </div>
        </li>)}
      </ul>

      <form onSubmit={async e => {
        e.preventDefault();
        if (await mutate(editingId === null ? "/memories" : `/memories/${editingId}`,
          editingId === null ? "POST" : "PATCH", memory, "Memory saved.")) {
          setEditingId(null); setMemory({ key: "", value: "", category: "profile" });
        }
      }}>
        <fieldset disabled={pending}>
          <div className="memory-form-row">
            <label className="setting flex-1">Memory label
              <input required maxLength={80} value={memory.key} placeholder="Project name"
                onChange={e => setMemory({ ...memory, key: e.target.value })} />
            </label>
            <label className="setting category-select-setting">Category
              <select
                value={memory.category}
                onChange={e => setMemory({ ...memory, category: e.target.value })}
                className="category-select"
              >
                <option value="profile">Profile</option>
                <option value="project">Project</option>
                <option value="episodic">Episodic</option>
                <option value="semantic">Semantic</option>
              </select>
            </label>
          </div>
          <label className="setting">Memory fact
            <textarea aria-label="Memory fact" required maxLength={500} rows={2} value={memory.value} placeholder="My project name is Cedar."
              onChange={e => setMemory({ ...memory, value: e.target.value })} />
          </label>
          <div className="memory-actions">
            <button type="submit" className="quiet">{editingId === null ? "Add memory" : "Save memory"}</button>
            {editingId !== null && <button type="button" className="quiet" onClick={() => {
              setEditingId(null); setMemory({ key: "", value: "", category: "profile" });
            }}>Cancel editing</button>}
          </div>
        </fieldset>
      </form>

      <div className="danger-zone">
        <p>Forget all saved preferences, custom instructions and memories. This keeps your conversations.</p>
        {!confirmClear ? <button className="danger-button" disabled={pending} onClick={() => setConfirmClear(true)}>Forget all personalization</button> :
          <div className="memory-actions"><button className="danger-button" disabled={pending} onClick={async () => {
            if (await mutate("", "DELETE", undefined, "Personalization cleared.")) {
              setConfirmClear(false); setEditingId(null); setMemory({ key: "", value: "", category: "profile" });
            }
          }}>Confirm forget personalization</button>
          <button className="quiet" disabled={pending} onClick={() => setConfirmClear(false)}>Cancel</button></div>}
      </div>
    </>}
  </div>;
}
