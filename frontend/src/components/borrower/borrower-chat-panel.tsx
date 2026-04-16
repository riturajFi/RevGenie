"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { sendBorrowerChatMessage } from "@/lib/api";
import { BorrowerChatMessage, BorrowerPortalLoginResponse, ResolutionMode } from "@/types/borrower";

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

function getInitialResolutionMode(session: BorrowerPortalLoginResponse): ResolutionMode {
  const raw = session.borrower_case.attributes["resolution_mode"];
  return raw === "CHAT" ? "CHAT" : "VOICE";
}

export function BorrowerChatPanel() {
  const router = useRouter();
  const [session, setSession] = useState<BorrowerPortalLoginResponse | null>(null);
  const [workflowId, setWorkflowId] = useState<string>("");
  const [stage, setStage] = useState<string>("");
  const [resolutionMode, setResolutionMode] = useState<ResolutionMode>("VOICE");
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
      setStage(parsed.borrower_case.core.stage);
      setResolutionMode(getInitialResolutionMode(parsed));
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
  const isResolutionVoiceMode = useMemo(
    () => stage === "RESOLUTION" && resolutionMode === "VOICE" && !finalResult,
    [finalResult, resolutionMode, stage]
  );

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
        resolutionMode,
      });
      setWorkflowId(response.workflow_id);
      setStage(response.stage);
      setResolutionMode(response.resolution_mode);
      setFinalResult(response.final_result);

      if (response.reply) {
        setMessages((current) => [...current, makeMessage("agent", response.reply ?? "", "agent")]);
      } else {
        setMessages((current) => [
          ...current,
          makeMessage("system", "Agent did not return a reply for this turn.", "system"),
        ]);
      }
      if (
        response.stage === "RESOLUTION" &&
        response.resolution_mode === "VOICE" &&
        ["registered", "ongoing"].includes(response.voice_call_status ?? "")
      ) {
        setMessages((current) => [
          ...current,
          makeMessage(
            "system",
            "Resolution has switched to voice mode. Expect a phone call on your registered number. Chat is paused until voice mode is turned off or the call flow completes.",
            "system"
          ),
        ]);
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
          <h2>Borrower Chat</h2>
          <p>Loading borrower session...</p>
        </section>
      </main>
    );
  }

  return (
    <main className="borrower-chat-page">
      <section className="panel borrower-chat-panel">
        <div className="borrower-chat-header">
          <div>
            <p className="eyebrow">Borrower Chat</p>
            <h1>{session.borrower_profile.full_name}</h1>
            <p className="panel-copy">
              Borrower ID: <strong>{session.borrower_profile.borrower_id}</strong> | Loan:{" "}
              <strong>{session.borrower_case.core.loan_id_masked}</strong>
            </p>
          </div>
          <button type="button" className="button button-secondary" onClick={handleLogout}>
            Logout
          </button>
        </div>

        <div className="borrower-chat-meta">
          <div>
            <span>Workflow ID</span>
            <strong>{workflowId}</strong>
          </div>
          <div>
            <span>Stage</span>
            <strong>{stage}</strong>
          </div>
          <div>
            <span>Case Status</span>
            <strong>{session.borrower_case.core.case_status}</strong>
          </div>
          <div>
            <span>Amount Due</span>
            <strong>{session.borrower_case.core.amount_due}</strong>
          </div>
        </div>

        <div className="borrower-chat-meta">
          <div>
            <span>Voice Mode</span>
            <strong>{resolutionMode === "VOICE" ? "On" : "Off"}</strong>
          </div>
          <div className="form-actions">
            <button
              type="button"
              className={resolutionMode === "VOICE" ? "button button-primary" : "button button-secondary"}
              onClick={() => setResolutionMode("VOICE")}
              disabled={isSending || Boolean(finalResult)}
            >
              Voice On
            </button>
            <button
              type="button"
              className={resolutionMode === "CHAT" ? "button button-primary" : "button button-secondary"}
              onClick={() => setResolutionMode("CHAT")}
              disabled={isSending || Boolean(finalResult)}
            >
              Voice Off
            </button>
          </div>
        </div>

        {isResolutionVoiceMode ? (
          <p className="form-success">
            Resolution is in voice mode. Chat stays paused while the phone-call flow is active. Turn voice mode off to resume
            chat-based resolution.
          </p>
        ) : null}

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
              placeholder={
                isConversationClosed
                  ? "Conversation is closed."
                  : isResolutionVoiceMode
                    ? "Resolution is currently paused for voice mode."
                    : "Type your message"
              }
              disabled={isSending || isConversationClosed || isResolutionVoiceMode}
            />
          </label>
          <div className="form-actions">
            <button
              type="submit"
              className="button button-primary"
              disabled={isSending || isConversationClosed || isResolutionVoiceMode}
            >
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
