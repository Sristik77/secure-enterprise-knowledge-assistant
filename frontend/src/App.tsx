
import { useEffect, useState, type FormEvent } from "react";
import {
  Activity,
  ArrowUp,
  BookOpen,
  FileText,
  LockKeyhole,
  LogOut,
  MessageSquare,
  Plus,
  ShieldCheck,
  Sparkles,
  UserRound,
} from "lucide-react";
import "./index.css";

const API =
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

type User = {
  id: string;
  email: string;
  full_name: string;
};

type Citation = {
  document_id: string;
  document_title: string;
  source_name: string;
  chunk_index: number;
  similarity: number;
};

type Message = {
  id?: string;
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  created_at?: string;
};

type ConversationSummary = {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
};

type ConversationDetail = ConversationSummary & {
  messages: Message[];
};

type ChatResult = {
  question: string;
  answer: string;
  citations: Citation[];
  conversation_id: string | null;
};

async function apiRequest<T>(
  path: string,
  options: RequestInit = {},
  token?: string
): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(
      data.detail || `Request failed (${response.status})`
    );
  }

  return data as T;
}

function AuthScreen({
  onLogin,
}: {
  onLogin: (token: string) => Promise<void>;
}) {
  const [register, setRegister] = useState(false);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setBusy(true);

    try {
      if (register) {
        await apiRequest("/auth/register", {
          method: "POST",
          body: JSON.stringify({
            full_name: name.trim(),
            email: email.trim(),
            password,
          }),
        });
      }

      const result = await apiRequest<{
        access_token: string;
      }>("/auth/login", {
        method: "POST",
        body: JSON.stringify({
          email: email.trim(),
          password,
        }),
      });

      await onLogin(result.access_token);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Unable to sign in."
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth-page">
      <div className="auth-glow glow-one" />
      <div className="auth-glow glow-two" />

      <section className="auth-card">
        <div className="brand-mark">
          <ShieldCheck size={25} />
        </div>

        <p className="eyebrow">PRIVATE KNOWLEDGE. VERIFIED ACCESS.</p>

        <h1>
          Your knowledge,
          <br />
          <span>securely connected.</span>
        </h1>

        <p className="auth-description">
          An intelligent workspace for enterprise knowledge, designed
          around access control and trusted sources.
        </p>

        <form onSubmit={submit} className="auth-form">
          {register && (
            <label>
              Full name
              <input
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="Your full name"
                required
                maxLength={200}
              />
            </label>
          )}

          <label>
            Email address
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="you@company.com"
              required
            />
          </label>

          <label>
            Password
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder={
                register ? "At least 12 characters" : "Your password"
              }
              minLength={register ? 12 : undefined}
              maxLength={128}
              required
            />
          </label>

          {error && <p className="error-message">{error}</p>}

          <button className="primary-button" disabled={busy}>
            {busy
              ? "Please wait..."
              : register
                ? "Create secure account"
                : "Sign in securely"}
            <ArrowUp size={17} className="button-arrow" />
          </button>
        </form>

        <p className="auth-switch">
          {register
            ? "Already have an account?"
            : "New to the workspace?"}{" "}
          <button
            type="button"
            onClick={() => {
              setRegister(!register);
              setError("");
            }}
          >
            {register ? "Sign in" : "Create account"}
          </button>
        </p>

        <div className="secure-note">
          <LockKeyhole size={14} />
          Protected access · Role-aware retrieval
        </div>
      </section>
    </main>
  );
}

