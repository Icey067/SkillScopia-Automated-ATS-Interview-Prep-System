import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { api, wsProtocols, wsUrl } from "../api.js";
import { useAuth } from "../auth.jsx";
import { useToast } from "../components/Toast";
import { Button, Card, LoadingSpinner, FadeInSection, StaggeredList, AnimatedCard } from "../components";
import { typingIndicator, pulse, fadeIn, slideUp } from "../animations/variants";

export default function Interview() {
  const { sessionId } = useParams();
  const { access } = useAuth();
  const { addToast } = useToast();
  const [session, setSession] = useState(null);
  const [index, setIndex] = useState(0);
  const [draft, setDraft] = useState("");
  const [stream, setStream] = useState("");
  const [log, setLog] = useState([]);
  const [error, setError] = useState("");
  const [sending, setSending] = useState(false);
  const [reconnecting, setReconnecting] = useState(false);
  const socketRef = useRef(null);
  const messagesEndRef = useRef(null);
  const reconnectTimerRef = useRef(null);
  const sessionRef = useRef(null);
  const indexRef = useRef(0);

  useEffect(() => {
    api(`/interviews/${sessionId}`, { token: access })
      .then((data) => {
        setSession(data);
        const firstUnanswered = data.questions.findIndex((q) => !q.user_answer);
        const nextIndex = firstUnanswered === -1 ? data.questions.length : firstUnanswered;
        sessionRef.current = data;
        indexRef.current = nextIndex;
        setIndex(nextIndex);
        setLog(data.questions.flatMap((q) => {
          if (!q.user_answer) return [];
          const items = [{ role: "you", text: q.user_answer, question: q.question, qa_id: q.id }];
          if (q.interviewer_reply) items.push({ role: "ai", text: q.interviewer_reply, score: q.score, qa_id: q.id, question: q.question });
          return items;
        }));
      })
      .catch((err) => {
        setError(err.message);
        addToast({ type: "error", message: err.message });
      });
  }, [sessionId, access, addToast]);

  useEffect(() => {
    if (!access) return undefined;

    let disposed = false;
    const connect = () => {
      const socket = new WebSocket(wsUrl(`/ws/interview/${sessionId}`), wsProtocols(access));
      socketRef.current = socket;

      socket.onopen = () => {
        setReconnecting(false);
      };

      socket.onmessage = (event) => {
        const payload = JSON.parse(event.data);
        if (payload.type === "token") {
          setStream((prev) => prev + payload.content);
        }
        if (payload.type === "stream_start") {
          setStream("");
          scrollToBottom();
        }
        if (payload.type === "stream_end") {
          setSending(false);
          setLog((prev) => [
            ...prev,
            { role: "ai", text: payload.reply, score: payload.score, qa_id: payload.qa_id, question: sessionRef.current?.questions?.[indexRef.current]?.question },
          ]);
          setStream("");
          setIndex((i) => {
            const next = i + 1;
            indexRef.current = next;
            return next;
          });
          setDraft("");
          scrollToBottom();
        }
        if (payload.type === "error") {
          setSending(false);
          setError(payload.error);
          addToast({ type: "error", message: payload.error });
        }
        if (payload.type === "connected") {
          setReconnecting(false);
        }
      };

      socket.onclose = () => {
        socketRef.current = null;
        if (!disposed) {
          setReconnecting(true);
          reconnectTimerRef.current = setTimeout(connect, 2000);
        }
      };

      socket.onerror = () => {
        setReconnecting(true);
      };
    };

    connect();
    return () => {
      disposed = true;
      clearTimeout(reconnectTimerRef.current);
      if (socketRef.current) {
        socketRef.current.close();
      }
    };
  }, [access, sessionId, addToast]);

  const question = session?.questions?.[index];
  const progress = session ? ((index + 1) / session.questions.length) * 100 : 0;

  const scrollToBottom = () => {
    setTimeout(() => {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, 50);
  };

  function sendAnswer(e) {
    e.preventDefault();
    if (!question || !draft.trim() || !socketRef.current || sending) return;
    setSending(true);
    setError("");
    setLog((prev) => [...prev, { role: "you", text: draft, question: question.question, qa_id: question.id }]);
    if (socketRef.current.readyState !== WebSocket.OPEN) {
      setSending(false);
      setError("Connection is not ready. Please wait for reconnection.");
      return;
    }
    socketRef.current.send(JSON.stringify({ type: "answer", qa_id: question.id, text: draft }));
    scrollToBottom();
  }

  async function endInterview() {
    if (!session || session.ended_at || sending) return;
    try {
      const updated = await api(`/interviews/${sessionId}/end`, { method: "POST", token: access });
      setSession(updated);
      sessionRef.current = updated;
      addToast({ type: "success", message: "Interview ended and saved." });
    } catch (err) {
      setError(err.message);
      addToast({ type: "error", message: err.message });
    }
  }

  const isComplete = session && (Boolean(session.ended_at) || index >= session.questions.length);

  return (
    <div className="min-h-screen bg-slate-950">
      <header className="glass border-b border-slate-800 px-6 py-4 sticky top-0 z-40">
        <div className="mx-auto max-w-3xl flex items-center justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-cyan-400">Live interview</p>
            <h1 className="text-xl font-semibold gradient-text">Session #{sessionId}</h1>
          </div>
          <Link to="/" className="btn-secondary text-sm">
            <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
            </svg>
            Back
          </Link>
          {session && !session.ended_at && (
            <Button variant="outline" size="sm" onClick={endInterview} disabled={sending}>End interview</Button>
          )}
        </div>

        {session && (
          <div className="mt-3 w-full">
            <div className="flex items-center justify-between text-xs text-slate-400 mb-1">
              <span>Question {Math.min(index + 1, session.questions.length)} of {session.questions.length}</span>
              <span>{Math.round(progress)}%</span>
            </div>
            <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
              <motion.div
                className="h-full bg-gradient-to-r from-cyan-500 to-cyan-400 rounded-full"
                initial={{ width: 0 }}
                animate={{ width: `${progress}%` }}
                transition={{ duration: 0.5, ease: "easeOut" }}
              />
            </div>
          </div>
        )}
      </header>

      <main className="mx-auto max-w-3xl px-6 py-8">
        {reconnecting && (
          <motion.div
            className="mb-4 rounded-xl bg-amber-950/30 border border-amber-800 p-3 flex items-center gap-2 text-amber-300"
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
          >
            <motion.svg
              className="w-5 h-5 flex-shrink-0"
              animate={{ rotate: 360 }}
              transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
            </motion.svg>
            <span className="text-sm">Reconnecting...</span>
          </motion.div>
        )}

        {error && (
          <motion.div
            className="mb-4 rounded-xl bg-rose-950/30 border border-rose-800 p-3 flex items-center gap-2 text-rose-300"
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
          >
            <svg className="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <span className="text-sm">{error}</span>
          </motion.div>
        )}

        {!isComplete && question ? (
          <AnimatedCard className="mb-6">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, ease: "easeOut" }}
              className="bg-slate-800/30 rounded-xl p-6"
            >
              <div className="flex items-center gap-2 mb-3">
                <div className="w-8 h-8 rounded-full bg-cyan-500/20 flex items-center justify-center">
                  <svg className="w-4 h-4 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                  </svg>
                </div>
                <span className="text-sm font-medium text-slate-400">Question {index + 1} of {session.questions.length}</span>
              </div>
              <h2 className="text-lg font-medium leading-relaxed whitespace-pre-wrap">{question.question}</h2>
            </motion.div>
          </AnimatedCard>
        ) : (
          session && (
            <AnimatePresence>
              <motion.div
                key="complete"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                className="mb-6 rounded-2xl border border-emerald-800 bg-emerald-950/30 p-6 text-center"
              >
                <motion.div
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  transition={{ type: "spring", stiffness: 260, damping: 20 }}
                  className="mx-auto w-16 h-16 rounded-full bg-emerald-500/20 flex items-center justify-center mb-4"
                >
                  <svg className="w-8 h-8 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                </motion.div>
                <h3 className="text-xl font-semibold text-emerald-300 mb-2">Interview Complete!</h3>
                <p className="text-slate-400">Great job! Review your transcript below.</p>
              </motion.div>
            </AnimatePresence>
          )
        )}

        <div className="space-y-3" ref={messagesEndRef}>
          <StaggeredList stagger={0.05}>
            {log.map((item, i) => (
              <AnimatedCard
                key={i}
                delay={0.02 * i}
                variant="elevated"
                className={`${item.role === "you" ? "border-slate-700" : "border-cyan-800/50"}`}
              >
                <div className="flex items-start gap-3">
                  <motion.div
                    className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${item.role === "you" ? "bg-slate-700" : "bg-cyan-950/50"}`}
                    initial={{ scale: 0 }}
                    animate={{ scale: 1 }}
                    transition={{ type: "spring", stiffness: 260, damping: 20, delay: 0.05 * i }}
                  >
                    {item.role === "you" ? (
                      <svg className="w-4 h-4 text-slate-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                      </svg>
                    ) : (
                      <svg className="w-4 h-4 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                      </svg>
                    )}
                  </motion.div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className={`text-xs font-medium ${item.role === "you" ? "text-slate-300" : "text-cyan-400"}`}>
                        {item.role === "you" ? "You" : "AI Interviewer"}
                      </span>
                      {item.score != null && (
                        <motion.span
                          initial={{ scale: 0 }}
                          animate={{ scale: 1 }}
                          transition={{ type: "spring", stiffness: 260, damping: 20, delay: 0.1 }}
                          className="rounded-full bg-cyan-500/20 px-2 py-0.5 text-xs font-mono text-cyan-300"
                        >
                          Score: {item.score}/10
                        </motion.span>
                      )}
                    </div>
                    {item.question && (
                      <p className="text-xs text-slate-500 mb-2 italic">"{item.question}"</p>
                    )}
                    <p className="whitespace-pre-wrap text-slate-100 leading-relaxed">{item.text}</p>
                  </div>
                </div>
              </AnimatedCard>
            ))}
          </StaggeredList>

          {stream && (
            <AnimatedCard variant="elevated" className="border-cyan-800/50 bg-cyan-950/20">
              <div className="flex items-start gap-3">
                <motion.div
                  variants={pulse}
                  animate="pulse"
                  className="w-8 h-8 rounded-full bg-cyan-950/50 flex items-center justify-center flex-shrink-0"
                >
                  <svg className="w-4 h-4 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                  </svg>
                </motion.div>
                <div className="flex-1">
                  <p className="text-xs font-medium text-cyan-400 mb-1">AI Interviewer</p>
                  <motion.p
                    className="whitespace-pre-wrap text-slate-100 leading-relaxed"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                  >
                    {stream}
                    <motion.span
                      className="text-cyan-400"
                      variants={typingIndicator}
                      animate="animate"
                    >
                      ▍
                    </motion.span>
                  </motion.p>
                </div>
              </div>
            </AnimatedCard>
          )}
        </div>

        {!isComplete && question && (
          <AnimatePresence>
            <motion.form
              key="answer-form"
              onSubmit={sendAnswer}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              className="mt-6"
            >
              <textarea
                className="w-full h-32 rounded-xl border-2 border-slate-700 bg-slate-950 p-4 text-slate-100 placeholder-slate-500 focus:outline-none focus:border-cyan-500 focus:ring-2 focus:ring-cyan-500/20 resize-none disabled:opacity-50 transition-all duration-150"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                placeholder="Type your answer…"
                disabled={sending}
                rows={6}
              />
              <div className="mt-4 flex items-center justify-between">
                <p className="text-xs text-slate-500">
                  {draft.length} characters
                </p>
                <Button type="submit" disabled={sending || !draft.trim()} isLoading={sending} size="lg">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                  </svg>
                  {sending ? "Sending…" : "Send Answer"}
                </Button>
              </div>
            </motion.form>
          </AnimatePresence>
        )}
      </main>
    </div>
  );
}
