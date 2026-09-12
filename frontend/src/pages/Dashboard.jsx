import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { api, wsProtocols, wsUrl } from "../api.js";
import { useAuth } from "../auth.jsx";
import { useToast } from "../components/Toast";
import { Button, Input, Card, CardStack, AnimatedCard, LoadingSpinner, SkeletonList, FadeInSection, StaggeredList } from "../components";

const STATUS_STYLES = {
  pending: "badge-warning",
  processing: "badge-processing",
  done: "badge-success",
  failed: "badge-error",
};

export default function Dashboard() {
  const { access, user, logout } = useAuth();
  const { addToast } = useToast();
  const navigate = useNavigate();
  const [resumes, setResumes] = useState([]);
  const [sessions, setSessions] = useState([]);
  const [selected, setSelected] = useState(null);
  const [detail, setDetail] = useState(null);
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);

  async function loadResumes() {
    try {
      const list = await api("/resumes", { token: access });
      setResumes(list);
      return list;
    } catch (err) {
      addToast({ type: "error", message: err.message });
      return [];
    }
  }

  async function loadSessions() {
    try {
      setSessions(await api("/interviews", { token: access }));
    } catch (err) {
      addToast({ type: "error", message: err.message });
    }
  }

  async function loadDetail(id) {
    try {
      const data = await api(`/resumes/${id}`, { token: access });
      setDetail(data);
      setSelected(id);
    } catch (err) {
      addToast({ type: "error", message: err.message });
    }
  }

  useEffect(() => {
    loadResumes();
    loadSessions();
  }, [access]);

  useEffect(() => {
    if (!access) return undefined;
    const socket = new WebSocket(wsUrl("/ws/notifications"), wsProtocols(access));
    socket.onmessage = (event) => {
      const payload = JSON.parse(event.data);
      if (payload.type === "resume_ready") {
        addToast({ type: "success", message: `Resume #${payload.resume_id} is ready (${payload.skill_count} skills).` });
        loadResumes().then((list) => {
          if (list.some((r) => r.id === payload.resume_id)) loadDetail(payload.resume_id);
        });
      }
      if (payload.type === "resume_failed") {
        addToast({ type: "error", message: `Resume #${payload.resume_id} failed: ${payload.error}` });
        loadResumes();
      }
    };
    return () => socket.close();
  }, [access, addToast]);

  const groupedSkills = useMemo(() => {
    if (!detail?.skills) return { resume: [], semantic: [] };
    return {
      resume: detail.skills.filter((s) => s.source === "resume"),
      semantic: detail.skills.filter((s) => s.source === "semantic"),
    };
  }, [detail]);

  async function upload(e) {
    e.preventDefault();
    if (!file) return;
    setBusy(true);
    setUploadProgress(0);
    try {
      const form = new FormData();
      form.append("file", file);
      const accepted = await api("/resumes", { method: "POST", token: access, body: form, isForm: true });
      setUploadProgress(100);
      addToast({ type: "success", message: `Upload accepted (resume #${accepted.resume_id}). Parsing in background…` });
      await loadResumes();
      setSelected(accepted.resume_id);
      setFile(null);
    } catch (err) {
      addToast({ type: "error", message: err.message });
    } finally {
      setBusy(false);
      setUploadProgress(0);
    }
  }

  async function startInterview() {
    if (!selected) return;
    setBusy(true);
    try {
      const session = await api("/interviews", {
        method: "POST",
        token: access,
        body: { resume_id: selected, question_count: 5 },
      });
      addToast({ type: "success", message: "Interview started!" });
      navigate(`/interview/${session.id}`);
    } catch (err) {
      addToast({ type: "error", message: err.message });
    } finally {
      setBusy(false);
    }
  }

  async function removeResume(id) {
    if (!window.confirm("Delete this résumé and all of its interview sessions?")) return;
    try {
      await api(`/resumes/${id}`, { method: "DELETE", token: access });
      setSelected(null);
      setDetail(null);
      await Promise.all([loadResumes(), loadSessions()]);
      addToast({ type: "success", message: "Résumé deleted." });
    } catch (err) {
      addToast({ type: "error", message: err.message });
    }
  }

  return (
    <div className="min-h-screen bg-slate-950">
      <header className="glass border-b border-slate-800 px-6 py-4 sticky top-0 z-40">
        <div className="mx-auto max-w-6xl flex items-center justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-cyan-400">MockInterview AI</p>
            <h1 className="text-xl font-semibold gradient-text">Dashboard</h1>
          </div>
          <div className="flex items-center gap-4 text-sm">
            <span className="text-slate-400 hidden sm:block">{user?.email}</span>
            <Button variant="ghost" size="sm" onClick={logout}>
              <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
              </svg>
              Log out
            </Button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 py-8">
        <div className="grid gap-6 md:grid-cols-[1fr_1.2fr]">
          <FadeInSection delay={0.1} className="md:max-h-[calc(100vh-8rem)] overflow-y-auto scrollbar-thin pr-2">
            <AnimatedCard delay={0.1} className="h-full">
              <div className="flex items-center justify-between mb-6">
                <div>
                  <h2 className="text-lg font-medium">Upload resume</h2>
                  <p className="mt-1 text-sm text-slate-400">PDF only. The API returns immediately; parsing happens in a background task.</p>
                </div>
                <svg className="w-8 h-8 text-slate-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                </svg>
              </div>

              <form onSubmit={upload} className="space-y-4">
                <Input
                  type="file"
                  accept="application/pdf"
                  onChange={(e) => setFile(e.target.files?.[0] || null)}
                  label="Select PDF resume"
                  hint="Drag and drop or click to browse"
                  disabled={busy}
                />
                {file && (
                  <div className="rounded-xl bg-slate-800/50 p-3 flex items-center justify-between animate-slide-up">
                    <div className="flex items-center gap-3">
                      <svg className="w-6 h-6 text-rose-500 flex-shrink-0" fill="currentColor" viewBox="0 0 24 24">
                        <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
                        <path d="M14 2v6h6" />
                        <path d="M16 13H8" />
                        <path d="M16 17H8" />
                        <path d="M10 9H8" />
                      </svg>
                      <div>
                        <p className="text-sm font-medium truncate max-w-[200px]">{file.name}</p>
                        <p className="text-xs text-slate-400">{(file.size / 1024).toFixed(1)} KB</p>
                      </div>
                    </div>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => setFile(null)}
                      disabled={busy}
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </Button>
                  </div>
                )}

                <Button type="submit" fullWidth disabled={busy || !file} isLoading={busy}>
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                  </svg>
                  {busy ? "Uploading…" : "Upload Resume"}
                </Button>
              </form>

              <div className="mt-8">
                <h3 className="text-sm font-medium uppercase tracking-wide text-slate-400">Your resumes</h3>
                {resumes.length === 0 ? (
                  <Card variant="outlined" padding="lg" className="mt-4 text-center animate-fade-in">
                    <svg className="mx-auto w-12 h-12 text-slate-600 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    <p className="text-slate-400">No uploads yet. Upload your first resume to get started!</p>
                  </Card>
                ) : (
                  <StaggeredList className="mt-4 space-y-2 max-h-[400px] overflow-y-auto scrollbar-thin pr-2" stagger={0.05}>
                    {resumes.map((resume) => (
                      <AnimatedCard
                        key={resume.id}
                        delay={0.05}
                        className={`${selected === resume.id ? "border-cyan-500 ring-2 ring-cyan-500/20" : ""} transition-all duration-200`}
                        onClick={() => loadDetail(resume.id)}
                      >
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-3">
                            <div className="w-10 h-10 rounded-xl bg-slate-800/50 flex items-center justify-center">
                              <svg className="w-5 h-5 text-slate-400" fill="currentColor" viewBox="0 0 24 24">
                                <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
                                <path d="M14 2v6h6" />
                              </svg>
                            </div>
                            <div>
                              <p className="font-medium">Resume #{resume.id}</p>
                              <p className="text-xs text-slate-500">
                                {new Date(resume.uploaded_at).toLocaleDateString()}
                              </p>
                            </div>
                          </div>
                          <span className={STATUS_STYLES[resume.parsed_status] || "badge"}>
                            {resume.parsed_status}
                          </span>
                        </div>
                      </AnimatedCard>
                    ))}
                  </StaggeredList>
                )}
                {resumes.length > 0 && selected && (
                  <Button variant="danger" size="sm" fullWidth className="mt-3" onClick={() => removeResume(selected)}>
                    Delete selected résumé
                  </Button>
                )}
              </div>
            </AnimatedCard>
          </FadeInSection>

          <FadeInSection delay={0.2} className="md:max-h-[calc(100vh-8rem)] overflow-y-auto scrollbar-thin pr-2">
            {detail ? (
              <AnimatedCard delay={0.05} className="mb-4">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <h2 className="text-lg font-medium">Skills & Interview Setup</h2>
                    <p className="mt-1 text-sm text-slate-400">
                      Status: <span className={STATUS_STYLES[detail.parsed_status] || "badge"}>{detail.parsed_status}</span>
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono bg-slate-800/80 px-2.5 py-1 rounded-full text-slate-300 border border-slate-700">
                      {detail.skills?.length || 0} skills
                    </span>
                  </div>
                </div>

                {groupedSkills.resume.length > 0 && (
                  <div className="mb-6">
                    <h3 className="text-xs uppercase tracking-wider text-slate-400 mb-3 font-semibold">From Resume</h3>
                    <div className="flex flex-wrap gap-2">
                      {groupedSkills.resume.map((s) => (
                        <span
                          key={s.id}
                          className="rounded-xl bg-slate-800/80 px-3 py-1 text-sm font-medium text-slate-200 border border-slate-700 shadow-sm"
                        >
                          {s.skill_name}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {groupedSkills.semantic.length > 0 && (
                  <div className="mb-6">
                    <h3 className="text-xs uppercase tracking-wider text-cyan-400 mb-3 font-semibold">Semantic Expansions</h3>
                    <div className="flex flex-wrap gap-2">
                      {groupedSkills.semantic.map((s) => (
                        <span
                          key={s.id}
                          className="rounded-xl bg-cyan-950/40 px-3 py-1 text-sm font-medium text-cyan-200 border border-cyan-800/60 shadow-sm flex items-center gap-1.5"
                        >
                          <span>{s.skill_name}</span>
                          <span className="text-cyan-400 text-xs font-mono font-bold">{s.confidence_score.toFixed(2)}</span>
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {groupedSkills.resume.length === 0 && groupedSkills.semantic.length === 0 && (
                  <div className="text-center py-8 text-slate-500">
                    <svg className="mx-auto w-12 h-12 mb-3 text-slate-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    <p>No skills extracted yet. Wait for parsing to complete.</p>
                  </div>
                )}

                <Button
                  disabled={busy || detail.parsed_status !== "done"}
                  onClick={startInterview}
                  fullWidth
                  isLoading={busy}
                  size="lg"
                  className="mt-4 font-semibold shadow-lg shadow-cyan-500/10"
                >
                  <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                  </svg>
                  Launch AI Interview (5 Questions)
                </Button>
              </AnimatedCard>
            ) : (
              <AnimatedCard delay={0.1} className="text-center py-16 border-dashed border-slate-800">
                <div className="w-16 h-16 mx-auto rounded-2xl bg-slate-800/40 border border-slate-700/50 flex items-center justify-center mb-4">
                  <svg className="w-8 h-8 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                </div>
                <h3 className="text-lg font-medium mb-1.5 text-slate-200">Select a Resume</h3>
                <p className="text-slate-400 text-sm max-w-xs mx-auto">
                  Choose a resume from the list on the left to review extracted skills and launch your mock interview session.
                </p>
              </AnimatedCard>
            )}
          </FadeInSection>
        </div>

        <section className="mt-10">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-slate-100 flex items-center gap-2">
              <span>Interview History</span>
              <span className="text-xs bg-slate-800 px-2 py-0.5 rounded-full text-slate-400 font-normal">
                {sessions.length}
              </span>
            </h2>
          </div>
          {sessions.length === 0 ? (
            <div className="rounded-2xl border border-slate-800/80 bg-slate-900/30 p-8 text-center text-slate-400 text-sm">
              <p>Completed and in-progress interviews will appear here automatically.</p>
            </div>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {sessions.map((session) => {
                const questions = session.questions || [];
                const answered = questions.filter((q) => q.user_answer).length;
                const scores = questions.map((q) => q.score).filter((score) => score != null);
                const average = scores.length ? (scores.reduce((sum, score) => sum + score, 0) / scores.length).toFixed(1) : null;
                return (
                  <motion.div
                    key={session.id}
                    whileHover={{ y: -3, transition: { duration: 0.2 } }}
                    whileTap={{ scale: 0.98 }}
                    className="cursor-pointer rounded-2xl border border-slate-800/80 bg-slate-900/60 p-5 backdrop-blur-md shadow-md hover:border-slate-700 hover:shadow-cyan-950/20 transition-all"
                    onClick={() => navigate(`/interview/${session.id}`)}
                  >
                    <div className="flex items-center justify-between gap-3 mb-2">
                      <span className="font-semibold text-slate-200">Session #{session.id}</span>
                      <span className={session.ended_at ? "badge-success" : "badge-processing"}>
                        {session.ended_at ? "Complete" : "In Progress"}
                      </span>
                    </div>
                    <p className="text-sm text-slate-400">
                      {answered}/{questions.length} answered
                      {average ? (
                        <span className="ml-1.5 text-cyan-400 font-mono font-medium">&bull; Avg {average}/10</span>
                      ) : ""}
                    </p>
                    <p className="mt-2 text-xs text-slate-500 font-mono">
                      {new Date(session.started_at).toLocaleString()}
                    </p>
                  </motion.div>
                );
              })}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
