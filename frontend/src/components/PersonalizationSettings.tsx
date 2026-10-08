import { useEffect, useState } from "react";
import { api } from "../services/api";

type Memory = { id: number; key: string; value: string };
type Profile = {
  memory_enabled: boolean;
  preferences: Record<string, string>;
  custom_instructions: string;
  memories: Memory[];
};

const fields = [
  ["name", "Preferred name"], ["language", "Preferred language"],
  ["tone", "Tone", "Friendly, professional, casual…"],
  ["response_length", "Response length", "Concise, detailed, adapt to the task…"],
  ["explanation_level", "Explanation level", "Beginner, college student, advanced…"],
  ["interests", "Interests", "Optional interests that help tailor examples"],
];

export function PersonalizationSettings() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [memory, setMemory] = useState({ key: "", value: "" });
  const [editingId, setEditingId] = useState<number | null>(null);
  const [confirmClear, setConfirmClear] = useState(false);

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
      <h3>Saved memories</h3>
      <p className="setting-help">Say “Remember this: my project name is Cedar”, or add a fact below. Use the same label to update a fact. Memories are not extracted from uploaded files or assistant replies. Avoid storing credentials.</p>
      {!profile.memories.length && <p>No saved memories yet.</p>}
      <ul className="memory-list">
        {profile.memories.map(item => <li key={item.id}>
          <strong>{item.key}</strong><p>{item.value}</p>
          <div className="memory-actions">
            <button type="button" className="quiet" disabled={pending} aria-label={`Edit memory ${item.key}`}
              onClick={() => { setEditingId(item.id); setMemory({ key: item.key, value: item.value }); }}>Edit</button>
            <button type="button" className="quiet" disabled={pending} aria-label={`Delete memory ${item.key}`}
              onClick={async () => {
                if (await mutate(`/memories/${item.id}`, "DELETE", undefined, "Memory deleted.")) {
                  if (editingId === item.id) { setEditingId(null); setMemory({ key: "", value: "" }); }
                }
              }}>Delete</button>
          </div>
        </li>)}
      </ul>
      <form onSubmit={async e => {
        e.preventDefault();
        if (await mutate(editingId === null ? "/memories" : `/memories/${editingId}`,
          editingId === null ? "POST" : "PATCH", memory, "Memory saved.")) {
          setEditingId(null); setMemory({ key: "", value: "" });
        }
      }}>
        <fieldset disabled={pending}>
          <label className="setting">Memory label
            <input required maxLength={80} value={memory.key} placeholder="Project name"
              onChange={e => setMemory({ ...memory, key: e.target.value })} />
          </label>
          <label className="setting">Memory fact
            <textarea aria-label="Memory fact" required maxLength={500} rows={2} value={memory.value} placeholder="My project name is Cedar."
              onChange={e => setMemory({ ...memory, value: e.target.value })} />
          </label>
          <div className="memory-actions">
            <button type="submit" className="quiet">{editingId === null ? "Add memory" : "Save memory"}</button>
            {editingId !== null && <button type="button" className="quiet" onClick={() => {
              setEditingId(null); setMemory({ key: "", value: "" });
            }}>Cancel editing</button>}
          </div>
        </fieldset>
      </form>
      <div className="danger-zone">
        <p>Forget all saved preferences, custom instructions and memories. This keeps your conversations.</p>
        {!confirmClear ? <button className="danger-button" disabled={pending} onClick={() => setConfirmClear(true)}>Forget all personalization</button> :
          <div className="memory-actions"><button className="danger-button" disabled={pending} onClick={async () => {
            if (await mutate("", "DELETE", undefined, "Personalization cleared.")) {
              setConfirmClear(false); setEditingId(null); setMemory({ key: "", value: "" });
            }
          }}>Confirm forget personalization</button>
          <button className="quiet" disabled={pending} onClick={() => setConfirmClear(false)}>Cancel</button></div>}
      </div>
    </>}
  </div>;
}
