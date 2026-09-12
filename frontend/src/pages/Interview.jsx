import { useEffect, useRef, useState, useMemo } from "react";
import { Link, useParams } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { api, wsProtocols, wsUrl } from "../api.js";
import { useAuth } from "../auth.jsx";
import { useToast } from "../components/Toast";
import { Button, LoadingSpinner, AnimatedCard, StaggeredList } from "../components";
import { typingIndicator, pulse, questionTransition, EASE_SMOOTH } from "../animations/variants";

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
        sessionRef.current = data;
        const firstUnanswered = data.questions.findIndex((q) => !q.user_answer);
        const nextIndex = firstUnanswered === -1 ? data.questions.length : firstUnanswered;
        indexRef.current = nextIndex;
        setIndex(nextIndex);
        setLog(
          data.questions.flatMap((q) => {
            if (!q.user_answer) return [];
            const items = [{ role: "you", text: q.user_answer, question: q.question, qa_id: q.id }];
            if (q.interviewer_reply) {
              items.push({
                role: "ai",
                text: q.interviewer_reply,
                score: q.score,
                qa_id: q.id,
                question: q.question,
              });
            }
            return items;
          })
        );
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
        setError("");
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
          const currentQuestionText =
            sessionRef.current?.questions?.[indexRef.current]?.question || "Question";

          setLog((prev) => [
            ...prev,
            {
              role: "ai",
              text: payload.reply,
              score: payload.score,
              qa_id: payload.qa_id,
              question: currentQuestionText,
            },
          ]);

          // Update local session state to mark current question as answered
          setSession((prev) => {
            if (!prev) return prev;
            const updatedQuestions = [...prev.questions];
            if (updatedQuestions[indexRef.current]) {
              updatedQuestions[indexRef.current] = {
                ...updatedQuestions[indexRef.current],
                user_answer: updatedQuestions[indexRef.current].user_answer || "Submitted",
                interviewer_reply: payload.reply,
                score: payload.score,
              };
            }
            const updated = { ...prev, questions: updatedQuestions };
            sessionRef.current = updated;
            return updated;
          });

          // Advance to the next question
          setIndex((i) => {
            const next = i + 1;
            indexRef.current = next;
            return next;
          });

          setStream("");
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
  const progress = session && session.questions.length > 0 ? (index / session.questions.length) * 100 : 0;
  const isComplete = session && (Boolean(session.ended_at) || index >= session.questions.length);

  const scores = useMemo(() => {
    return log.filter((item) => item.role === "ai" && item.score != null).map((item) => item.score);
  }, [log]);

  const averageScore = useMemo(() => {
    if (!scores.length) return null;
    const sum = scores.reduce((a, b) => a + b, 0);
    return (sum / scores.length).toFixed(1);
  }, [scores]);

  const scrollToBottom = () => {
    setTimeout(() => {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, 60);
  };

  function sendAnswer(e) {
    if (e && e.preventDefault) e.preventDefault();
    const answerText = draft.trim();
    if (!question || !answerText || sending) return;

    if (!socketRef.current || socketRef.current.readyState !== WebSocket.OPEN) {
      setError("Connection is currently reconnecting. Please wait a moment.");
      return;
    }

    setSending(true);
    setError("");

    // Append to local log immediately for responsive UX
    setLog((prev) => [
      ...prev,
      { role: "you", text: answerText, question: question.question, qa_id: question.id },
    ]);

    // Record answer in local session state
    setSession((prev) => {
      if (!prev) return prev;
      const updatedQuestions = [...prev.questions];
      if (updatedQuestions[index]) {
        updatedQuestions[index] = { ...updatedQuestions[index], user_answer: answerText };
      }
      const updated = { ...prev, questions: updatedQuestions };
      sessionRef.current = updated;
      return updated;
    });

    socketRef.current.send(
      JSON.stringify({ type: "answer", qa_id: question.id, text: answerText })
    );

    scrollToBottom();
  }

  async function endInterview() {
    if (!session || session.ended_at || sending) return;
    try {
      const updated = await api(`/interviews/${sessionId}/end`, { method: "POST", token: access });
      setSession(updated);
      sessionRef.current = updated;
      addToast({ type: "success", message: "Interview completed and results saved!" });
    } catch (err) {
      setError(err.message);
      addToast({ type: "error", message: err.message });
    }
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      {/* Sticky Header */}
      <header className="glass border-b border-slate-800 px-6 py-4 sticky top-0 z-40">
        <div className="mx-auto max-w-3xl flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2">
              <span className="inline-block w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              <p className="text-xs uppercase tracking-[0.2em] text-cyan-400 font-semibold">Live Interview</p>
            </div>
            <h1 className="text-xl font-bold gradient-text">Session #{sessionId}</h1>
          </div>
          <div className="flex items-center gap-3">
            <Link to="/" className="btn-secondary text-sm">
              <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
              </svg>
              Dashboard
            </Link>
            {session && !session.ended_at && !isComplete && (
              <Button variant="outline" size="sm" onClick={endInterview} disabled={sending}>
                End Early
              </Button>
            )}
          </div>
        </div>

        {/* Progress Bar */}
        {session && session.questions.length > 0 && (
          <div className="mt-3 mx-auto max-w-3xl">
            <div className="flex items-center justify-between text-xs text-slate-400 mb-1.5 font-medium">
              <span>
                Question {Math.min(index + 1, session.questions.length)} of {session.questions.length}
              </span>
              <span>{Math.round(progress)}% Completed</span>
            </div>
            <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
              <motion.div
                className="h-full bg-gradient-to-r from-cyan-500 via-teal-400 to-cyan-400 rounded-full"
                initial={{ width: 0 }}
                animate={{ width: `${Math.min(100, Math.max(0, progress))}%` }}
                transition={{ duration: 0.4, ease: EASE_SMOOTH }}
              />
            </div>
          </div>
        )}
      </header>

      {/* Main Content */}
      <main className="mx-auto max-w-3xl px-6 py-8 flex-1 w-full">
        {/* Reconnecting banner */}
        <AnimatePresence>
          {reconnecting && (
            <motion.div
              className="mb-4 rounded-xl bg-amber-950/40 border border-amber-800/80 p-3 flex items-center gap-2.5 text-amber-300 text-sm backdrop-blur-md"
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.2 }}
            >
              <svg className="w-4 h-4 animate-spin flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              <span>Reconnecting to interview server…</span>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Error banner */}
        <AnimatePresence>
          {error && (
            <motion.div
              className="mb-4 rounded-xl bg-rose-950/40 border border-rose-800/80 p-3.5 flex items-center justify-between text-rose-300 text-sm backdrop-blur-md"
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.2 }}
            >
              <div className="flex items-center gap-2.5">
                <svg className="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
                <span>{error}</span>
              </div>
              <button
                type="button"
                onClick={() => setError("")}
                className="text-rose-400 hover:text-rose-200 text-xs uppercase tracking-wider font-semibold ml-3"
              >
                Dismiss
              </button>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Active Question with Smooth Sliding Transition */}
        <AnimatePresence mode="wait">
          {!isComplete && question ? (
            <motion.div
              key={question.id || `q-${index}`}
              variants={questionTransition}
              initial="initial"
              animate="animate"
              exit="exit"
              className="mb-6 rounded-2xl border border-slate-800 bg-slate-900/70 p-6 backdrop-blur-md shadow-xl shadow-slate-950/40"
            >
              <div className="flex items-center justify-between mb-3.5">
                <div className="flex items-center gap-2">
                  <span className="flex h-2 w-2 rounded-full bg-cyan-400" />
                  <span className="text-xs font-semibold uppercase tracking-wider text-cyan-400">
                    Question {index + 1} of {session.questions.length}
                  </span>
                </div>
                <span className="text-xs font-mono text-slate-500 bg-slate-800/60 px-2.5 py-0.5 rounded-full border border-slate-700/50">
                  ID #{question.id}
                </span>
              </div>
              <h2 className="text-lg font-medium leading-relaxed text-slate-100 whitespace-pre-wrap">
                {question.question}
              </h2>
            </motion.div>
          ) : (
            isComplete && (
              <motion.div
                key="complete"
                initial={{ opacity: 0, scale: 0.95, y: 15 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.95, y: -15 }}
                transition={{ duration: 0.4, ease: EASE_SMOOTH }}
                className="mb-8 rounded-2xl border border-emerald-800/80 bg-gradient-to-b from-emerald-950/40 to-slate-900/60 p-8 text-center backdrop-blur-md shadow-2xl"
              >
                <motion.div
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  transition={{ type: "spring", stiffness: 350, damping: 20, delay: 0.1 }}
                  className="mx-auto w-16 h-16 rounded-2xl bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center mb-4 shadow-lg shadow-emerald-500/10"
                >
                  <svg className="w-8 h-8 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                  </svg>
                </motion.div>
                <h3 className="text-2xl font-bold text-slate-100 mb-2">Interview Completed!</h3>
                <p className="text-slate-400 max-w-md mx-auto text-sm mb-6">
                  You have answered all questions in this session. Review your transcript and AI evaluator feedback below.
                </p>

                {averageScore != null && (
                  <div className="inline-flex items-center gap-3 bg-slate-900/90 border border-slate-700/80 rounded-2xl px-5 py-3 mb-6 shadow-inner">
                    <span className="text-xs uppercase tracking-wider text-slate-400 font-medium">Overall Score</span>
                    <span className="text-2xl font-bold text-cyan-400 font-mono">{averageScore} / 10</span>
                  </div>
                )}

                <div className="flex items-center justify-center gap-4">
                  <Link to="/" className="btn-primary px-6 py-2.5 text-sm font-semibold">
                    Return to Dashboard
                  </Link>
                  {session && !session.ended_at && (
                    <Button variant="outline" size="sm" onClick={endInterview} disabled={sending}>
                      Finalize & Close
                    </Button>
                  )}
                </div>
              </motion.div>
            )
          )}
        </AnimatePresence>

        {/* Conversation Transcript Log */}
        <div className="space-y-4" ref={messagesEndRef}>
          <StaggeredList stagger={0.04}>
            {log.map((item, i) => (
              <AnimatedCard
                key={`${item.qa_id}-${item.role}-${i}`}
                delay={0.02 * i}
                variant="elevated"
                className={`transition-all duration-200 ${
                  item.role === "you"
                    ? "border-slate-800 bg-slate-900/60"
                    : "border-cyan-900/60 bg-cyan-950/20"
                }`}
              >
                <div className="flex items-start gap-3.5">
                  <div
                    className={`w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0 shadow-sm ${
                      item.role === "you"
                        ? "bg-slate-800 border border-slate-700 text-slate-300"
                        : "bg-cyan-500/20 border border-cyan-500/40 text-cyan-300"
                    }`}
                  >
                    {item.role === "you" ? (
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                      </svg>
                    ) : (
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                      </svg>
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2.5 mb-1.5">
                      <span className={`text-xs font-semibold uppercase tracking-wider ${item.role === "you" ? "text-slate-300" : "text-cyan-400"}`}>
                        {item.role === "you" ? "Candidate" : "AI Evaluator"}
                      </span>
                      {item.score != null && (
                        <span className="rounded-full bg-cyan-500/15 border border-cyan-500/30 px-2.5 py-0.5 text-xs font-mono font-medium text-cyan-300">
                          Score: {item.score}/10
                        </span>
                      )}
                    </div>
                    {item.question && item.role === "you" && (
                      <p className="text-xs text-slate-500 mb-2 italic line-clamp-2">Q: "{item.question}"</p>
                    )}
                    <p className="whitespace-pre-wrap text-slate-200 leading-relaxed text-sm">{item.text}</p>
                  </div>
                </div>
              </AnimatedCard>
            ))}
          </StaggeredList>

          {/* Live Streaming Indicator Card */}
          <AnimatePresence>
            {stream && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                transition={{ duration: 0.2 }}
                className="rounded-2xl border border-cyan-500/30 bg-cyan-950/30 p-6 backdrop-blur-md shadow-lg shadow-cyan-950/50"
              >
                <div className="flex items-start gap-3.5">
                  <motion.div
                    variants={pulse}
                    animate="pulse"
                    className="w-9 h-9 rounded-xl bg-cyan-500/20 border border-cyan-500/40 flex items-center justify-center flex-shrink-0 text-cyan-300"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                    </svg>
                  </motion.div>
                  <div className="flex-1">
                    <p className="text-xs font-semibold uppercase tracking-wider text-cyan-400 mb-1.5 flex items-center gap-2">
                      <span>AI Evaluator</span>
                      <span className="text-[10px] text-cyan-300/70 font-mono">Generating review…</span>
                    </p>
                    <p className="whitespace-pre-wrap text-slate-200 leading-relaxed text-sm">
                      {stream}
                      <motion.span
                        className="inline-block w-2 h-4 ml-1 bg-cyan-400 align-middle"
                        variants={typingIndicator}
                        animate="animate"
                      />
                    </p>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Answer Input Area */}
        {!isComplete && question && (
          <motion.form
            onSubmit={sendAnswer}
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, delay: 0.1 }}
            className="mt-8 sticky bottom-4 z-30"
          >
            <div className="rounded-2xl border border-slate-700/80 bg-slate-900/90 p-3 shadow-2xl backdrop-blur-xl">
              <textarea
                className="w-full h-28 rounded-xl bg-slate-950/70 p-3.5 text-slate-100 placeholder-slate-500 border border-slate-800 focus:outline-none focus:border-cyan-500/80 focus:ring-2 focus:ring-cyan-500/20 resize-none disabled:opacity-50 text-sm leading-relaxed transition-all"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => {
                  if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
                    e.preventDefault();
                    sendAnswer(e);
                  }
                }}
                placeholder="Type your answer… (Press Ctrl+Enter to submit)"
                disabled={sending}
              />
              <div className="mt-2.5 px-2 flex items-center justify-between">
                <span className="text-xs text-slate-400 font-mono">
                  {draft.length} characters &bull; <span className="text-slate-500">Ctrl+Enter to send</span>
                </span>
                <Button
                  type="submit"
                  disabled={sending || !draft.trim()}
                  isLoading={sending}
                  size="md"
                  className="px-5 font-semibold"
                >
                  <svg className="w-4 h-4 mr-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                  </svg>
                  {sending ? "Evaluating…" : "Submit Answer"}
                </Button>
              </div>
            </div>
          </motion.form>
        )}
      </main>
    </div>
  );
}
