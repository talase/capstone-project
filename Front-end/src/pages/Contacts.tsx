import {
  useCallback,
  useEffect,
  useState,
  type FormEvent,
} from "react";
import { Badge } from "../components/Badge";
import { Card } from "../components/Card";
import { Modal } from "../components/Modal";
import { PageHeader } from "../components/PageHeader";
import { UserIcon } from "../components/icons";
import {
  ApiError,
  createContact,
  deleteContact,
  getContacts,
  updateContact,
} from "../services/api";
import type { Contact, ContactInput } from "../types";
import styles from "./Contacts.module.css";

interface ContactForm {
  name: string;
  phone_number: string;
  relationship_type: string;
  notes: string;
  can_receive_requested_messages: boolean;
  message_aliases: string;
}

const EMPTY_FORM: ContactForm = {
  name: "",
  phone_number: "",
  relationship_type: "",
  notes: "",
  can_receive_requested_messages: false,
  message_aliases: "",
};

function Contacts() {
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editor, setEditor] = useState<"create" | "edit" | null>(null);
  const [editingContact, setEditingContact] = useState<Contact | null>(null);
  const [form, setForm] = useState<ContactForm>(EMPTY_FORM);
  const [deleteTarget, setDeleteTarget] = useState<Contact | null>(null);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const refreshContacts = useCallback(async () => {
    setRefreshing(true);
    setError(null);
    try {
      setContacts(await getContacts());
    } catch (err) {
      setError(messageFor(err));
    } finally {
      setRefreshing(false);
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    getContacts()
      .then((items) => {
        if (active) setContacts(items);
      })
      .catch((err) => {
        if (active) setError(messageFor(err));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  function openCreate() {
    setForm(EMPTY_FORM);
    setEditingContact(null);
    setActionError(null);
    setEditor("create");
  }

  function openEdit(contact: Contact) {
    setForm({
      name: contact.name,
      phone_number: contact.phone_number,
      relationship_type: contact.relationship_type ?? "",
      notes: contact.notes ?? "",
      can_receive_requested_messages:
        contact.can_receive_requested_messages,
      message_aliases: contact.message_aliases?.join(", ") ?? "",
    });
    setEditingContact(contact);
    setActionError(null);
    setEditor("edit");
  }

  function closeEditor() {
    if (busy) return;
    setEditor(null);
    setEditingContact(null);
    setActionError(null);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const payload = toContactInput(form);
    if (!payload.name || !payload.phone_number) {
      setActionError("Name and phone number are required.");
      return;
    }

    setBusy(true);
    setActionError(null);
    try {
      if (editor === "edit" && editingContact) {
        const updated = await updateContact(editingContact.id, payload);
        setContacts((current) =>
          current.map((contact) =>
            contact.id === updated.id ? updated : contact
          )
        );
      } else {
        const created = await createContact(payload);
        setContacts((current) => [created, ...current]);
      }
      closeEditorAfterSave();
    } catch (err) {
      setActionError(messageFor(err));
    } finally {
      setBusy(false);
    }
  }

  function closeEditorAfterSave() {
    setEditor(null);
    setEditingContact(null);
    setForm(EMPTY_FORM);
  }

  async function handleDelete() {
    if (!deleteTarget) return;
    setBusy(true);
    setActionError(null);
    try {
      await deleteContact(deleteTarget.id);
      setContacts((current) =>
        current.filter((contact) => contact.id !== deleteTarget.id)
      );
      setDeleteTarget(null);
    } catch (err) {
      setActionError(messageFor(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Contacts"
        subtitle="Manage the people the assistant can identify and contact on your behalf."
        action={
          <button className={styles.primary} onClick={openCreate}>
            Add contact
          </button>
        }
      />

      <Card
        title="Saved contacts"
        subtitle={`${contacts.length} contact${contacts.length === 1 ? "" : "s"}`}
        action={
          <button
            className={styles.secondary}
            onClick={() => void refreshContacts()}
            disabled={refreshing}
          >
            {refreshing ? "Refreshing..." : "Refresh"}
          </button>
        }
      >
        {loading ? (
          <p className={styles.muted}>Loading contacts...</p>
        ) : error ? (
          <p className={styles.error}>{error}</p>
        ) : contacts.length === 0 ? (
          <div className={styles.empty}>
            <span className={styles.emptyIcon}>
              <UserIcon size={24} />
            </span>
            <strong>No contacts yet</strong>
            <span>Add someone the assistant is allowed to recognize.</span>
          </div>
        ) : (
          <div className={styles.grid}>
            {contacts.map((contact) => (
              <article key={contact.id} className={styles.contact}>
                <div className={styles.contactHead}>
                  <span className={styles.avatar}>
                    {contact.name.trim().charAt(0).toUpperCase() || "?"}
                  </span>
                  <div className={styles.identity}>
                    <h2>{contact.name}</h2>
                    <p>{formatPhone(contact.phone_number)}</p>
                  </div>
                  {contact.relationship_type && (
                    <Badge dot={false}>{contact.relationship_type}</Badge>
                  )}
                </div>

                <div className={styles.contactBody}>
                  <div className={styles.permission}>
                    <span
                      title="Whether the assistant may send this contact a message when another contact asks it to forward one."
                    >
                      Forward messages requested by others
                    </span>
                    <Badge
                      tone={
                        contact.can_receive_requested_messages
                          ? "low"
                          : "neutral"
                      }
                    >
                      {contact.can_receive_requested_messages
                        ? "Allowed"
                        : "Not allowed"}
                    </Badge>
                  </div>

                  {contact.message_aliases &&
                    contact.message_aliases.length > 0 && (
                      <div className={styles.aliases}>
                        <span className={styles.label}>Aliases</span>
                        <div className={styles.aliasList}>
                          {contact.message_aliases.map((alias) => (
                            <span key={alias}>{alias}</span>
                          ))}
                        </div>
                      </div>
                    )}

                  {contact.notes && (
                    <p className={styles.notes}>{contact.notes}</p>
                  )}
                </div>

                <div className={styles.contactActions}>
                  <button
                    className={styles.secondary}
                    onClick={() => openEdit(contact)}
                  >
                    Edit
                  </button>
                  <button
                    className={styles.delete}
                    onClick={() => {
                      setActionError(null);
                      setDeleteTarget(contact);
                    }}
                  >
                    Delete
                  </button>
                </div>
              </article>
            ))}
          </div>
        )}
      </Card>

      {editor && (
        <Modal
          title={editor === "create" ? "Add contact" : "Edit contact"}
          onClose={closeEditor}
        >
          <form className={styles.form} onSubmit={handleSubmit}>
            <div className={styles.fieldGrid}>
              <label className={styles.field}>
                <span>Name</span>
                <input
                  value={form.name}
                  autoFocus
                  required
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      name: event.target.value,
                    }))
                  }
                />
              </label>
              <label className={styles.field}>
                <span>Phone number</span>
                <input
                  value={form.phone_number}
                  type="tel"
                  required
                  placeholder="+90 555 123 4567"
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      phone_number: event.target.value,
                    }))
                  }
                />
              </label>
            </div>

            <label className={styles.field}>
              <span>Relationship</span>
              <input
                value={form.relationship_type}
                placeholder="Friend, family, colleague..."
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    relationship_type: event.target.value,
                  }))
                }
              />
            </label>

            <label className={styles.field}>
              <span>Message aliases</span>
              <input
                value={form.message_aliases}
                placeholder="Mom, Mother, Anne"
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    message_aliases: event.target.value,
                  }))
                }
              />
              <small>Separate aliases with commas.</small>
            </label>

            <label className={styles.field}>
              <span>Notes</span>
              <textarea
                value={form.notes}
                rows={3}
                placeholder="Optional context about this contact"
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    notes: event.target.value,
                  }))
                }
              />
            </label>

            <label className={styles.toggle}>
              <input
                type="checkbox"
                checked={form.can_receive_requested_messages}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    can_receive_requested_messages: event.target.checked,
                  }))
                }
              />
              <span>
                <strong>Allow messages requested by other contacts</strong>
                <small>
                  The assistant may send this person a message when another
                  contact asks it to forward one.
                </small>
              </span>
            </label>

            {actionError && <p className={styles.error}>{actionError}</p>}

            <div className={styles.dialogActions}>
              <button
                type="button"
                className={styles.secondary}
                onClick={closeEditor}
                disabled={busy}
              >
                Cancel
              </button>
              <button className={styles.primary} disabled={busy}>
                {busy
                  ? "Saving..."
                  : editor === "create"
                    ? "Create contact"
                    : "Save changes"}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {deleteTarget && (
        <Modal
          title="Delete contact"
          onClose={() => !busy && setDeleteTarget(null)}
        >
          <p className={styles.dialogText}>
            Permanently delete <strong>{deleteTarget.name}</strong>? The
            assistant will no longer recognize this contact.
          </p>
          {actionError && <p className={styles.error}>{actionError}</p>}
          <div className={styles.dialogActions}>
            <button
              className={styles.secondary}
              onClick={() => setDeleteTarget(null)}
              disabled={busy}
            >
              Cancel
            </button>
            <button
              className={styles.deleteSolid}
              onClick={() => void handleDelete()}
              disabled={busy}
            >
              {busy ? "Deleting..." : "Delete contact"}
            </button>
          </div>
        </Modal>
      )}
    </>
  );
}

function toContactInput(form: ContactForm): ContactInput {
  const aliases = Array.from(
    new Set(
      form.message_aliases
        .split(",")
        .map((alias) => alias.trim())
        .filter(Boolean)
    )
  );

  return {
    name: form.name.trim(),
    phone_number: form.phone_number.trim(),
    relationship_type: form.relationship_type.trim() || null,
    notes: form.notes.trim() || null,
    can_receive_requested_messages: form.can_receive_requested_messages,
    message_aliases: aliases.length > 0 ? aliases : null,
  };
}

function messageFor(err: unknown): string {
  if (err instanceof ApiError) return err.message;
  return "Something went wrong. Please try again.";
}

function formatPhone(value: string): string {
  return value.startsWith("+") ? value : `+${value}`;
}

export default Contacts;
