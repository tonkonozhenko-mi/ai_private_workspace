import { FormEvent, useEffect, useState } from "react";

import {
  addUserProfileFact,
  deleteUserProfileFact,
  getUserProfile,
  pinUserProfileFact,
  suggestUserProfileFacts,
} from "../api/client";
import type { ProfileFactCandidate, UserProfileFact } from "../api/types";

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

  // Review-first suggestions: the model proposes facts; you approve each one.
  const [suggestOpen, setSuggestOpen] = useState(false);
  const [suggestText, setSuggestText] = useState("");
  const [suggesting, setSuggesting] = useState(false);
  const [candidates, setCandidates] = useState<ProfileFactCandidate[] | null>(null);

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

  const findSuggestions = async () => {
    const trimmed = suggestText.trim();
    if (!trimmed) return;
    setSuggesting(true);
    setError(null);
    try {
      const result = await suggestUserProfileFacts(trimmed);
      setCandidates(result.candidates);
    } catch (err) {
      setError(err instanceof Error ? err.message : "The local model couldn't suggest facts.");
    } finally {
      setSuggesting(false);
    }
  };

  const acceptCandidate = async (candidate: ProfileFactCandidate) => {
    await addUserProfileFact(candidate.text, candidate.category);
    setCandidates((current) => current?.filter((c) => c !== candidate) ?? null);
    await load();
  };

  const dismissCandidate = (candidate: ProfileFactCandidate) => {
    setCandidates((current) => current?.filter((c) => c !== candidate) ?? null);
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

      <div className="up-suggest">
        <button
          type="button"
          className="up-suggest-toggle"
          onClick={() => setSuggestOpen((v) => !v)}
        >
          {suggestOpen ? "▾" : "▸"} Suggest facts from a conversation
        </button>
        {suggestOpen ? (
          <div className="up-suggest-body">
            <p className="up-muted">
              Paste a recent chat (or a sentence about yourself). The local model proposes facts —
              nothing is saved until you keep it.
            </p>
            <textarea
              className="up-suggest-input"
              rows={4}
              value={suggestText}
              onChange={(e) => setSuggestText(e.target.value)}
              placeholder="Paste a conversation here…"
              maxLength={20000}
            />
            <button
              type="button"
              className="up-add-btn"
              onClick={() => void findSuggestions()}
              disabled={suggesting || !suggestText.trim()}
            >
              {suggesting ? "Reading…" : "Find facts"}
            </button>

            {candidates !== null ? (
              candidates.length === 0 ? (
                <p className="up-muted">No new facts found — nothing durable to remember here.</p>
              ) : (
                <ul className="up-list up-candidates">
                  {candidates.map((candidate, i) => (
                    <li key={`${candidate.text}-${i}`} className="up-item up-candidate">
                      <span className="up-cat">
                        {CATEGORY_LABELS[candidate.category] ?? candidate.category}
                      </span>
                      <span className="up-text">{candidate.text}</span>
                      <div className="up-actions">
                        <button
                          type="button"
                          className="up-keep"
                          onClick={() => void acceptCandidate(candidate)}
                        >
                          Keep
                        </button>
                        <button
                          type="button"
                          className="up-icon up-icon-danger"
                          title="Dismiss"
                          aria-label="Dismiss"
                          onClick={() => dismissCandidate(candidate)}
                        >
                          ✕
                        </button>
                      </div>
                    </li>
                  ))}
                </ul>
              )
            ) : null}
          </div>
        ) : null}
      </div>

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
