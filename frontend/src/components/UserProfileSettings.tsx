import { FormEvent, useEffect, useState } from "react";

import {
  addUserProfileFact,
  deleteUserProfileFact,
  getUserProfile,
  pinUserProfileFact,
} from "../api/client";
import type { UserProfileFact } from "../api/types";

const CATEGORY_LABELS: Record<string, string> = {
  role: "Role",
  preference: "Preference",
  style: "Style",
  context: "Context",
  fact: "Fact",
};

const PLACEHOLDER_BY_CATEGORY: Record<string, string> = {
  role: "e.g. I'm a DevOps engineer",
  preference: "e.g. Keep answers concise; show commands",
  style: "e.g. Answer in Russian",
  context: "e.g. We call production 'prd'",
  fact: "e.g. I mostly work with Terragrunt",
};

export function UserProfileSettings() {
  const [facts, setFacts] = useState<UserProfileFact[]>([]);
  const [categories, setCategories] = useState<string[]>(["fact"]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [text, setText] = useState("");
  const [category, setCategory] = useState("fact");
  const [saving, setSaving] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const result = await getUserProfile();
      setFacts(result.facts);
      if (result.categories.length > 0) setCategories(result.categories);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load your profile.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const add = async (event: FormEvent) => {
    event.preventDefault();
    const trimmed = text.trim();
    if (!trimmed) return;
    setSaving(true);
    try {
      await addUserProfileFact(trimmed, category);
      setText("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save that.");
    } finally {
      setSaving(false);
    }
  };

  const remove = async (id: string) => {
    await deleteUserProfileFact(id);
    setFacts((current) => current.filter((f) => f.id !== id));
  };

  const togglePin = async (fact: UserProfileFact) => {
    const updated = await pinUserProfileFact(fact.id, !fact.pinned);
    setFacts((current) => current.map((f) => (f.id === fact.id ? updated : f)));
  };

  return (
    <section className="panel settings-clean-card up-card">
      <header className="settings-clean-card-head">
        <div>
          <p className="eyebrow">About you</p>
          <h3>What the assistant remembers about you</h3>
        </div>
      </header>
      <p className="settings-clean-card-intro">
        A few stable facts and preferences — who you are, how you like answers — applied to every
        project, in Ask and the Investigator. It stays on your computer and you control every line.
      </p>

      {error ? <p className="up-error">{error}</p> : null}

      <form className="up-add" onSubmit={add}>
        <div className="up-add-row">
          <select value={category} onChange={(e) => setCategory(e.target.value)} className="up-select">
            {categories.map((c) => (
              <option key={c} value={c}>
                {CATEGORY_LABELS[c] ?? c}
              </option>
            ))}
          </select>
          <input
            className="up-input"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={PLACEHOLDER_BY_CATEGORY[category] ?? "Add a fact about yourself"}
            maxLength={600}
          />
          <button type="submit" className="up-add-btn" disabled={saving || !text.trim()}>
            {saving ? "Adding…" : "Add"}
          </button>
        </div>
      </form>

      {loading ? (
        <p className="up-muted">Loading…</p>
      ) : facts.length === 0 ? (
        <p className="up-muted">
          Nothing yet. Add things like your role, the language to answer in, or conventions your team
          uses.
        </p>
      ) : (
        <ul className="up-list">
          {facts.map((fact) => (
            <li key={fact.id} className={`up-item${fact.pinned ? " is-pinned" : ""}`}>
              <span className="up-cat">{CATEGORY_LABELS[fact.category] ?? fact.category}</span>
              <span className="up-text">{fact.text}</span>
              <div className="up-actions">
                <button
                  type="button"
                  className="up-icon"
                  title={fact.pinned ? "Unpin" : "Pin (always applied)"}
                  aria-label={fact.pinned ? "Unpin" : "Pin"}
                  onClick={() => void togglePin(fact)}
                >
                  {fact.pinned ? "★" : "☆"}
                </button>
                <button
                  type="button"
                  className="up-icon up-icon-danger"
                  title="Delete"
                  aria-label="Delete"
                  onClick={() => void remove(fact.id)}
                >
                  ✕
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
