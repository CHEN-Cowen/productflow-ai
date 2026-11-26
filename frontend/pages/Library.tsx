import { useEffect, useRef, useState } from "react";
import { ANGLES, ASSET_TYPES, PURPOSES, angleLabel, api, formatSize, formatTime, statusLabel } from "../api";
import { Badge, Empty, ErrorBox, Field, Loading, Section, statusTone } from "../ui";
import { OutputCard } from "../components";
import { navigate, productPath } from "../router";

export default function Library() {
  const [tab, setTab] = useState<"outputs" | "sources">("outputs");
  const [products, setProducts] = useState<any[]>([]);
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [filters, setFilters] = useState({ status: "approved", kind: "", product_id: "", search: "", angle: "", review_status: "", asset_type: "" });

  const requestId = useRef(0);
  const resultKey = JSON.stringify([tab, filters]);
  const [loadedKey, setLoadedKey] = useState("");

  async function loadProducts() {
    try {
      const data = await api.get("/products");
      setProducts(data.items);
    } catch {
      setProducts([]);
    }
  }

  async function load() {
    const request = ++requestId.current;
    setLoading(true);
    setError(null);
    try {
      if (tab === "outputs") {
        const query = new URLSearchParams();
        if (filters.status) query.set("status", filters.status);
        if (filters.kind) query.set("kind", filters.kind);
        if (filters.product_id) query.set("product_id", filters.product_id);
        if (filters.search) query.set("search", filters.search);
        const data = await api.get(`/library/outputs?${query.toString()}`);
        if (request === requestId.current) { setItems(data.items); setLoadedKey(resultKey); }
      } else {
        const query = new URLSearchParams();
        if (filters.product_id) query.set("product_id", filters.product_id);
        if (filters.angle) query.set("angle", filters.angle);
        if (filters.review_status) query.set("review_status", filters.review_status);
        if (filters.asset_type) query.set("asset_type", filters.asset_type);
        if (filters.search) query.set("search", filters.search);
        const data = await api.get(`/assets/sources?${query.toString()}`);
        if (request === requestId.current) { setItems(data.items); setLoadedKey(resultKey); }
      }
    } catch (err) {
      if (request === requestId.current) { setError(err); setLoadedKey(resultKey); }
    } finally {
      if (request === requestId.current) setLoading(false);
    }
  }

  useEffect(() => { loadProducts(); }, []);
  useEffect(() => { const timer = setTimeout(() => { void load(); }, 250); return () => clearTimeout(timer); }, [tab, filters.status, filters.kind, filters.product_id, filters.angle, filters.review_status, filters.asset_type, filters.search]);

  return (
    <>
      <div className="topbar">
        <div>

          <h1>内容资产库</h1>
        </div>
        <div className="toolbar">
          <button className="btn btn-small btn-ghost" onClick={() => navigate("/studio")}>内容生产</button>
        </div>
      </div>

      <div className="tabs">
        <button className={tab === "outputs" ? "active" : ""} onClick={() => { requestId.current++; setTab("outputs"); }}>生成内容</button>
        <button className={tab === "sources" ? "active" : ""} onClick={() => { requestId.current++; setTab("sources"); }}>参考素材</button>
      </div>

      <Section title="筛选" subtitle={tab === "outputs" ? "默认仅显示已通过审核的正式交付成品" : "原始素材保留关联商品、视角、用途与审核状态"}>
        <div className="filters">
          <Field label="商品">
            <select value={filters.product_id} onChange={(event) => setFilters({ ...filters, product_id: event.target.value })}>
              <option value="">全部商品</option>
              {products.map((product) => <option key={product.id} value={product.id}>{product.id} · {product.name}</option>)}
            </select>
          </Field>
          {tab === "outputs" ? (
            <>
              <Field label="状态">
                <select value={filters.status} onChange={(event) => setFilters({ ...filters, status: event.target.value })}>
                  <option value="">全部</option><option value="approved">已通过</option>
                  <option value="pending">待审核</option><option value="rejected">已驳回</option>
                </select>
              </Field>
              <Field label="类型">
                <select value={filters.kind} onChange={(event) => setFilters({ ...filters, kind: event.target.value })}>
                  <option value="">全部</option><option value="image">商品图</option><option value="video">短视频</option>
                </select>
              </Field>
            </>
          ) : (
            <>
              <Field label="视角">
                <select value={filters.angle} onChange={(event) => setFilters({ ...filters, angle: event.target.value })}>
                  <option value="">全部</option>
                  {ANGLES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
                </select>
              </Field>
              <Field label="审核状态">
                <select value={filters.review_status} onChange={(event) => setFilters({ ...filters, review_status: event.target.value })}>
                  <option value="">全部</option><option value="pending">待审核</option>
                  <option value="confirmed">已确认</option><option value="rejected">已废弃</option>
                </select>
              </Field>
              <Field label="素材类型">
                <select value={filters.asset_type} onChange={(event) => setFilters({ ...filters, asset_type: event.target.value })}>
                  <option value="">全部</option>
                  {ASSET_TYPES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
                </select>
              </Field>
            </>
          )}
          <Field label="搜索">
            <input value={filters.search} placeholder="商品或场景关键词"
                   onChange={(event) => setFilters({ ...filters, search: event.target.value })}
                   onKeyDown={(event) => { if (event.key === "Enter") load(); }} />
          </Field>
          <button className="btn btn-small" onClick={load}>查询</button>
        </div>
      </Section>

      {loading || loadedKey !== resultKey ? <Loading /> : error ? <ErrorBox error={error} onRetry={load} /> : items.length === 0 ? (
        <Section title="资产"><Empty title="当前筛选下没有资产" hint={tab === "outputs" ? "成品通过审核后会进入资产库" : "上传参考图并完成视角标注"} /></Section>
      ) : tab === "outputs" ? (
        <div className="grid asset-grid">
          {items.map((output: any) => (
            <div key={output.id} className="stack" style={{ gap: 8 }}>
              <OutputCard output={output} allowReview={false} allowDownload />
              <div className="toolbar">
                <a className="btn btn-small btn-ghost" href={`#${productPath(output.product_id, "plans")}`}>复用素材创建新场景</a>
                <span className="muted small">策划 {output.plan_id.slice(0, 8)} · {formatTime(output.created_at)}</span>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="grid auto">
          {items.map((source: any) => (
            <div className="asset-card" key={source.id}>
              {source.kind === "image" ? <img className="thumb" src={source.url} alt={source.name} /> : <div className="thumb document-thumb">文档</div>}
              <div className="strong ellipsis" title={source.name}>{source.name}</div>
              <div className="row gap wrap">
                <Badge tone={source.view_angle ? "success" : "warn"}>{angleLabel(source.view_angle)}</Badge>
                <Badge tone={statusTone(source.review_status)}>{statusLabel(source.review_status)}</Badge>
                <span className="muted small">{formatSize(source.size)}</span>
              </div>
              <div className="muted small">{source.product_id} · {source.product_name}</div>
              <div className="muted small">{PURPOSES.find((item) => item.value === source.purpose)?.label || source.purpose} · {formatTime(source.created_at)}</div>
              <div className="toolbar">
                <a className="btn btn-small btn-ghost" href={source.url} target="_blank" rel="noreferrer">{source.kind === "image" ? "预览原图" : "查看资料"}</a>
                <a className="btn btn-small btn-ghost" href={`#${productPath(source.product_id, "assets")}`}>管理素材</a>
              </div>
            </div>
          ))}
        </div>
      )}
    </>
  );
}