export default function App() {
  const [token, setToken] = useState(
    () => sessionStorage.getItem("knowledge_token") || ""
  );
  const [user, setUser] = useState<User | null>(null);
  const [checking, setChecking] = useState(true);
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [conversations, setConversations] = useState<
    ConversationSummary[]
  >([]);
  const [activeConversationId, setActiveConversationId] =
    useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [sidebarOpen, setSidebarOpen] = useState(true);

  // Validate the current login token.
  useEffect(() => {
    let active = true;

    if (!token) {
      setUser(null);
      setChecking(false);
      return;
    }

    setChecking(true);

    apiRequest<User>("/auth/me", {}, token)
      .then((result) => {
        if (active) setUser(result);
      })
      .catch(() => {
        sessionStorage.removeItem("knowledge_token");

        if (active) {
          setToken("");
          setUser(null);
        }
      })
      .finally(() => {
        if (active) setChecking(false);
      });

    return () => {
      active = false;
    };
  }, [token]);

  // Load the user's history and restore the latest conversation.
  useEffect(() => {
    let active = true;

    if (!token || !user) {
      setConversations([]);
      setActiveConversationId(null);
      setMessages([]);
      return;
    }

    async function restoreHistory() {
      try {
        const history = await apiRequest<ConversationSummary[]>(
          "/conversations",
          {},
          token
        );

        if (!active) return;

        setConversations(history);

        if (history.length === 0) {
          setActiveConversationId(null);
          setMessages([]);
          return;
        }

        const latest = history[0];

        const detail = await apiRequest<ConversationDetail>(
          `/conversations/${latest.id}`,
          {},
          token
        );

        if (!active) return;

        setActiveConversationId(detail.id);
        setMessages(detail.messages || []);
      } catch (err) {
        if (active) {
          setError(
            err instanceof Error
              ? err.message
              : "Unable to load conversation history."
          );
        }
      }
    }

    void restoreHistory();

    return () => {
      active = false;
    };
  }, [token, user]);

  async function login(accessToken: string) {
    sessionStorage.setItem("knowledge_token", accessToken);
    setChecking(true);
    setToken(accessToken);
  }

  function logout() {
    sessionStorage.removeItem("knowledge_token");
    setToken("");
    setUser(null);
    setMessages([]);
    setConversations([]);
    setActiveConversationId(null);
    setQuestion("");
    setError("");
  }

  async function refreshHistory(accessToken: string) {
    const history = await apiRequest<ConversationSummary[]>(
      "/conversations",
      {},
      accessToken
    );

    setConversations(history);
  }

  async function openConversation(id: string) {
    if (busy || !token) return;

    setError("");

    try {
      const detail = await apiRequest<ConversationDetail>(
        `/conversations/${id}`,
        {},
        token
      );

      setActiveConversationId(detail.id);
      setMessages(detail.messages || []);
      setQuestion("");
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to open this conversation."
      );
    }
  }

  function startNewConversation() {
    if (busy) return;

    setActiveConversationId(null);
    setMessages([]);
    setQuestion("");
    setError("");
  }

  async function sendQuestion(text = question) {
    const clean = text.trim();

    if (!clean || busy || !token) return;

    setQuestion("");
    setError("");
    setMessages((previous) => [
      ...previous,
      { role: "user", content: clean },
    ]);
    setBusy(true);

    try {
      const result = await apiRequest<ChatResult>(
        "/chat",
        {
          method: "POST",
          body: JSON.stringify({
            question: clean,
            limit: 5,
            min_similarity: 0,
            ...(activeConversationId
              ? { conversation_id: activeConversationId }
              : {}),
          }),
        },
        token
      );

      if (result.conversation_id) {
        setActiveConversationId(result.conversation_id);
      }

      setMessages((previous) => [
        ...previous,
        {
          role: "assistant",
          content: result.answer,
          citations: result.citations || [],
        },
      ]);

      await refreshHistory(token);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to get an answer."
      );
    } finally {
      setBusy(false);
    }
  }

  if (checking) {
    return (
      <main className="loading-screen">
        <div className="brand-mark">
          <ShieldCheck />
        </div>
        <p>Securing your workspace...</p>
      </main>
    );
  }

  if (!token || !user) {
    return <AuthScreen onLogin={login} />;
  }

  return (
    <main
      className={`app-shell ${sidebarOpen ? "" : "sidebar-collapsed"}`}
    >
      <aside className="sidebar">
        <a className="brand" href="#" onClick={(event) => event.preventDefault()}>
          <div className="brand-mark small">
            <ShieldCheck size={21} />
          </div>
          <span>
            NOCTURNE
            <small>KNOWLEDGE SYSTEM</small>
          </span>
        </a>

        <button
          className="new-chat"
          onClick={startNewConversation}
          disabled={busy}
        >
          <Plus size={17} />
          New conversation
        </button>

        <div className="side-label">WORKSPACE</div>
        <div className="side-link active">
          <MessageSquare size={17} />
          Knowledge assistant
        </div>
        <div className="side-link">
          <BookOpen size={17} />
          Knowledge sources
        </div>
        <div className="side-link">
          <Activity size={17} />
          Activity overview
        </div>

        <div className="history-section">
          <div className="side-label">RECENT CONVERSATIONS</div>

          {conversations.length === 0 ? (
            <p className="history-empty">
              Your saved conversations will appear here.
            </p>
          ) : (
            <div className="history-list">
              {conversations.map((conversation) => (
                <button
                  type="button"
                  key={conversation.id}
                  className={`history-item ${
                    activeConversationId === conversation.id
                      ? "selected"
                      : ""
                  }`}
                  onClick={() => void openConversation(conversation.id)}
                  disabled={busy}
                  title={conversation.title}
                >
                  <MessageSquare size={15} />
                  <span>{conversation.title}</span>
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="sidebar-bottom">
          <div className="security-card">
            <div className="security-icon">
              <LockKeyhole size={16} />
            </div>
            <strong>Access protected</strong>
            <p>
              Answers are generated from documents your account is
              permitted to access.
            </p>
            <span>
              <i /> SECURITY ACTIVE
            </span>
          </div>

          <div className="profile-row">
            <div className="avatar">
              <UserRound size={18} />
            </div>
            <div className="profile-info">
              <strong>{user.full_name}</strong>
              <small>{user.email}</small>
            </div>
            <button
              className="icon-button"
              onClick={logout}
              title="Sign out"
            >
              <LogOut size={17} />
            </button>
          </div>
        </div>
      </aside>

      <section className="main-panel">
        <header className="topbar">
          <button
            className="icon-button mobile-menu"
            onClick={() => setSidebarOpen(!sidebarOpen)}
            title="Toggle sidebar"
          >
            <MessageSquare size={18} />
          </button>

          <div className="breadcrumb">
            Workspace <span>/</span>{" "}
            <strong>Knowledge assistant</strong>
          </div>

          <div className="topbar-status">
            <span className="status-dot" /> PRIVATE SESSION
          </div>
        </header>

        <div className="chat-area">
          {messages.length === 0 ? (
            <section className="welcome">
              <div className="orb-wrap">
                <div className="orb">
                  <div className="orb-core" />
                  <div className="orb-ring ring-a" />
                  <div className="orb-ring ring-b" />
                </div>
              </div>

              <p className="eyebrow">
                <Sparkles size={13} /> YOUR ENTERPRISE KNOWLEDGE,
                REIMAGINED
              </p>

              <h1>
                Good knowledge
                <br />
                starts with <span>the right question.</span>
              </h1>

              <p className="welcome-copy">
                Ask about your organization's documents. Get focused
                answers grounded in the information you're authorized
                to access.
              </p>

              <div className="suggestion-grid">
                {[
                  [
                    "Summarize a document",
                    "Give me a concise summary of the key information.",
                  ],
                  [
                    "Find a key detail",
                    "Find the key points most relevant to my work.",
                  ],
                  [
                    "Understand a process",
                    "Explain the relevant process step by step.",
                  ],
                ].map(([title, prompt]) => (
                  <button
                    key={title}
                    className="suggestion-card"
                    onClick={() => void sendQuestion(prompt)}
                  >
                    <span className="suggestion-icon">
                      <FileText size={18} />
                    </span>
                    <strong>{title}</strong>
                    <span className="suggestion-arrow">↗</span>
                    <p>{prompt}</p>
                  </button>
                ))}
              </div>
            </section>
          ) : (
            <section className="conversation">
              <div className="conversation-heading">
                <span className="eyebrow">KNOWLEDGE SESSION</span>
                <span>
                  {messages.filter((m) => m.role === "user").length}{" "}
                  question(s)
                </span>
              </div>

              {messages.map((message, index) => (
                <article
                  className={`message ${message.role}`}
                  key={message.id || `${index}-${message.role}`}
                >
                  <div className="message-avatar">
                    {message.role === "assistant" ? (
                      <Sparkles size={17} />
                    ) : (
                      <UserRound size={17} />
                    )}
                  </div>

                  <div className="message-body">
                    <div className="message-author">
                      {message.role === "assistant"
                        ? "Knowledge assistant"
                        : "You"}
                    </div>

                    <div className="message-text">{message.content}</div>

                    {message.citations &&
                      message.citations.length > 0 && (
                        <div className="citations">
                          <div className="citation-heading">
                            <BookOpen size={15} /> SOURCES USED
                            <span>{message.citations.length}</span>
                          </div>

                          {message.citations.map((citation, i) => (
                            <div
                              className="citation-card"
                              key={`${citation.document_id}-${citation.chunk_index}-${i}`}
                            >
                              <div className="citation-file">
                                <FileText size={17} />
                              </div>
                              <div className="citation-info">
                                <strong>{citation.document_title}</strong>
                                <small>
                                  {citation.source_name} · Chunk{" "}
                                  {citation.chunk_index}
                                </small>
                              </div>
                              <span className="citation-number">
                                {String(i + 1).padStart(2, "0")}
                              </span>
                            </div>
                          ))}
                        </div>
                      )}
                  </div>
                </article>
              ))}

              {busy && (
                <div className="thinking-row">
                  <div className="thinking-dots">
                    <i />
                    <i />
                    <i />
                  </div>
                  <span>Searching authorized knowledge...</span>
                </div>
              )}

              <div id="conversation-end" />
            </section>
          )}

          {error && <div className="error-banner">{error}</div>}
        </div>

        <footer className="composer-area">
          <form
            className="composer"
            onSubmit={(event) => {
              event.preventDefault();
              void sendQuestion();
            }}
          >
            <textarea
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="Ask a question about your knowledge base..."
              rows={2}
              maxLength={2000}
              onKeyDown={(event) => {
                if (
                  event.key === "Enter" &&
                  !event.shiftKey &&
                  !event.nativeEvent.isComposing
                ) {
                  event.preventDefault();
                  void sendQuestion();
                }
              }}
            />

            <button
              className="send-button"
              type="submit"
              disabled={!question.trim() || busy}
              title="Send question"
            >
              <ArrowUp size={19} />
            </button>
          </form>

          <div className="composer-caption">
            <LockKeyhole size={12} />
            Only authorized document excerpts are used for answers
            <span>ENTER TO SEND · SHIFT + ENTER FOR NEW LINE</span>
          </div>
        </footer>
      </section>
    </main>
  );
}
