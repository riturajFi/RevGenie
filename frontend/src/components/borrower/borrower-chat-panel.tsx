"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { sendBorrowerChatMessage } from "@/lib/api";
import { BorrowerChatMessage, BorrowerPortalLoginResponse } from "@/types/borrower";

const BORROWER_SESSION_STORAGE_KEY = "revgenie.borrower.session";

function nowIso() {
  return new Date().toISOString();
}

function makeMessage(
  actor: BorrowerChatMessage["actor"],
  text: string,
  idPrefix: string
): BorrowerChatMessage {
  return {
    id: `${idPrefix}_${Date.now()}_${Math.random().toString(16).slice(2, 8)}`,
    actor,
    text,
    created_at: nowIso(),
  };
}

export function BorrowerChatPanel() {
  const router = useRouter();
  const [session, setSession] = useState<BorrowerPortalLoginResponse | null>(null);
  const [workflowId, setWorkflowId] = useState<string>("");
  const [finalResult, setFinalResult] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [messages, setMessages] = useState<BorrowerChatMessage[]>([]);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const raw = sessionStorage.getItem(BORROWER_SESSION_STORAGE_KEY);
    if (!raw) {
      router.replace("/borrower/login");
      return;
    }

    try {
      const parsed = JSON.parse(raw) as BorrowerPortalLoginResponse;
      setSession(parsed);
      setWorkflowId(parsed.borrower_case.core.workflow_id);
      setMessages([
        makeMessage(
          "system",
          `Connected as ${parsed.borrower_profile.full_name}. You can now chat with the collections agent.`,
          "system"
        ),
      ]);
    } catch {
      sessionStorage.removeItem(BORROWER_SESSION_STORAGE_KEY);
      router.replace("/borrower/login");
    }
  }, [router]);

  const isConversationClosed = useMemo(() => Boolean(finalResult), [finalResult]);

  async function handleSend(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!session) return;

    const message = draft.trim();
    if (!message) return;

    setIsSending(true);
    setError(null);
    setDraft("");
    setMessages((current) => [...current, makeMessage("borrower", message, "borrower")]);

    try {
      const response = await sendBorrowerChatMessage({
        borrowerId: session.borrower_profile.borrower_id,
        workflowId,
        message,
      });
      setWorkflowId(response.workflow_id);
      setFinalResult(response.final_result);

      if (response.reply) {
        setMessages((current) => [...current, makeMessage("agent", response.reply ?? "", "agent")]);
      }
    } catch (sendError) {
      setError(sendError instanceof Error ? sendError.message : "Failed to send message");
    } finally {
      setIsSending(false);
    }
  }

  function handleLogout() {
    sessionStorage.removeItem(BORROWER_SESSION_STORAGE_KEY);
    router.push("/borrower/login");
  }

  if (!session) {
    return (
      <main className="login-shell">
        <section className="panel placeholder-panel">
          <h2>Chat</h2>
          <p>Loading borrower session...</p>
        </section>
      </main>
    );
  }

  return (
    <main className="borrower-chat-page">
      <section className="panel borrower-chat-panel">
        <div className="borrower-chat-header">
          <h1>Chat</h1>
          <button type="button" className="button button-secondary" onClick={handleLogout}>
            Logout
          </button>
        </div>

        <div className="borrower-chat-stream">
          {messages.map((message) => (
            <article
              key={message.id}
              className={`message-row ${
                message.actor === "borrower" ? "msg-borrower" : message.actor === "agent" ? "msg-agent" : "msg-system"
              }`}
            >
              <header>
                <strong>{message.actor === "borrower" ? "You" : message.actor === "agent" ? "Collections Agent" : "System"}</strong>
                <time>{new Date(message.created_at).toLocaleTimeString()}</time>
              </header>
              <p>{message.text}</p>
            </article>
          ))}
        </div>

        <form className="borrower-chat-input" onSubmit={handleSend}>
          <label className="field">
            <span>Message</span>
            <textarea
              rows={3}
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              placeholder={isConversationClosed ? "Conversation is closed." : "Type your message"}
              disabled={isSending || isConversationClosed}
            />
          </label>
          <div className="form-actions">
            <button type="submit" className="button button-primary" disabled={isSending || isConversationClosed}>
              {isSending ? "Sending..." : "Send"}
            </button>
          </div>
        </form>

        {finalResult ? <p className="form-success">Conversation closed with result: {finalResult}</p> : null}
        {error ? <p className="form-error">{error}</p> : null}
      </section>
    </main>
  );
}
