'use client';

import type { NextPage } from 'next';
import React, { useState, useRef } from 'react';
import { DEFAULT_BRIEF } from '@/lib/brief';
import { ReportMarkdown, safeExternalHref } from './report';

const DEFAULT_DRUG_INPUT = DEFAULT_BRIEF;

const RUN_ID_STORAGE_KEY = 'nimble-patent-cliff-run-id';
const POLL_INTERVAL_MS = 5000;
const POLL_TIMEOUT_MS = 15 * 60 * 1000;

const Home: NextPage = () => {
  const [task, setTask] = useState(DEFAULT_DRUG_INPUT);
  const [runId, setRunId] = useState<string | null>(null);
  const [assistantText, setAssistantText] = useState<string | null>(null);
  const [result, setResult] = useState<any | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [copied, setCopied] = useState(false);
  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pollGenerationRef = useRef(0);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  React.useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = textareaRef.current.scrollHeight + 'px';
    }
  }, [task]);

  // A running clock, so a 5-15 minute wait shows visible progress.
  React.useEffect(() => {
    if (!isRunning) return;
    const started = Date.now() - elapsed * 1000;
    const tick = setInterval(() => setElapsed(Math.floor((Date.now() - started) / 1000)), 1000);
    return () => clearInterval(tick);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isRunning]);

  React.useEffect(() => {
    const savedRunId = window.sessionStorage.getItem(RUN_ID_STORAGE_KEY);
    if (savedRunId) {
      setRunId(savedRunId);
      setAssistantText('Retrieving your patent-cliff research run…');
      setIsRunning(true);
      // Check straight away rather than after the poll interval. The run may
      // already be finished, in which case this restores the report at once.
      pollForResult(savedRunId, { immediate: true });
    }

    return () => stopPolling();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /** Cancel any scheduled poll and invalidate the checks already in flight. */
  function stopPolling() {
    if (pollRef.current) clearTimeout(pollRef.current);
    pollRef.current = null;
    pollGenerationRef.current += 1;
  }

  async function handleStart() {
    if (!task.trim() || isRunning) return;
    stopPolling();
    setElapsed(0);
    setError(null);
    setAssistantText(null);
    setResult(null);
    setRunId(null);
    setIsRunning(true);

    try {
      const res = await fetch('/api/research', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task: task.trim() }),
      });

      const data = await res.json();
      if (!res.ok || data.error) throw new Error(data.error || 'Failed to start research.');
      if (!data.runId) throw new Error('No runId returned.');

      setRunId(data.runId);
      window.sessionStorage.setItem(RUN_ID_STORAGE_KEY, data.runId);
      setAssistantText(data.text);
      pollForResult(data.runId);
    } catch (err: any) {
      setError(err.message || 'Failed to start research.');
      setIsRunning(false);
    }
  }

  /**
   * Check the run, then schedule the next check only once the previous one has
   * come back. A fixed interval would stack overlapping requests whenever a
   * check takes longer than the interval.
   */
  function pollForResult(runId: string, options: { immediate?: boolean } = {}) {
    const generation = ++pollGenerationRef.current;
    const deadline = Date.now() + POLL_TIMEOUT_MS;

    const check = async () => {
      if (pollGenerationRef.current !== generation) return;

      try {
        const res = await fetch('/api/research', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ runId }),
        });

        const data = await res.json();
        if (pollGenerationRef.current !== generation) return;

        if (!res.ok || data.error) {
          throw new Error(data.error || 'Failed to check research status.');
        }

        setAssistantText(data.text);

        if (data.result?.ready) {
          setResult(data.result);
          // Keep the run ID. Nimble holds the completed run, so a refresh in
          // this tab can fetch the finished report straight back. Retrieving a
          // completed run costs nothing: no model call, and it returns at once.
          window.sessionStorage.setItem(RUN_ID_STORAGE_KEY, runId);
          setIsRunning(false);
          return;
        }

        if (Date.now() >= deadline) {
          setAssistantText(
            `Stopped checking after 15 minutes. The run is still going on Nimble's side — ` +
            `resume it any time with: npm run cli:resume -- ${runId}`
          );
          setIsRunning(false);
          return;
        }

        pollRef.current = setTimeout(check, POLL_INTERVAL_MS);
      } catch (err: any) {
        if (pollGenerationRef.current !== generation) return;
        // Keep the run ID: the run itself is unaffected by a failed check, so
        // a refresh should be able to pick it back up.
        setError(err.message || 'Failed to check research status.');
        setIsRunning(false);
      }
    };

    if (options.immediate) void check();
    else pollRef.current = setTimeout(check, POLL_INTERVAL_MS);
  }

  function handleNewResearch() {
    stopPolling();
    window.sessionStorage.removeItem(RUN_ID_STORAGE_KEY);
    setTask(DEFAULT_DRUG_INPUT);
    setRunId(null);
    setAssistantText(null);
    setResult(null);
    setError(null);
    setIsRunning(false);
    setElapsed(0);
    setCopied(false);
  }

  async function copyResumeCommand() {
    if (!runId) return;
    try {
      await navigator.clipboard.writeText(`npm run cli:resume -- ${runId}`);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard access can be blocked; the command stays selectable either way.
    }
  }

  // A completed run returns either prose or structured JSON. Render both, so a
  // JSON-output agent still gets the report panel and its trust metadata.
  const reportText = !result?.ready
    ? null
    : result.output?.type === 'json'
      ? JSON.stringify(result.output.json, null, 2)
      : result.output?.text ?? null;

  const trust = result?.output?.trust;
  const isJsonReport = result?.output?.type === 'json';

  const confidence = String(trust?.confidence ?? '').toLowerCase();
  const badgeClass =
    confidence === 'high' ? 'badge-high' : confidence === 'medium' ? 'badge-medium' : 'badge-low';

  const formattedElapsed = `${Math.floor(elapsed / 60)}:${String(elapsed % 60).padStart(2, '0')}`;

  return (
    <div className="app">
      <main className="shell">
        <header className="masthead">
          <span className="eyebrow">Nimble Web Search Agents</span>
          <h1 className="title">Patent Cliff Monitor</h1>
          <p className="tagline">
            Give it a list of medicines nearing patent expiry. Get back a{' '}
            <strong>cited competitive-intelligence report</strong> on biosimilars, court dockets,
            pricing, and manufacturer response.
          </p>
        </header>

        <section className="composer">
          <div className="composer-label">
            <span>Research brief</span>
          </div>
          <textarea
            ref={textareaRef}
            className="field"
            value={task}
            onChange={e => setTask(e.target.value)}
            disabled={isRunning}
            placeholder="List the medicines you want covered, with patent-expiry context."
            onKeyDown={e => {
              if (e.key === 'Enter' && !e.shiftKey && !isRunning) {
                e.preventDefault();
                handleStart();
              }
            }}
          />
          <div className="composer-actions">
            <span className="hint">
              <span className="kbd">Enter</span> to run, <span className="kbd">Shift</span> +{' '}
              <span className="kbd">Enter</span> for a new line
            </span>
            <button
              className="btn btn-primary"
              onClick={handleStart}
              disabled={isRunning || !task.trim()}
            >
              {isRunning ? 'Researching…' : 'Generate report'}
            </button>
          </div>
        </section>

        {isRunning && (
          <div className="status" role="status" aria-live="polite">
            <span className="pulse" />
            <span>
              {runId
                ? 'Researching across the live web. A full report usually takes 5 to 15 minutes.'
                : 'Starting the research run…'}
            </span>
            <span className="status-meta">{formattedElapsed}</span>
          </div>
        )}

        {error && (
          <div className="alert" role="alert">
            {error}
          </div>
        )}

        {!isRunning && !result && !assistantText && (
          <div className="card">
            <h2 className="card-title">What the report covers</h2>
            <ul className="checklist">
              <li>FDA biosimilar and generic approvals, with dates and manufacturers</li>
              <li>Court dockets: injunctions, IPR decisions, and settlements</li>
              <li>Pricing signals, including WAC and median acquisition cost</li>
              <li>Manufacturer response: line extensions, reformulations, marketing pivots</li>
              <li>Every finding carries a source link and a Nimble confidence grade</li>
            </ul>
          </div>
        )}

        {assistantText && !result?.ready && <div className="note">{assistantText}</div>}

        {result?.ready && reportText && (
          <article className="report">
            <div className="report-header">
              <span className="report-header-title">Report</span>
              {trust?.confidence && (
                <span className={`badge ${badgeClass}`}>{trust.confidence} confidence</span>
              )}
              {trust && (
                <span className="report-stats">
                  {trust.sources.length} sources · {trust.claims.length} cited claims
                </span>
              )}
            </div>
            <div className="report-body">
              {isJsonReport ? (
                <pre className="json-dump">{reportText}</pre>
              ) : (
                <ReportMarkdown markdown={reportText} trust={trust} />
              )}

              {trust && trust.sources.length > 0 && (
                <div className="sources">
                  <h2 className="sources-title">Sources</h2>
                  {trust.sources.map((s: any, i: number) => {
                    // Nimble sources come from the open web. Anything that is
                    // not http(s) is shown as plain text, never as a link.
                    const href = safeExternalHref(s.url);
                    return (
                      <div className="source" key={i}>
                        <span className="chip">{s.type}</span>
                        {href ? (
                          <a href={href} target="_blank" rel="noopener noreferrer">
                            {s.title ?? s.url}
                          </a>
                        ) : (
                          <span className="source-unlinked">{s.title ?? s.url}</span>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </article>
        )}

        {result?.ready && runId && (
          <div className="note">
            <h2 className="card-title">Keep this report</h2>
            Refreshing this tab restores it. Nimble holds the completed run, so you can also fetch
            it from any machine:
            <div className="snippet">
              <code>npm run cli:resume -- {runId}</code>
              <button className="btn btn-ghost btn-tiny" onClick={copyResumeCommand}>
                {copied ? 'Copied' : 'Copy'}
              </button>
            </div>
            Starting a new report clears it from this tab.
          </div>
        )}

        {result?.ready && (
          <div className="footer-actions">
            <button className="btn btn-ghost" onClick={handleNewResearch}>
              Start a new report
            </button>
          </div>
        )}
      </main>
    </div>
  );
};

export default Home;
