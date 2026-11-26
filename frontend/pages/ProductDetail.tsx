import { useEffect, useState } from "react";
import { api, formatSize, formatTime, statusLabel } from "../api";
import { Badge, Empty, ErrorBox, Field, Loading, Notice, Section, statusTone } from "../ui";
import { RunSteps } from "../components";
import { locatorText } from "../product-utils";
import { AssetsTab, DocsTab, PlansTab, ProductionTab, QualityTab, type TabProps } from "./product-tabs";
import { navigate, productPath } from "../router";

const TABS = [
  { key: "overview", label: "概览与事实" },
  { key: "docs", label: "资料与导入" },
  { key: "assets", label: "素材" },
  { key: "plans", label: "策划" },
  { key: "production", label: "生产" },
  { key: "quality", label: "质量审核" },
  { key: "versions", label: "版本与影响" },
];

export default function ProductDetail({ productId, tab }: { productId: string; tab: string }) {
  const [detail, setDetail] = useState<any>(null);
  const [models, setModels] = useState<any>(null);
  const [importsList, setImportsList] = useState<any[]>([]);
  const [plans, setPlans] = useState<any[]>([]);
  const [outputs, setOutputs] = useState<any[]>([]);
  const [runs, setRuns] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);

  async function reload() {
    const [detailData, importsData, plansData, outputsData, runsData, modelData] = await Promise.all([
      api.get(`/products/${productId}`),
      api.get(`/products/${productId}/imports`),
      api.get(`/products/${productId}/plans`),
      api.get(`/products/${productId}/outputs`),
      api.get(`/products/${productId}/runs`),
      models ? Promise.resolve(models) : api.get("/models/status"),
    ]);
    setDetail(detailData);
    setImportsList(importsData);
    setPlans(plansData);
    setOutputs(outputsData);
    setRuns(runsData);
    setModels(modelData);
  }

  async function load() {
    setLoading(true);
    setError(null);
    try {
      await reload();
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [productId]);

  if (loading) return <Loading label="加载商品档案…" />;
  if (error) return <ErrorBox error={error} onRetry={load} />;
  if (!detail) return <Empty title="商品不存在" />;

  const goTab = (next: string) => navigate(productPath(productId, next));
  const props: TabProps = { productId, detail, models, importsList, plans, outputs, runs, reload, goTab };

  return (
    <>
      <div className="topbar">
        <div>
          <div className="crumbs"><a href="#/products">商品数据中心</a> / {detail.product.id}</div>
          <h1>{detail.product.name}</h1>
          <div className="row gap wrap mt">
            <Badge tone="accent">{detail.category.name} v{detail.category.version}</Badge>
            <Badge tone={statusTone(detail.product.status)}>{detail.product.status === "confirmed" ? "已确认" : "草稿"}</Badge>
            {detail.latest_version ? (
              <Badge tone="success">当前版本 v{detail.latest_version.version}</Badge>
            ) : (
              <Badge tone="warn">尚无确认版本</Badge>
            )}
            <span className="muted small">商品编号 {detail.product.id}</span>
            {detail.product.origin && <span className="muted small">产地 {detail.product.origin}</span>}
          </div>
        </div>
        <div className="toolbar">
          <button className="btn btn-small btn-ghost" onClick={() => goTab("docs")}>上传资料</button>
          <button className="btn btn-small btn-ghost" onClick={() => goTab("plans")}>内容策划</button>
          <button className="btn btn-small btn-ghost" onClick={() => goTab("quality")}>审核成品</button>
        </div>
      </div>

      <div className="grid four">
        <div className="stat"><div className="stat-label">资料</div><div className="stat-value">{detail.counts.sources}</div><div className="muted small">{detail.sources.filter((item: any) => item.kind === "image").length} 图 · {detail.sources.filter((item: any) => item.kind === "document").length} 文档</div></div>
        <div className="stat"><div className="stat-label">必填完整度</div><div className="stat-value">{detail.completeness.required_filled}/{detail.completeness.required_total}</div><div className="muted small">{detail.completeness.missing.length ? `待补：${detail.completeness.missing.join("、")}` : "已齐全"}</div></div>
        <div className="stat"><div className="stat-label">策划</div><div className="stat-value">{detail.counts.plans}</div><div className="muted small">已确认 {plans.filter((plan) => plan.status === "confirmed").length}</div></div>
        <div className="stat"><div className="stat-label">成品 / 待审核</div><div className="stat-value">{detail.counts.outputs}</div><div className="muted small">{detail.counts.pending_reviews} 个待审核</div></div>
      </div>

      <div className="tabs mt">
        {TABS.map((item) => (
          <button key={item.key} className={tab === item.key ? "active" : ""} onClick={() => goTab(item.key)}>{item.label}</button>
        ))}
      </div>

      {tab === "overview" && <OverviewTab {...props} />}
      {tab === "docs" && <DocsTab {...props} />}
      {tab === "assets" && <AssetsTab {...props} />}
      {tab === "plans" && <PlansTab {...props} />}
      {tab === "production" && <ProductionTab {...props} />}
      {tab === "quality" && <QualityTab {...props} />}
      {tab === "versions" && <VersionsTab {...props} />}
    </>
  );
}

