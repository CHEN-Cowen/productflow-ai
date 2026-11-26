import React, { useEffect, useRef } from "react";
import { ApiError } from "./api";

export function Badge({ tone = "default", children }: { tone?: string; children: React.ReactNode }) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}

export function statusTone(status: string): string {
  if (["confirmed", "approved", "success", "completed", "ok", "verified"].includes(status)) return "success";
  if (["failed", "rejected", "error"].includes(status)) return "danger";
  if (["pending", "reviewing", "draft", "running"].includes(status)) return "warn";
  return "default";
}

export function Loading({ label = "加载中…" }: { label?: string }) {
  return (
    <div className="loading">
      <span className="spinner" /> {label}
    </div>
  );
}

export function ErrorBox({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const apiError = error instanceof ApiError ? error : null;
  const message = error instanceof Error ? error.message : String(error || "未知错误");
  return (
    <div className="error-box" role="alert">
      <div className="error-title">操作未完成</div>
      <div>{message}</div>
      {apiError?.hint && <div className="muted small">提示：{apiError.hint}</div>}
      {apiError?.code && <div className="muted small">错误类别：{apiError.code}</div>}
      {onRetry && (
        <button type="button" className="btn btn-ghost btn-small" onClick={onRetry}>
          重试
        </button>
      )}
    </div>
  );
}

export function Empty({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="empty">
      <div className="empty-title">{title}</div>
      {hint && <div className="muted">{hint}</div>}
    </div>
  );
}

export function Section({
  title,
  subtitle,
  actions,
  children,
  id,
}: {
  title: string;
  subtitle?: string;
  actions?: React.ReactNode;
  children: React.ReactNode;
  id?: string;
}) {
  return (
    <section className="card" id={id}>
      <header className="card-head">
        <div>
          <h2>{title}</h2>

        </div>
        {actions && <div className="row gap">{actions}</div>}
      </header>
      {children}
    </section>
  );
}

export function Field({
  label,
  required,
  hint,
  children,
}: {
  label: string;
  required?: boolean;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="field">
      <span className="field-label">
        {label}
        {required ? <em className="required" aria-label="必填">*</em> : null}
      </span>
      {children}
      {hint && <span className="muted small">{hint}</span>}
    </label>
  );
}

export function Stat({ label, value, hint }: { label: string; value: React.ReactNode; hint?: string }) {
  return (
    <div className="stat">
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      {hint && <div className="muted small">{hint}</div>}
    </div>
  );
}

export function Notice({ tone = "info", children }: { tone?: string; children: React.ReactNode }) {
  return <div className={`notice notice-${tone}`}>{children}</div>;
}

export function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => { const dialog = ref.current!; dialog.showModal(); return () => dialog.close(); }, []);
  return <dialog ref={ref} className="modal" aria-label={title} onCancel={event => { event.preventDefault(); onClose(); }} onClick={event => { if(event.target===ref.current)onClose(); }}><div className="modal-content"><div className="row between gap mb"><h2>{title}</h2><button type="button" className="btn btn-ghost btn-small" aria-label="关闭弹窗" onClick={onClose}>✕</button></div>{children}</div></dialog>;
}
