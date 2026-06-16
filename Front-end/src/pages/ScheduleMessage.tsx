import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Card } from "../components/Card";
import { PageHeader } from "../components/PageHeader";
import { ClockIcon } from "../components/icons";
import {
  ApiError,
  getContacts,
  scheduleMessage,
} from "../services/api";
import type { Contact } from "../types";
import styles from "./ScheduleMessage.module.css";

interface FormState {
  contact_id: string;
  phone: string;
  scheduled_time: string;
  message: string;
}

const EMPTY_FORM: FormState = {
  contact_id: "",
  phone: "",
  scheduled_time: "",
  message: "",
};

function ScheduleMessage() {
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [loadingContacts, setLoadingContacts] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    getContacts()
      .then((items) => {
        if (active) setContacts(items);
      })
      .catch(() => {
        if (active) setContacts([]);
      })
      .finally(() => {
        if (active) setLoadingContacts(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const selectedContact = useMemo(
    () => contacts.find((contact) => contact.id === form.contact_id) ?? null,
    [contacts, form.contact_id]
  );

  function selectContact(contactId: string) {
    const contact = contacts.find((item) => item.id === contactId);
    setForm((current) => ({
      ...current,
      contact_id: contactId,
      phone: contact?.phone_number ?? current.phone,
    }));
    setError(null);
    setSuccess(null);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSuccess(null);

    if (!form.phone.trim() || !form.message.trim() || !form.scheduled_time) {
      setError("Phone number, message, and scheduled time are required.");
      return;
    }

    setBusy(true);
    try {
      const result = await scheduleMessage({
        phone: form.phone.trim(),
        message: form.message.trim(),
        scheduled_time: form.scheduled_time,
        contact_id: form.contact_id || null,
      });
      setSuccess(
        `Message scheduled for ${formatTime(result.scheduled_time)}.`
      );
      setForm(EMPTY_FORM);
    } catch (err) {
      setError(messageFor(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Schedule Message"
        subtitle="Write one message, choose who should receive it, and pick when n8n should send it."
      />

      <Card
        title="New scheduled message"
        subtitle="The time is saved using the Europe/Istanbul timezone."
      >
        <form className={styles.form} onSubmit={handleSubmit}>
          <div className={styles.fieldGrid}>
            <label className={styles.field}>
              <span>Saved contact</span>
              <select
                value={form.contact_id}
                disabled={loadingContacts}
                onChange={(event) => selectContact(event.target.value)}
              >
                <option value="">
                  {loadingContacts ? "Loading contacts..." : "Use manual phone"}
                </option>
                {contacts.map((contact) => (
                  <option key={contact.id} value={contact.id}>
                    {contact.name} ({formatPhone(contact.phone_number)})
                  </option>
                ))}
              </select>
            </label>

            <label className={styles.field}>
              <span>Phone number</span>
              <input
                type="tel"
                required
                value={form.phone}
                placeholder="+90 555 123 4567"
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    contact_id: "",
                    phone: event.target.value,
                  }))
                }
              />
            </label>
          </div>

          {selectedContact && (
            <p className={styles.selected}>
              Sending to <strong>{selectedContact.name}</strong>.
            </p>
          )}

          <label className={styles.field}>
            <span>Send at</span>
            <input
              type="datetime-local"
              required
              min={localDateTimeNow()}
              value={form.scheduled_time}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  scheduled_time: event.target.value,
                }))
              }
            />
          </label>

          <label className={styles.field}>
            <span>Message</span>
            <textarea
              required
              rows={6}
              value={form.message}
              placeholder="Write the message to send later..."
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  message: event.target.value,
                }))
              }
            />
          </label>

          {error && <p className={styles.error}>{error}</p>}
          {success && <p className={styles.success}>{success}</p>}

          <div className={styles.actions}>
            <button
              type="button"
              className={styles.secondary}
              disabled={busy}
              onClick={() => {
                setForm(EMPTY_FORM);
                setError(null);
                setSuccess(null);
              }}
            >
              Clear
            </button>
            <button className={styles.primary} disabled={busy}>
              <ClockIcon size={16} />
              {busy ? "Scheduling..." : "Schedule message"}
            </button>
          </div>
        </form>
      </Card>
    </>
  );
}

function localDateTimeNow(): string {
  const now = new Date();
  now.setSeconds(0, 0);
  const offset = now.getTimezoneOffset() * 60000;
  return new Date(now.getTime() - offset).toISOString().slice(0, 16);
}

function formatPhone(value: string): string {
  return value.startsWith("+") ? value : `+${value}`;
}

function formatTime(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function messageFor(err: unknown): string {
  if (err instanceof ApiError) return err.message;
  return "Could not schedule the message. Please try again.";
}

export default ScheduleMessage;
