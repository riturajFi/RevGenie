"use client";

import { useEffect, useMemo, useState } from "react";

import { getConversationMessages, listConversationLogs } from "@/lib/api";
import { ConversationLogSummary, ConversationMessage } from "@/types/borrower";

function actorLabel(senderType: string): string {
  if (senderType === "borrower") return "Borrower";
  if (senderType === "agent") return "Agent";
  return "System";
}

function actorClass(senderType: string): string {
  if (senderType === "borrower") return "msg-borrower";
  if (senderType === "agent") return "msg-agent";
  return "msg-system";
}

function formatTimestamp(value: string | null): string {
  if (!value) return "unknown";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString();
}

function previewText(value: string | null): string {
  const text = (value ?? "").trim();
  if (!text) return "No message preview";
  return text.length > 96 ? `${text.slice(0, 96)}...` : text;
}

export function ConversationLogDashboard() {
  const [conversations, setConversations] = useState<ConversationLogSummary[]>([]);
  const [selectedWorkflowId, setSelectedWorkflowId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [isLoadingConversations, setIsLoadingConversations] = useState(true);
  const [isLoadingMessages, setIsLoadingMessages] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadConversations() {
    setIsLoadingConversations(true);
    setError(null);
    try {
      const nextConversations = await listConversationLogs();
      setConversations(nextConversations);
      setSelectedWorkflowId((current) => {
        if (current && nextConversations.some((item) => item.workflow_id === current)) {
          return current;
        }
        return nextConversations[0]?.workflow_id ?? null;
      });
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Failed to load conversation logs.");
    } finally {
      setIsLoadingConversations(false);
    }
  }

  useEffect(() => {
    void loadConversations();
  }, []);

  useEffect(() => {
    if (!selectedWorkflowId) {
      setMessages([]);
      return;
    }
    const workflowId = selectedWorkflowId;
    let cancelled = false;

    async function loadEvents() {
      setIsLoadingMessages(true);
      setError(null);
      try {
        const nextMessages = await getConversationMessages(workflowId);
        if (!cancelled) {
          setMessages(nextMessages);
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : "Failed to load conversation messages.");
          setMessages([]);
        }
      } finally {
        if (!cancelled) {
          setIsLoadingMessages(false);
        }
      }
    }

    void loadEvents();
    return () => {
      cancelled = true;
    };
  }, [selectedWorkflowId]);

  const selectedConversation = useMemo(
    () => conversations.find((item) => item.workflow_id === selectedWorkflowId) ?? null,
    [conversations, selectedWorkflowId]
  );

  return (
    <section className="conversation-log-layout">
      <div className="panel conversation-log-panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Admin</p>
            <h2>Conversation Logs</h2>
          </div>
          <div className="conversation-log-actions">
            <p className="panel-copy">Browse persisted live borrower conversations by workflow.</p>
            <button className="button button-secondary" type="button" onClick={() => void loadConversations()}>
              Refresh
            </button>
          </div>
        </div>

        {error ? <p className="form-error">{error}</p> : null}

        <div className="conversation-log-grid">
          <div className="conversation-list">
            {isLoadingConversations ? <p className="form-status">Loading conversations...</p> : null}
            {!isLoadingConversations && conversations.length === 0 ? (
              <p className="form-status">No persisted live conversation logs yet.</p>
            ) : null}
            {conversations.map((conversation) => (
              <button
                key={conversation.workflow_id}
                type="button"
                className={
                  selectedWorkflowId === conversation.workflow_id
                    ? "conversation-list-item conversation-list-item-active"
                    : "conversation-list-item"
                }
                onClick={() => setSelectedWorkflowId(conversation.workflow_id)}
              >
                <strong>{conversation.workflow_id}</strong>
                <span>Borrower: {conversation.borrower_id ?? "unknown"}</span>
                <span>
                  {conversation.stage ?? "unknown stage"} / {conversation.case_status ?? "unknown status"}
                </span>
                <span>{conversation.message_count} messages</span>
                <small>{previewText(conversation.last_message_text)}</small>
              </button>
            ))}
          </div>

          <div className="conversation-events-panel">
            {selectedConversation ? (
              <div className="conversation-events-header">
                <div>
                  <strong>{selectedConversation.workflow_id}</strong>
                  <p>
                    Borrower {selectedConversation.borrower_id ?? "unknown"} | Lender{" "}
                    {selectedConversation.lender_id ?? "unknown"}
                  </p>
                </div>
                <div>
                  <p>{selectedConversation.message_count} stored messages</p>
                  <p>{formatTimestamp(selectedConversation.last_message_at)}</p>
                </div>
              </div>
            ) : null}

            {isLoadingMessages ? <p className="form-status">Loading messages...</p> : null}
            {!isLoadingMessages && selectedWorkflowId && messages.length === 0 ? (
              <p className="form-status">No messages found for this workflow.</p>
            ) : null}

            <div className="conversation-events">
              {messages.map((message) => (
                <article className={`message-row ${actorClass(message.sender_type)}`} key={message.id}>
                  <div className="conversation-event-meta">
                    <strong>{actorLabel(message.sender_type)}</strong>
                    <span>{formatTimestamp(message.created_at)}</span>
                  </div>
                  <p>{message.message_text}</p>
                  <div className="conversation-message-meta">
                    <span>{message.agent_id}</span>
                    <span>{message.visible_to_borrower ? "Visible" : "Hidden from borrower"}</span>
                  </div>
                </article>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
