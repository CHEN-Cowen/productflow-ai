import { useEffect, useState } from "react";
import { api, formatTime, statusLabel } from "../api";
import { Badge, Empty, ErrorBox, Field, Loading, Notice, Section, statusTone } from "../ui";
import { OutputCard } from "../components";
import { navigate, productPath } from "../router";

export default function Reviews() {
  const [status, setStatus] = useState("pending");
  const [kind, setKind] = useState("");
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const query = new URLSearchParams();
      if (status) query.set("status", status);
      if (kind) query.set("kind", kind);
      const data = await api.get(`/library/outputs?${query.toString()}`);
      setItems(data.items);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [status, kind]);

  return (
    <>
      <div className="topbar">
        <div>
          <div className="crumbs">质量审核</div>
          <h1>成品审核队列</h1>
          <p className="page-sub">核对参考图与成品；驳回必须写明原因，未通过不得正式下载，不合格结果保留复盘。</p>
        </div>
      </div>

      <Section title="筛选" subtitle="待审核 → 通过/驳回；商品版本更新后旧成品自动进入待复审">
        <div className="filters">
          <Field label="审核状态">
            <select value={status} onChange={(event) => setStatus(event.target.value)}>
              <option value="">全部</option>
              <option value="pending">待审核</option>
              <option value="approved">已通过</option>
              <option value="rejected">已驳回</option>
            </select>
          </Field>
          <Field label="成品类型">
            <select value={kind} onChange={(event) => setKind(event.target.value)}>
              <option value="">全部</option>
              <option value="image">商品图</option>
              <option value="video">短视频</option>
            </select>
          </Field>
        </div>
        {status === "pending" && items.length > 0 && (
          <Notice tone="warn">共 {items.length} 个待审核成品；通过与驳回都会写入审核记录。</Notice>
        )}
      </Section>

      {loading ? <Loading /> : error ? <ErrorBox error={error} onRetry={load} /> : items.length === 0 ? (
        <Section title="队列"><Empty title="当前筛选下没有成品" hint="生成图片或视频后会出现在这里" /></Section>
      ) : (
        <div className="stack">
          {items.map((output: any) => (
            <Section key={output.id}
                     title={`${output.kind === "video" ? "短视频" : "商品图"} · ${output.product_name}`}
                     subtitle={`${output.plan?.scene} · 版本 v${output.plan?.version} · ${formatTime(output.created_at)}`}
                     actions={<>
                       <Badge tone={statusTone(output.status)}>{statusLabel(output.status)}</Badge>
                       {output.needs_review && <Badge tone="danger">待复审</Badge>}
                     </>}>
              <div className="row gap wrap mb">
                <button className="btn btn-small btn-ghost" onClick={() => navigate(productPath(output.product_id, "quality"))}>
                  打开商品审核页
                </button>
                <span className="muted small">来源素材：{output.sources?.map((item: any) => item.name).join("、") || "—"}</span>
              </div>
              <OutputCard output={output} onChanged={load} />
            </Section>
          ))}
        </div>
      )}
    </>
  );
}