function OverviewTab({ productId, detail, runs, reload }: TabProps) {
  const [form, setForm] = useState({
    name: detail.product.name, category_id: detail.product.category_id,
    brand: detail.product.brand, origin: detail.product.origin,
    description: detail.product.description,
  });
  const [busy, setBusy] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [message, setMessage] = useState("");
  const [impact, setImpact] = useState<any>(null);
  const [skuCode, setSkuCode] = useState("");
  const [skuAttributes, setSkuAttributes] = useState('{"color": ""}');
  const labels: Record<string, string> = {};
  for (const attr of detail.category.schema.attributes) labels[attr.key] = attr.label;
  const fields = detail.latest_version?.fields || {};
  const provenance = detail.latest_version?.provenance || {};

  useEffect(() => {
    api.get(`/products/${productId}/impact`).then(setImpact).catch(() => setImpact(null));
  }, [productId, detail.latest_version?.id]);

  async function save() {
    setBusy("save");
    setError(null);
    setMessage("");
    try {
      await api.put(`/products/${productId}`, form);
      setMessage("商品基础信息已保存");
      await reload();
    } catch (err) {
      setError(err);
    } finally {
      setBusy("");
    }
  }

  async function addSku() {
    setBusy("sku");
    setError(null);
    setMessage("");
    try {
      const attributes = JSON.parse(skuAttributes || "{}");
      await api.post(`/products/${productId}/skus`, { sku_code: skuCode, attributes });
      setSkuCode("");
      setMessage("SKU 已添加");
      await reload();
    } catch (err) {
      setError(err);
    } finally {
      setBusy("");
    }
  }

  return (
    <>
      <Section title="商品基础信息" subtitle="基础信息变更记录在审核日志中；品类字段事实以不可变版本为准">
        <div className="form-grid">
          <Field label="商品名称" required><input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} /></Field>
          <Field label="品类模板"><select value={form.category_id} onChange={(event) => setForm({ ...form, category_id: event.target.value })}>
            <option value={detail.category.id}>{detail.category.name}</option>
          </select></Field>
          <Field label="品牌"><input value={form.brand} onChange={(event) => setForm({ ...form, brand: event.target.value })} /></Field>
          <Field label="产地"><input value={form.origin} onChange={(event) => setForm({ ...form, origin: event.target.value })} /></Field>
          <Field label="备注"><input value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} /></Field>
        </div>
        {error !== null && <div className="mt"><ErrorBox error={error} /></div>}
        {message && <div className="notice notice-success mt">{message}</div>}
        <div className="form-actions"><button className="btn" disabled={!!busy} onClick={save}>{busy === "save" ? "保存中…" : "保存基础信息"}</button></div>
      </Section>

      <Section title="已确认商品事实" subtitle="每条事实保留标准值、来源文件、定位与原文；候选值不会直接进入发布内容">
        {!detail.latest_version ? (
          <Notice tone="warn">还没有已确认版本。请到“资料与导入”上传资料并完成人工确认。</Notice>
        ) : (
          <>
            <div className="muted small mb">
              版本 v{detail.latest_version.version} · SKU {detail.latest_version.sku || "未指定"} · 确认于 {formatTime(detail.latest_version.created_at)}
              {detail.latest_version.note && ` · ${detail.latest_version.note}`}
            </div>
            <table>
              <thead><tr><th>字段</th><th>标准值</th><th>来源与定位</th><th>原文</th></tr></thead>
              <tbody>
                {detail.category.schema.attributes.map((attr: any) => {
                  const proof = provenance[attr.key];
                  return (
                    <tr key={attr.key}>
                      <td>{attr.label}{attr.required && <Badge tone="accent">必填</Badge>}</td>
                      <td>{fields[attr.key] || <span className="muted">待补充</span>}</td>
                      <td className="small">
                        {proof ? (
                          proof.method === "manual"
                            ? <>人工补充 · 依据：{proof.basis || "—"}</>
                            : <>{proof.source_name} · {locatorText(proof.locator)}</>
                        ) : <span className="muted">—</span>}
                      </td>
                      <td className="quote small">{proof?.quote || "—"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            <div className="muted small mt">缺失字段：{detail.completeness.missing.length ? detail.completeness.missing.map((key: string) => labels[key] || key).join("、") : "无"}</div>
          </>
        )}
      </Section>

      <Section title={`SKU（${detail.skus.length}）`} subtitle="同一商品可管理多个 SKU，规格可与素材关联">
        {detail.skus.length > 0 && (
          <table>
            <thead><tr><th>SKU 编码</th><th>规格</th><th>创建时间</th></tr></thead>
            <tbody>
              {detail.skus.map((sku: any) => (
                <tr key={sku.id}>
                  <td className="mono">{sku.sku_code}</td>
                  <td className="small">{JSON.stringify(sku.attributes)}</td>
                  <td className="muted small">{formatTime(sku.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <div className="form-grid mt">
          <Field label="SKU 编码" required><input value={skuCode} onChange={(event) => setSkuCode(event.target.value.toUpperCase())} placeholder="BP01-BEIGE" /></Field>
          <Field label="规格 JSON" hint="例如 {&quot;color&quot;:&quot;暖米白&quot;,&quot;size&quot;:&quot;M&quot;}">
            <input value={skuAttributes} onChange={(event) => setSkuAttributes(event.target.value)} />
          </Field>
        </div>
        <div className="form-actions">
          <button className="btn btn-small" disabled={!!busy || !skuCode.trim()} onClick={addSku}>{busy === "sku" ? "添加中…" : "添加 SKU"}</button>
        </div>
      </Section>

      <Section title="版本影响" subtitle="商品事实更新后，按实际引用字段与版本定位受影响成品">
        {!impact || !impact.changed_fields?.length ? (
          <div className="muted small">暂无版本差异{impact?.note ? `。${impact.note}` : ""}</div>
        ) : (
          <>
            <div className="pill-list mb">
              {impact.changed_fields.map((field: any) => (
                <Badge key={field.field} tone="warn">{field.label}：{field.from || "空"} → {field.to || "空"}</Badge>
              ))}
            </div>
            <div className="small">受影响策划 {impact.affected_plans.length} 个 · 成品 {impact.affected_outputs} 个。{impact.note}</div>
            <div className="form-actions"><button className="btn btn-small btn-ghost" onClick={() => navigate(productPath(productId, "versions"))}>查看版本与影响</button></div>
          </>
        )}
      </Section>

      <Section title="最近任务" subtitle="导入、策划与生产执行记录">
        {runs.length === 0 ? <Empty title="暂无任务" /> : runs.slice(0, 5).map((run: any) => <RunSteps key={run.id} run={run} />)}
      </Section>
    </>
  );
}

function VersionsTab({ productId, detail }: TabProps) {
  const versions = detail.versions || [];
  const [from, setFrom] = useState<number | "">(versions[1]?.version ?? "");
  const [to, setTo] = useState<number | "">(versions[0]?.version ?? "");
  const [diff, setDiff] = useState<any>(null);
  const [impact, setImpact] = useState<any>(null);
  const [error, setError] = useState<unknown>(null);
  const [selected, setSelected] = useState<any>(versions[0] || null);

  useEffect(() => {
    Promise.all([
      api.get(`/products/${productId}/versions/diff?from_version=${from || ""}&to_version=${to || ""}`),
      api.get(`/products/${productId}/impact`),
    ]).then(([diffData, impactData]) => {
      setDiff(diffData);
      setImpact(impactData);
      setError(null);
    }).catch(setError);
  }, [productId, from, to]);

  if (!versions.length) return <Section title="版本"><Empty title="还没有版本" hint="完成一次人工确认后生成不可变版本" /></Section>;

  return (
    <>
      <Section title="不可变版本历史" subtitle="确认入库后写入新版本，旧版本永久保留，可回查差异与来源">
        <table>
          <thead><tr><th>版本</th><th>字段</th><th>SKU</th><th>备注</th><th>确认时间</th><th></th></tr></thead>
          <tbody>
            {versions.map((version: any) => (
              <tr key={version.id}>
                <td><Badge tone={version.is_current ? "success" : "default"}>v{version.version}{version.is_current ? " · 当前" : ""}</Badge></td>
                <td className="muted small">{Object.keys(version.fields).length} 个</td>
                <td className="small">{version.sku || "—"}</td>
                <td className="small">{version.note || "—"}</td>
                <td className="muted small">{formatTime(version.created_at)}</td>
                <td><button className="btn btn-small btn-ghost" onClick={() => setSelected(version)}>查看字段</button></td>
              </tr>
            ))}
          </tbody>
        </table>
        {selected && (
          <div className="mt">
            <div className="strong mb">v{selected.version} 字段与来源</div>
            <table>
              <thead><tr><th>字段</th><th>标准值</th><th>来源</th><th>原文</th></tr></thead>
              <tbody>
                {detail.category.schema.attributes.map((attr: any) => {
                  const proof = selected.provenance?.[attr.key];
                  return (
                    <tr key={attr.key}>
                      <td>{attr.label}</td>
                      <td>{selected.fields[attr.key] || "—"}</td>
                      <td className="small">{proof ? (proof.method === "manual" ? `人工 · ${proof.basis || "—"}` : `${proof.source_name} · ${locatorText(proof.locator)}`) : "—"}</td>
                      <td className="quote small">{proof?.quote || "—"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Section>

      <Section title="版本差异" subtitle="按字段比较两个版本，媒体单位已统一为 cm 与 g">
        <div className="filters">
          <Field label="起始版本"><select value={from} onChange={(event) => setFrom(Number(event.target.value))}>
            <option value="">自动</option>
            {versions.map((version: any) => <option key={version.id} value={version.version}>v{version.version}</option>)}
          </select></Field>
          <Field label="目标版本"><select value={to} onChange={(event) => setTo(Number(event.target.value))}>
            <option value="">最新</option>
            {versions.map((version: any) => <option key={version.id} value={version.version}>v{version.version}</option>)}
          </select></Field>
        </div>
        {error !== null && <ErrorBox error={error} />}
        {diff?.changed?.length ? (
          <table>
            <thead><tr><th>字段</th><th>旧值</th><th>新值</th></tr></thead>
            <tbody>
              {diff.changed.map((item: any) => (
                <tr key={item.field}><td>{item.label}</td><td>{item.from || "空"}</td><td>{item.to || "空"}</td></tr>
              ))}
            </tbody>
          </table>
        ) : <div className="muted small">{diff?.message || "无字段差异"}</div>}
      </Section>

      <Section title="受影响成品" subtitle="旧版本成品暂停正式下载，需重新生成并复审">
        {!impact ? <Loading /> : (
          <>
            <div className="muted small mb">{impact.note} · 受影响成品 {impact.affected_outputs} 个</div>
            {impact.affected_plans?.length === 0 ? <div className="muted small">暂无受影响策划</div> : (
              <table>
                <thead><tr><th>策划</th><th>场景</th><th>版本</th><th>成品</th></tr></thead>
                <tbody>
                  {impact.affected_plans.map((plan: any) => (
                    <tr key={plan.id}>
                      <td className="mono">{plan.id.slice(0, 8)}</td>
                      <td>{plan.scene}</td>
                      <td>v{versions.find((version: any) => version.id === plan.version_id)?.version ?? plan.version_id}</td>
                      <td className="small">{plan.outputs.map((output: any) => `${output.kind}（${statusLabel(output.status)}）`).join("、") || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </>
        )}
      </Section>
    </>
  );
}
