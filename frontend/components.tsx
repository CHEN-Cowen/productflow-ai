import { useState } from "react";
import { api, angleLabel, errorText, formatSize, formatTime, statusLabel } from "./api";
import { Badge, ErrorBox, Modal, statusTone } from "./ui";

export function RunSteps({ run }: { run: any }) {
  return (
    <div className="stack" style={{ gap: 6 }}>
      <div className="row gap wrap">
        <Badge tone={statusTone(run.status)}>{statusLabel(run.status)}</Badge>
        <span className="muted small">{({ image_generation: "图片生产", video_generation: "视频生产", content_planning: "内容策划" } as Record<string, string>)[run.workflow_type] || "资料处理"}</span>
        <span className="muted small">{formatTime(run.created_at)}</span>
      </div>
      <div className="steps">
        {run.steps.map((step: any) => (
          <span key={step.name} className={`step ${step.status}`} title={step.detail}>
            <span className="step-dot" /> {step.name}
            {step.detail ? `：${step.detail}` : ""}
          </span>
        ))}
      </div>
      {run.error && <div className="muted small">失败原因：{run.error}</div>}
    </div>
  );
}

export function OutputCard({
  output,
  onChanged,
  allowReview = true,
  allowDownload = true,
}: {
  output: any;
  onChanged?: () => void;
  allowReview?: boolean;
  allowDownload?: boolean;
}) {
  const [note, setNote] = useState("");
  const [previewing, setPreviewing] = useState(false);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [revising, setRevising] = useState(false);
  const [prompt, setPrompt] = useState(output.prompt || "");
  const [message, setMessage] = useState("");

  async function review(approved: boolean) {
    setBusy(approved ? "approve" : "reject");
    setError(null);
    setMessage("");
    try {
      await api.put(`/outputs/${output.id}/review`, { approved, note });
      setNote("");
      setMessage(approved ? "已通过审核" : "已驳回，成品不可正式下载");
      onChanged?.();
    } catch (err) {
      setError(err);
    } finally {
      setBusy("");
    }
  }

  async function revise() {
    setBusy("revise");
    setError(null);
    try {
      await api.post(`/outputs/${output.id}/revise`, { prompt });
      setRevising(false);
      setMessage("已创建修订任务，新候选进入待审核队列");
      onChanged?.();
    } catch (err) {
      setError(err);
    } finally {
      setBusy("");
    }
  }

  return (
    <div className="asset-card">
      <button type="button" className="media-frame media-preview" aria-label={`预览${output.product_name}${output.kind === "video" ? "视频" : "图片"}`} onClick={() => setPreviewing(true)}>
        {output.kind === "video" ? <><video src={output.url} muted preload="metadata"/><span className="play-overlay" aria-hidden="true">▷</span></> : <img src={output.url} alt={output.product_name}/>}
      </button>
      {previewing && <Modal title={output.product_name + (output.kind === "video" ? " · 视频" : " · 图片")} onClose={() => setPreviewing(false)}><div className="media-frame">{output.kind === "video" ? <video src={output.url} controls autoPlay preload="metadata"/> : <img src={output.url} alt={output.product_name}/>}</div></Modal>}
      <div className="row gap wrap">
        <Badge tone="accent">{output.kind === "video" ? "短视频" : "商品图"}</Badge>
        <Badge tone={statusTone(output.status)}>{statusLabel(output.status)}</Badge>
        {output.needs_review && <Badge tone="danger">待复审</Badge>}
        <span className="muted small">{formatSize(output.size)}</span>
      </div>
      <div className="small">
        <div className="strong">{output.product_name}</div>
        <div className="muted">
          {output.plan?.scene || "—"} · 版本 v{output.plan?.version ?? "?"} · 第 {output.attempt} 次
        </div>
        {output.kind === "video" && (
          <div className="muted">
            {output.params?.duration} 秒 · {output.params?.width}×{output.params?.height} · {output.params?.codec}
          </div>
        )}
        <details><summary>生成信息</summary><div className="muted">{output.model || output.provider || "—"} · {formatTime(output.created_at)}</div><div className="muted">来源素材：{output.sources?.map((item: any) => `${item.name}（${angleLabel(item.view_angle)}）`).join("、") || "—"}</div></details>
        {output.needs_review && <div className="muted">{output.stale_reason}</div>}
      </div>
      {output.note && <div className="small muted">审核备注：{output.note}</div>}
      {error !== null && <ErrorBox error={error} />}
      {message && <div className="notice notice-success small">{message}</div>}

      {allowReview && (
        <div className="stack" style={{ gap: 6 }}>
          <input value={note} onChange={(event) => setNote(event.target.value)}
                 placeholder="审核说明（驳回必填，通过可留空）" />
          <div className="toolbar">
            <button className="btn btn-small" disabled={!!busy || output.needs_review}
                    onClick={() => review(true)}>
              {busy === "approve" ? "提交中…" : "通过审核"}
            </button>
            <button className="btn btn-small btn-ghost" disabled={!!busy || output.needs_review}
                    onClick={() => review(false)}>
              {busy === "reject" ? "提交中…" : "驳回"}
            </button>
            <button className="btn btn-small btn-ghost" onClick={() => setRevising((value) => !value)}>
              修订任务
            </button>
          </div>
          {revising && (
            <div className="stack" style={{ gap: 6 }}>
              <textarea value={prompt} onChange={(event) => setPrompt(event.target.value)}
                        placeholder="修订后的提示词，需保留已确认商品事实" />
              <button className="btn btn-small btn-soft" disabled={!!busy || !prompt.trim()} onClick={revise}>
                {busy === "revise" ? "创建中…" : "创建修订任务"}
              </button>
            </div>
          )}
        </div>
      )}

      {allowDownload && (
        <div className="row gap">
          {output.status === "approved" && !output.needs_review ? (
            <a className="btn btn-small btn-ghost" href={output.download_url}>下载正式成品</a>
          ) : (
            <span className="muted small">审核通过后才可下载正式文件</span>
          )}
        </div>
      )}

    </div>
  );
}
