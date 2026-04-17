"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { getBorrowerRealtimeWebSocketUrl } from "@/lib/api";
import {
  BorrowerChatMessage,
  BorrowerPortalLoginResponse,
  BorrowerSocketServerEvent,
} from "@/types/borrower";

const BORROWER_SESSION_STORAGE_KEY = "revgenie.borrower.session";

function nowIso() {
  return new Date().toISOString();
}

function makeSystemMessage(text: string): BorrowerChatMessage {
  return {
    id: `system_${Date.now()}_${Math.random().toString(16).slice(2, 8)}`,
    actor: "system",
    text,
    created_at: nowIso(),
  };
}

export function BorrowerChatPanel() {
  const router = useRouter();
  const socketRef = useRef<WebSocket | null>(null);
  const [session, setSession] = useState<BorrowerPortalLoginResponse | null>(null);
  const [finalResult, setFinalResult] = useState<string | null>(null);
  const [inputEnabled, setInputEnabled] = useState(false);
  const [draft, setDraft] = useState("");
  const [messages, setMessages] = useState<BorrowerChatMessage[]>([]);
  const [isConnected, setIsConnected] = useState(false);
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
    } catch {
      sessionStorage.removeItem(BORROWER_SESSION_STORAGE_KEY);
      router.replace("/borrower/login");
    }
  }, [router]);

  useEffect(() => {
    if (!session) {
      return;
    }

    const socket = new WebSocket(getBorrowerRealtimeWebSocketUrl(session.borrower_profile.borrower_id));
    socketRef.current = socket;

    socket.addEventListener("open", () => {
      setIsConnected(true);
      setError(null);
    });

    socket.addEventListener("message", (event) => {
      const payload = JSON.parse(event.data) as BorrowerSocketServerEvent;
      if (payload.type === "error") {
        setError(payload.message);
        setIsSending(false);
        return;
      }

      const nextSession: BorrowerPortalLoginResponse = {
        borrower_profile: session.borrower_profile,
        borrower_case: payload.state.borrower_case,
      };
      sessionStorage.setItem(BORROWER_SESSION_STORAGE_KEY, JSON.stringify(nextSession));
      setSession(nextSession);
      setFinalResult(payload.state.final_result);
      setInputEnabled(payload.state.input_enabled);
      setMessages(payload.state.messages);
      setIsSending(false);
      setError(null);
    });

    socket.addEventListener("close", () => {
      setIsConnected(false);
      setIsSending(false);
    });

    socket.addEventListener("error", () => {
      setError("Realtime chat connection failed.");
    });

    return () => {
      socket.close();
      socketRef.current = null;
      setIsConnected(false);
    };
  }, [session?.borrower_profile.borrower_id]);

  const connectionMessage = useMemo(() => {
    if (!session) {
      return null;
    }
    return makeSystemMessage(`Connected as ${session.borrower_profile.full_name}. You can now chat with the collections agent.`);
  }, [session]);

  const displayMessages = useMemo(
    () => (connectionMessage ? [connectionMessage, ...messages] : messages),
    [connectionMessage, messages]
  );

  const isConversationClosed = useMemo(() => Boolean(finalResult), [finalResult]);
  const isInputDisabled = !isConnected || !inputEnabled || isSending || isConversationClosed;

  async function handleSend(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const message = draft.trim();
    if (!message || !socketRef.current || socketRef.current.readyState !== WebSocket.OPEN) {
      return;
    }

    setIsSending(true);
    setError(null);
    setDraft("");
    socketRef.current.send(
      JSON.stringify({
        type: "borrower_message",
        message,
      })
    );
  }

  function handleLogout() {
    sessionStorage.removeItem(BORROWER_SESSION_STORAGE_KEY);
    socketRef.current?.close();
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
          {displayMessages.map((message) => (
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
                  : inputEnabled
                    ? "Type your message"
                    : "Waiting for the next agent update."
              }
              disabled={isInputDisabled}
            />
          </label>
          <div className="form-actions">
            <button type="submit" className="button button-primary" disabled={isInputDisabled}>
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
