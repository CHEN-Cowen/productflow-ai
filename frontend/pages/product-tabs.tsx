import { useEffect, useState } from "react";
import { ANGLES, ASSET_TYPES, PURPOSES, angleLabel, api, formatSize, formatTime, statusLabel } from "../api";
import { Badge, Empty, ErrorBox, Field, Loading, Modal, Notice, Section, statusTone } from "../ui";
import { OutputCard, RunSteps } from "../components";
import { fieldLabels, locatorText, planTemplate } from "../product-utils";
import { navigate, productPath } from "../router";

export type TabProps = {
  productionKind?: "image" | "video";
  productId: string;
  detail: any;
  models: any;
  importsList: any[];
  plans: any[];
  outputs: any[];
  runs: any[];
  reload: () => Promise<void>;
  goTab: (tab: string) => void;
};

/* ---------------- 资料与导入 ---------------- */

export function DocsTab(props: TabProps) {
  const { productId, detail, models, importsList, reload } = props;
  const docs = (detail.sources || []).filter((source: any) => source.kind === "document");
  const [selected, setSelected] = useState<string[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [uploadMeta, setUploadMeta] = useState({ sku_id: "", purpose: "spec", view_angle: "" });
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<unknown>(null);
  const [message, setMessage] = useState("");
  const [manual, setManual] = useState(!models?.llm?.configured);
  const [extracting, setExtracting] = useState(false);
  const [extractError, setExtractError] = useState<unknown>(null);
  const [activeId, setActiveId] = useState<string>("");
  const [active, setActive] = useState<any>(null);
  const [activeLoading, setActiveLoading] = useState(false);

  const sourceIdsKey = docs.map((item: any) => item.id).join(",");
  useEffect(() => { setSelected(docs.slice(0, 1).map((item: any) => item.id)); }, [sourceIdsKey]);

  async function openImport(importId: string) {
    setActiveId(importId);
    setActiveLoading(true);
    setActive(null);
    try {
      setActive(await api.get(`/imports/${importId}`));
    } catch (error) {
      setExtractError(error);
    } finally {
      setActiveLoading(false);
    }
  }

  async function upload() {
    if (!file) {
      setUploadError(new Error("请选择要上传的文件"));
      return;
    }
    setUploading(true);
    setUploadError(null);
    setMessage("");
    const form = new FormData();
    form.append("file", file);
    form.append("purpose", uploadMeta.purpose);
    if (uploadMeta.sku_id) form.append("sku_id", uploadMeta.sku_id);
    if (uploadMeta.view_angle) form.append("view_angle", uploadMeta.view_angle);
    try {
      await api.upload(`/products/${productId}/sources`, form);
      setFile(null);
      setMessage("原始资料已保存，可在下方列表中预览");
      await reload();
    } catch (error) {
      setUploadError(error);
    } finally {
      setUploading(false);
    }
  }

  async function extract() {
    if (!selected.length) {
      setExtractError(new Error("请至少选择一份资料"));
      return;
    }
    setExtracting(true);
    setExtractError(null);
    setMessage("");
    try {
      const result = await api.post(`/products/${productId}/imports/extract`, {
        category_id: detail.product.category_id,
        source_ids: selected,
        manual,
      });
      await reload();
      await openImport(result.id);
      setMessage(manual ? "已创建人工录入任务，请补充字段并填写依据" : "AI 候选已生成，请人工核对来源后确认");
    } catch (error) {
      setExtractError(error);
    } finally {
      setExtracting(false);
    }
  }

  return (
    <>
      <div className="record-links">
        <Badge tone="accent">{detail.latest_version ? '基于当前资料 v' + detail.latest_version.version : "首次整理资料"}</Badge>
        <span>上传原件 → 核对字段 → 确认生效</span>
        <button className="btn btn-small btn-ghost" onClick={() => props.goTab("versions")}>查看版本与影响</button>
      </div>
      <Section title="1. 上传原始资料" subtitle="支持带文字层 PDF、XLSX、DOCX、PNG/JPEG；单文件不超过 10 MB，服务端校验类型与体积">
        <div className="form-grid">
          <Field label="选择文件" required hint="旧版 .doc/.xls 请先另存为 .docx/.xlsx">
            <input type="file" accept=".pdf,.xlsx,.docx,.png,.jpg,.jpeg"
                   onChange={(event) => setFile(event.target.files?.[0] || null)} />
          </Field>
          <Field label="用途">
            <select value={uploadMeta.purpose} onChange={(event) => setUploadMeta({ ...uploadMeta, purpose: event.target.value })}>
              {PURPOSES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
            </select>
          </Field>
          <Field label="关联 SKU">
            <select value={uploadMeta.sku_id} onChange={(event) => setUploadMeta({ ...uploadMeta, sku_id: event.target.value })}>
              <option value="">不关联</option>
              {(detail.skus || []).map((sku: any) => <option key={sku.id} value={sku.id}>{sku.sku_code}</option>)}
            </select>
          </Field>
          <Field label="视角（图片）">
            <select value={uploadMeta.view_angle} onChange={(event) => setUploadMeta({ ...uploadMeta, view_angle: event.target.value })}>
              <option value="">不标注</option>
              {ANGLES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
            </select>
          </Field>
        </div>
        {uploadError !== null && <div className="mt"><ErrorBox error={uploadError} /></div>}
        {message && <div className="notice notice-success mt">{message}</div>}
        <div className="form-actions">
          <button className="btn" disabled={uploading || !file} onClick={upload}>
            {uploading ? "上传中…" : "上传并保存原件"}
          </button>
        </div>
      </Section>

      <Section title={`资料文件（${docs.length}）`} subtitle="每条记录保留文件名、大小、上传时间与预览入口">
        {docs.length === 0 ? (
          <Empty title="还没有文档资料" hint="上传 PDF、Excel 或 Word 后开始提取" />
        ) : (
          <table>
            <thead><tr><th>文件名</th><th>类型</th><th>大小</th><th>用途</th><th>上传时间</th><th></th></tr></thead>
            <tbody>
              {docs.map((doc: any) => (
                <tr key={doc.id}>
                  <td>{doc.name}</td>
                  <td className="muted small">{doc.mime.split("/").pop()}</td>
                  <td className="muted small">{formatSize(doc.size)}</td>
                  <td className="muted small">{PURPOSES.find((item) => item.value === doc.purpose)?.label || doc.purpose}</td>
                  <td className="muted small">{formatTime(doc.created_at)}</td>
                  <td><a href={doc.url} target="_blank" rel="noreferrer">预览原件</a></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Section>

      <Section title="2. 选择资料并提取字段" subtitle="模型只生成候选；服务端会核对引用原文能否定位，无法定位的值直接拒绝">
        {docs.length === 0 ? (
          <Empty title="请先上传资料" hint="支持 PDF 页码、Excel 工作表/行列、Word 段落、图片 OCR 定位" />
        ) : (
          <>
            <div className="pill-list mb">
              {docs.map((doc: any) => (
                <label key={doc.id} className="row gap small" style={{ gap: 6 }}>
                  <input type="checkbox" checked={selected.includes(doc.id)}
                         onChange={(event) => setSelected((current) =>
                           event.target.checked ? [...current, doc.id] : current.filter((id) => id !== doc.id))} />
                  {doc.name}
                </label>
              ))}
            </div>
            <label className="row gap small">
              <input type="checkbox" checked={manual} onChange={(event) => setManual(event.target.checked)} />
              人工录入模式（不调用模型，按缺失字段补充并填写依据）
            </label>
            {!models?.llm?.configured && !manual && (
              <Notice tone="warn">文本模型未配置，AI 抽取会返回配置错误。可勾选人工录入模式继续。</Notice>
            )}
            {extractError !== null && <div className="mt"><ErrorBox error={extractError} /></div>}
            <div className="form-actions">
              <button className="btn" disabled={extracting || selected.length === 0} onClick={extract}>
                {extracting ? "解析与校验中…" : "提取并核对字段"}
              </button>
            </div>
          </>
        )}
      </Section>

      <Section title="导入任务" subtitle="保留每次提取的候选、异常、来源与确认结果">
        {importsList.length === 0 ? (
          <Empty title="暂无导入任务" />
        ) : (
          <table>
            <thead><tr><th>任务</th><th>品类</th><th>异常</th><th>状态</th><th>创建时间</th><th></th></tr></thead>
            <tbody>
              {importsList.map((item: any) => (
                <tr key={item.id}>
                  <td className="mono">{item.id.slice(0, 8)}</td>
                  <td>{item.category}</td>
                  <td>{item.issue_count}</td>
                  <td><Badge tone={statusTone(item.status)}>{statusLabel(item.status)}</Badge></td>
                  <td className="muted small">{formatTime(item.created_at)}</td>
                  <td><button className="btn btn-small btn-ghost" onClick={() => openImport(item.id)}>查看</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Section>

      {activeLoading && <Section title="导入详情"><Loading /></Section>}
      {active && (
        <ImportEditor data={active} productDetail={detail}
                      onPublished={() => props.goTab("versions")} onRefresh={async () => { await reload(); await openImport(activeId); }} />
      )}
    </>
  );
}

function ImportEditor({ data, productDetail, onRefresh, onPublished }: { data: any; productDetail: any; onRefresh: () => Promise<void>; onPublished: () => void }) {
  const attrs = data.schema?.attributes || [];
  const editable = data.status === "reviewing";
  const base = editable ? productDetail.latest_version : null;
  const [fields, setFields] = useState<Record<string, string>>({});
  const [basis, setBasis] = useState<Record<string, string>>({});
  const [resolutions, setResolutions] = useState<Record<string, string>>({});
  const [sku, setSku] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [message, setMessage] = useState("");

  useEffect(() => {
    const next: Record<string, string> = {};
    for (const attr of attrs) {
      const candidates = data.candidates?.[attr.key] || [];
      const first = candidates.find((item: any) => item.valid);
      next[attr.key] = first?.value ?? base?.fields?.[attr.key] ?? "";
    }
    setFields(next);
    setSku(base?.sku || "");
    setBasis({});
    setResolutions({});
    setError(null);
    setMessage("");
  }, [data.id, data.status, base?.id]);

  async function confirm() {
    setBusy("confirm");
    setError(null);
    setMessage("");
    try {
      const manualBasis: Record<string, string> = {};
      for (const [key, value] of Object.entries(basis)) {
        if (value.trim()) manualBasis[key] = value.trim();
      }
      const result = await api.post(`/imports/${data.id}/confirm`, {
        fields,
        base_version_id: base?.id,
        sku,
        note,
        manual_basis: manualBasis,
        resolutions: Object.entries(resolutions).map(([issue_id, resolution]) => ({ issue_id, resolution })),
      });
      setMessage(`已生成不可变版本 v${result.version}，受影响成品 ${result.affected_outputs} 个`);
      await onRefresh();
      onPublished();
    } catch (err) {
      setError(err);
    } finally {
      setBusy("");
    }
  }

  async function reject() {
    if (!note.trim()) {
      setError(new Error("驳回时请填写原因"));
      return;
    }
    setBusy("reject");
    setError(null);
    try {
      await api.post(`/imports/${data.id}/reject`, { note });
      setMessage("已驳回该导入任务");
      await onRefresh();
    } catch (err) {
      setError(err);
    } finally {
      setBusy("");
    }
  }

  const labels = fieldLabels(productDetail);
  const changed = base ? attrs.filter((attr: any) =>
    (fields[attr.key] || "") !== (base.fields[attr.key] || "")) : [];

  return (
    <Section title={`3. 核对字段 · ${data.id.slice(0, 8)}`}
             subtitle={`${data.category_name} · ${statusLabel(data.status)} · 创建于 ${formatTime(data.created_at)}`}
             actions={<Badge tone={statusTone(data.status)}>{statusLabel(data.status)}</Badge>}>
      {data.warnings?.length > 0 && (
        <div className="stack mb">
          {data.warnings.map((warning: string) => <Notice key={warning} tone="warn">{warning}</Notice>)}
        </div>
      )}
      {data.version_id && (
        <Notice tone="success">已生成版本 v{data.version}（ID {data.version_id}），可在概览与版本页查看来源。</Notice>
      )}
      {error !== null && <div className="mb"><ErrorBox error={error} /></div>}
      {message && <div className="notice notice-success mb">{message}</div>}

      <div className="stack">
        {attrs.map((attr: any) => {
          const candidates = data.candidates?.[attr.key] || [];
          const issue = (data.issues || []).find((item: any) => item.field === attr.key);
          return (
            <div key={attr.key} className="issue" style={{ borderLeftColor: "#e7ded4", background: "#fff" }}>
              <div className="row gap wrap mb">
                <strong>{attr.label}</strong>
                {attr.required && <Badge tone="accent">必填</Badge>}
                <span className="muted small">{attr.type}{attr.unit ? ` · ${attr.unit}` : ""}</span>
                {issue && <Badge tone={issue.type === "conflict" ? "danger" : issue.type === "missing" ? "warn" : "default"}>{issue.type === "conflict" ? "来源冲突" : issue.type === "missing" ? "待补充" : issue.type === "duplicate" ? "多来源一致" : "需核对"}</Badge>}
              </div>
              <div className="form-grid">
                <Field label="采用值" required={attr.required} hint={base ? "当前生效值：" + (base.fields[attr.key] || "未填写") : undefined}>
                  <input value={fields[attr.key] || ""} disabled={!editable}
                         placeholder={attr.required ? "必填，待补充" : "可选"}
                         onChange={(event) => setFields({ ...fields, [attr.key]: event.target.value })} />
                </Field>
                <Field label="人工补充/修改依据" hint="与提取候选不一致或人工新增时必须填写">
                  <input value={basis[attr.key] || ""} disabled={!editable}
                         placeholder="例如：供应商邮件、实物测量"
                         onChange={(event) => setBasis({ ...basis, [attr.key]: event.target.value })} />
                </Field>
              </div>
              {issue && (
                <div className="small mt">
                  <div className={`issue ${issue.type}`} style={{ marginBottom: 6 }}>
                    <div className="strong">{issue.message}</div>
                    {issue.type === "duplicate" && editable && (
                      <select value={resolutions[issue.id] || ""}
                              onChange={(event) => setResolutions({ ...resolutions, [issue.id]: event.target.value })}>
                        <option value="">选择处理方式：合并 / 保留</option>
                        <option value="merge">合并为同一值</option>
                        <option value="keep">保留为多来源</option>
                      </select>
                    )}
                    {issue.type === "conflict" && editable && (
                      <select value={resolutions[issue.id] || ""}
                              onChange={(event) => setResolutions({ ...resolutions, [issue.id]: event.target.value })}>
                        <option value="">请选择采用来源并标记已处理</option>
                        <option value="resolved">已人工核对并采用当前值</option>
                        <option value="keep">保留冲突待复核</option>
                      </select>
                    )}
                  </div>
                </div>
              )}
              {candidates.length > 0 && (
                <div className="grid two mt">
                  {candidates.map((candidate: any, index: number) => (
                    <button type="button" key={`${candidate.source_id}-${index}`}
                            className={`candidate ${fields[attr.key] === candidate.value ? "active" : ""}`}
                            disabled={!editable || !candidate.valid}
                            onClick={() => setFields({ ...fields, [attr.key]: candidate.value })}>
                      <div className="row gap wrap">
                        <strong>{candidate.value || candidate.raw_value}</strong>
                        <Badge tone={candidate.valid ? "success" : "danger"}>{candidate.valid ? "已校验" : candidate.error}</Badge>
                      </div>
                      <div className="quote">“{candidate.quote}”</div>
                      <div className="muted small">{candidate.source_name} · {locatorText(candidate.locator)}</div>
                    </button>
                  ))}
                </div>
              )}
              {candidates.length === 0 && <div className="muted small mt">{base?.fields?.[attr.key] ? "可沿用已确认值和来源。手工修改时请补充依据。" : "没有可用候选，请核实后补充。"}</div>}
            </div>
          );
        })}
      </div>

      <div className="form-grid mt">
        <Field label="关联 SKU"><select value={sku} disabled={!editable} onChange={(event) => setSku(event.target.value)}>
          <option value="">不关联</option>
          {base?.sku && !productDetail.skus.some((item: any) => item.sku_code === base.sku) && <option value={base.sku}>{base.sku}（沿用）</option>}
          {(productDetail.skus || []).map((item: any) => <option key={item.id} value={item.sku_code}>{item.sku_code}</option>)}
        </select></Field>
        <Field label="确认备注"><input value={note} disabled={!editable} onChange={(event) => setNote(event.target.value)} placeholder="人工复核说明" /></Field>
      </div>
      <div className="form-actions">
        {base && <span className="muted small">相对 v{base.version}：{changed.length ? changed.map((attr: any) => attr.label).join("、") + "待更新" : "字段值无变更"}</span>}
        <button className="btn" disabled={!editable || !!busy} onClick={confirm}>
          {busy === "confirm" ? "确认中…" : "确认并设为生效版本"}
        </button>
        <button className="btn btn-ghost" disabled={!editable || !!busy} onClick={reject}>
          {busy === "reject" ? "提交中…" : "驳回"}
        </button>
      </div>
    </Section>
  );
}

/* ---------------- 素材 ---------------- */

export function AssetsTab({ detail, productId, reload }: TabProps) {
  const images = (detail.sources || []).filter((source: any) => source.kind === "image");
  const [editingId, setEditingId] = useState("");
  const usable = ANGLES.flatMap((angle) => images.filter((source: any) =>
    source.view_angle === angle.value && source.review_status === "confirmed"));
  const other = images.filter((source: any) => !usable.includes(source));
  const editing = images.find((source: any) => source.id === editingId);

  function gallery(items: any[]) {
    return <div className="reference-grid">{items.map((source) => (
      <button key={source.id} className="reference-tile" onClick={() => setEditingId(source.id)}>
        <img src={source.url} alt={source.name} loading="lazy" />
        <strong>{angleLabel(source.view_angle)} · {statusLabel(source.review_status)}</strong>
        <span className="ellipsis">{source.name}</span>
      </button>
    ))}</div>;
  }

  return (
    <>
      <Section title={"可调用参考图（" + usable.length + "）"} subtitle="已确认且标过视角。点击图片查看原图、修改标注或停用旧素材。">
        {usable.length ? gallery(usable) : <Empty title="暂无可调用参考图" hint="补充图片后标注视角并确认。" />}
      </Section>
      {other.length > 0 && <Section title={"待整理与已停用（" + other.length + "）"}>{gallery(other)}</Section>}
      {editing && <Modal title="编辑参考素材" onClose={() => setEditingId("")}>
        <AssetCard key={editing.id} source={editing} productId={productId} skus={detail.skus || []} reload={reload} onDeleted={() => setEditingId("")} />
      </Modal>}
      <ImageUpload productId={productId} skus={detail.skus || []} reload={reload} />
    </>
  );
}

function AssetCard({ source, productId, skus, reload, onDeleted }: { source: any; productId: string; skus: any[]; reload: () => Promise<void>; onDeleted?: () => void }) {
  const [angle, setAngle] = useState(source.view_angle || "");
  const [purpose, setPurpose] = useState(source.purpose || "reference");
  const [reviewStatus, setReviewStatus] = useState(source.review_status || "pending");
  const [skuId, setSkuId] = useState(source.sku_id || "");
  const [assetType, setAssetType] = useState(source.asset_type || "raw");
  const [tags, setTags] = useState<string>((source.tags || []).join(", "));
  const [busy, setBusy] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [message, setMessage] = useState("");

  async function save() {
    setBusy("save");
    setError(null);
    setMessage("");
    try {
      await api.put(`/products/${productId}/sources/${source.id}`, {
        view_angle: angle, purpose, review_status: reviewStatus, sku_id: skuId || "",
        asset_type: assetType, tags: tags.split(",").map((tag) => tag.trim()).filter(Boolean),
      });
      setMessage("标注已保存");
      await reload();
    } catch (err) {
      setError(err);
    } finally {
      setBusy("");
    }
  }

  async function suggest() {
    setBusy("suggest");
    setError(null);
    try {
      const result = await api.post(`/products/${productId}/sources/${source.id}/suggest-angle`);
      if (result.angle) {
        setAngle(result.angle);
        setMessage(result.note);
      } else {
        setMessage(result.note);
      }
    } catch (err) {
      setError(err);
    } finally {
      setBusy("");
    }
  }

  async function remove() {
    if (!window.confirm(`确认删除素材「${source.name}」？此操作不可撤销。`)) return;
    setBusy("delete");
    setError(null);
    setMessage("");
    try {
      await api.delete(`/products/${productId}/sources/${source.id}`);
      await reload();
      onDeleted?.();
    } catch (err) {
      setError(err);
    } finally {
      setBusy("");
    }
  }

  return (
    <div className="asset-card">
      <img className="thumb" src={source.url} alt={source.name} />
      <div className="strong ellipsis" title={source.name}>{source.name}</div>
      <div className="row gap wrap">
        <Badge tone={angle ? "success" : "warn"}>{angleLabel(angle)}</Badge>
        <span className="muted small">{formatSize(source.size)}</span>
        <span className="muted small">{statusLabel(reviewStatus)}</span>
      </div>
      <Field label="视角">
        <select value={angle} onChange={(event) => setAngle(event.target.value)}>
          <option value="">未标注</option>
          {ANGLES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
        </select>
      </Field>
      <div className="form-grid" style={{ gridTemplateColumns: "1fr 1fr" }}>
        <Field label="用途">
          <select value={purpose} onChange={(event) => setPurpose(event.target.value)}>
            {PURPOSES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
          </select>
        </Field>
        <Field label="审核">
          <select value={reviewStatus} onChange={(event) => setReviewStatus(event.target.value)}>
            <option value="pending">待审核</option><option value="confirmed">已确认</option><option value="rejected">已废弃</option>
          </select>
        </Field>
      </div>
      <div className="form-grid" style={{ gridTemplateColumns: "1fr 1fr" }}>
        <Field label="素材类型">
          <select value={assetType} onChange={(event) => setAssetType(event.target.value)}>
            {ASSET_TYPES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
          </select>
        </Field>
        <Field label="标签" hint="逗号分隔">
          <input value={tags} onChange={(event) => setTags(event.target.value)} />
        </Field>
      </div>
      <Field label="关联 SKU">
        <select value={skuId} onChange={(event) => setSkuId(event.target.value)}>
          <option value="">不关联</option>
          {skus.map((sku) => <option key={sku.id} value={sku.id}>{sku.sku_code}</option>)}
        </select>
      </Field>
      {error !== null && <ErrorBox error={error} />}
      {message && <div className="notice notice-success small">{message}</div>}
      <div className="toolbar">
        <button className="btn btn-small" disabled={!!busy} onClick={save}>{busy === "save" ? "保存中…" : "保存标注"}</button>
        <button className="btn btn-small btn-ghost" disabled={!!busy} onClick={suggest}>{busy === "suggest" ? "建议中…" : "AI 建议视角"}</button>
        <a className="btn btn-small btn-ghost" href={source.url} target="_blank" rel="noreferrer">预览原图</a>
        <button className="btn btn-small btn-soft" disabled={!!busy} onClick={remove}>{busy === "delete" ? "删除中…" : "删除"}</button>
      </div>
    </div>
  );
}

function ImageUpload({ productId, skus, reload }: { productId: string; skus: any[]; reload: () => Promise<void> }) {
  const [file, setFile] = useState<File | null>(null);
  const [angle, setAngle] = useState("");
  const [skuId, setSkuId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [message, setMessage] = useState("");

  async function upload() {
    if (!file) {
      setError(new Error("请选择图片文件"));
      return;
    }
    setBusy(true);
    setError(null);
    setMessage("");
    const form = new FormData();
    form.append("file", file);
    form.append("purpose", "reference");
    if (angle) form.append("view_angle", angle);
    if (skuId) form.append("sku_id", skuId);
    try {
      await api.upload(`/products/${productId}/sources`, form);
      setFile(null);
      setMessage("图片已上传");
      await reload();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Section title="补充参考图" subtitle="同一 SKU 可上传多张；文件名含“正面/侧面”等关键词时 AI 建议会更准确">
      <div className="form-grid">
        <Field label="图片文件" required><input type="file" accept=".png,.jpg,.jpeg" onChange={(event) => setFile(event.target.files?.[0] || null)} /></Field>
        <Field label="视角"><select value={angle} onChange={(event) => setAngle(event.target.value)}>
          <option value="">暂不标注</option>
          {ANGLES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
        </select></Field>
        <Field label="关联 SKU"><select value={skuId} onChange={(event) => setSkuId(event.target.value)}>
          <option value="">不关联</option>
          {skus.map((sku) => <option key={sku.id} value={sku.id}>{sku.sku_code}</option>)}
        </select></Field>
      </div>
      {error !== null && <div className="mt"><ErrorBox error={error} /></div>}
      {message && <div className="notice notice-success mt">{message}</div>}
      <div className="form-actions"><button className="btn" disabled={busy || !file} onClick={upload}>{busy ? "上传中…" : "上传参考图"}</button></div>
    </Section>
  );
}

/* ---------------- 策划 ---------------- */

export function PlansTab(props: TabProps) {
  const { productId, detail, models, plans, outputs, reload, goTab } = props;
  const images = (detail.sources || []).filter((source: any) => source.kind === "image" && source.view_angle && source.review_status === "confirmed");
  const [scene, setScene] = useState("抖音春节年货节");
  const [channel, setChannel] = useState("抖音");
  const [audience, setAudience] = useState("约30岁女性");
  const [contentType, setContentType] = useState("商品主图+短视频");
  const [selected, setSelected] = useState<string[]>([]);
  const [manual, setManual] = useState(!models?.llm?.configured);
  const [manualJson, setManualJson] = useState("");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [message, setMessage] = useState("");

  const imageKey = images.map((item: any) => item.id).join(",");
  useEffect(() => {
    setSelected(images.map((item: any) => item.id));
    setManualJson(planTemplate(detail));
  }, [imageKey, detail.latest_version?.id]);

  async function create() {
    setBusy("create");
    setError(null);
    setMessage("");
    try {
      let content: any = undefined;
      if (manual) {
        try {
          content = JSON.parse(manualJson);
        } catch {
          throw new Error("手工策划 JSON 格式不正确，请检查括号与引号");
        }
      }
      const plan = await api.post(`/products/${productId}/plans`, {
        scene, channel, audience, content_type: contentType,
        source_ids: selected, manual, content,
      });
      setMessage(`策划已创建（${plan.blocked.length ? `发现 ${plan.blocked.length} 处待处理宣传词` : "待人工确认"}）`);
      await reload();
    } catch (err) {
      setError(err);
    } finally {
      setBusy("");
    }
  }

  if (!detail.latest_version) {
    return <Section title="内容策划"><Empty title="请先确认商品版本" hint="在“资料与导入”完成人工确认后，才能基于已确认事实策划" /></Section>;
  }

  return (
    <>
      <Section title="新建内容策划" subtitle="读取已确认商品版本与已标注视角的参考图；模型输出卖点、文案、主视觉、图片提示词与分镜">
        {images.length === 0 && <Notice tone="warn">还没有已标注视角的参考图，请先到“素材”完成视角标注。</Notice>}
        <div className="form-grid">
          <Field label="营销场景" required hint="例如：抖音春节年货节"><input value={scene} onChange={(event) => setScene(event.target.value)} /></Field>
          <Field label="渠道"><input value={channel} onChange={(event) => setChannel(event.target.value)} /></Field>
          <Field label="目标人群"><input value={audience} onChange={(event) => setAudience(event.target.value)} /></Field>
          <Field label="目标内容"><input value={contentType} onChange={(event) => setContentType(event.target.value)} /></Field>
        </div>
        <div className="record-links">
          <Badge tone="success">商品事实 v{detail.latest_version.version}</Badge>
          <button className="btn btn-small btn-ghost" onClick={() => goTab("overview")}>查看商品事实</button>
          <span>已选 {selected.length} 张参考图</span>
        </div>
        <div className="reference-grid">
          {images.map((image: any) => (
            <label key={image.id} className="reference-tile">
              <img src={image.url} alt={image.name} loading="lazy" />
              <span><input type="checkbox" checked={selected.includes(image.id)}
                onChange={(event) => setSelected((current) =>
                  event.target.checked ? [...current, image.id] : current.filter((id) => id !== image.id))} />
                {angleLabel(image.view_angle)}
              </span>
            </label>
          ))}
        </div>
        <label className="row gap small mt">
          <input type="checkbox" checked={manual} onChange={(event) => setManual(event.target.checked)} />
          手工策划（不调用模型，人工撰写结构化内容，仍会做事实与宣传词校验）
        </label>
        {manual && (
          <div className="mt">
            <Field label="策划内容 JSON" required hint="selling_points 必须绑定字段键并提供字段值中的 evidence；分镜总时长 10-15 秒">
              <textarea className="code" value={manualJson} onChange={(event) => setManualJson(event.target.value)} />
            </Field>
          </div>
        )}
        {error !== null && <div className="mt"><ErrorBox error={error} /></div>}
        {message && <div className="notice notice-success mt">{message}</div>}
        <div className="form-actions">
          <button className="btn" disabled={!!busy || !scene.trim() || selected.length === 0} onClick={create}>
            {busy === "create" ? "生成中…" : manual ? "保存手工策划" : "AI 生成策划"}
          </button>
        </div>
      </Section>

      {plans.length === 0 ? (
        <Section title="策划列表"><Empty title="还没有策划" hint="创建后可编辑、刷新读回、确认，并进入生产" /></Section>
      ) : (
        plans.map((plan: any) => (
          <PlanCard key={plan.id} plan={plan} detail={detail} outputs={outputs}
                    reload={reload} goTab={goTab} />
        ))
      )}
    </>
  );
}

function PlanCard({ plan, detail, outputs, reload, goTab }: {
  plan: any; detail: any; outputs: any[]; reload: () => Promise<void>; goTab: (tab: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [json, setJson] = useState(JSON.stringify(plan.content, null, 2));
  const [busy, setBusy] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [message, setMessage] = useState("");
  const [reuseScene, setReuseScene] = useState("日常商品展示");
  const [reuseOutputs, setReuseOutputs] = useState<string[]>([]);
  const labels = fieldLabels(detail);
  const approvedImages = outputs.filter((output: any) =>
    output.kind === "image" && output.status === "approved" && !output.needs_review);

  async function save() {
    setBusy("save");
    setError(null);
    setMessage("");
    try {
      const content = JSON.parse(json);
      await api.put(`/plans/${plan.id}`, { content, note: "人工编辑策划" });
      setEditing(false);
      setMessage("策划已保存，需要重新确认");
      await reload();
    } catch (err) {
      setError(err);
    } finally {
      setBusy("");
    }
  }

  async function confirmPlan() {
    setBusy("confirm");
    setError(null);
    setMessage("");
    try {
      await api.post(`/plans/${plan.id}/confirm`);
      setMessage("策划已确认，可进入生产");
      await reload();
    } catch (err) {
      setError(err);
    } finally {
      setBusy("");
    }
  }

  async function reuse() {
    setBusy("reuse");
    setError(null);
    setMessage("");
    try {
      const result = await api.post(`/plans/${plan.id}/reuse`, {
        scene: reuseScene, content_type: "日常商品展示", output_ids: reuseOutputs,
        manual: true, content: plan.content,
      });
      setMessage(`已创建复用策划 ${result.id.slice(0, 8)}（记录原策划 ${plan.id.slice(0, 8)}）`);
      await reload();
    } catch (err) {
      setError(err);
    } finally {
      setBusy("");
    }
  }

  return (
    <Section title={plan.content.theme || "未命名策划"}
             subtitle={`${plan.scene} · ${plan.channel || "—"} · 商品版本 v${plan.version ?? "?"} · ${formatTime(plan.created_at)}`}
             actions={<><Badge tone={statusTone(plan.status)}>{statusLabel(plan.status)}</Badge>
               {!plan.is_current_version && <Badge tone="danger">版本已过期</Badge>}</>}>
      {plan.blocked?.length > 0 && (
        <div className="stack mb">
          {plan.blocked.map((item: any, index: number) => (
            <div className="issue conflict" key={`${item.term}-${index}`}>
              <div className="strong">{item.term} · {item.message}</div>
              <div className="muted small">位置：{item.where}</div>
            </div>
          ))}
        </div>
      )}
      <div className="grid two">
        <div>
          <div className="kv">
            <dt>投放文案</dt><dd>{plan.content.copy || "—"}</dd>
            <dt>主视觉</dt><dd>{plan.content.visual || "—"}</dd>
            <dt>图片提示词</dt><dd>{plan.content.image_prompt}</dd>
            <dt>话题</dt><dd>{(plan.content.hashtags || []).join(" ") || "—"}</dd>
          </div>
        </div>
        <div>
          <div className="strong small mb">事实卖点与来源</div>
          {(plan.content.selling_points || []).map((point: any, index: number) => (
            <div className="list-row" key={index}>
              <div className="grow">
                <div>{point.text}</div>
                <div className="muted small">{labels[point.field] || point.field} · 依据“{point.evidence}”</div>
              </div>
            </div>
          ))}
          <div className="strong small mt mb">分镜</div>
          {(plan.content.shots || []).map((shot: any, index: number) => (
            <div className="plan-shot" key={index}>
              <Badge tone="accent">{index + 1}</Badge>
              <div className="grow">{shot.caption}</div>
              <span className="muted small">{angleLabel(shot.angle)} · {shot.duration} 秒</span>
            </div>
          ))}
        </div>
      </div>
      <div className="mt muted small">
        参考素材：{(plan.materials || []).map((item: any) => `${item.name}（${angleLabel(item.view_angle)}）`).join("、") || "—"}
        {plan.parent_plan_id && <> · 复用自策划 {plan.parent_plan_id.slice(0, 8)}</>}
      </div>
      {error !== null && <div className="mt"><ErrorBox error={error} /></div>}
      {message && <div className="notice notice-success mt">{message}</div>}

      {editing && (
        <div className="mt">
          <Field label="编辑策划 JSON" hint="保存后状态回到草稿，必须重新确认">
            <textarea className="code" value={json} onChange={(event) => setJson(event.target.value)} />
          </Field>
        </div>
      )}

      <div className="form-actions">
        {plan.status === "confirmed" ? (
          <button className="btn btn-small" onClick={() => goTab("production")}>进入生产</button>
        ) : (
          <button className="btn btn-small" disabled={!!busy || plan.blocked.length > 0} onClick={confirmPlan}>
            {busy === "confirm" ? "确认中…" : "人工确认策划"}
          </button>
        )}
        <button className="btn btn-small btn-ghost" onClick={() => { setEditing(!editing); setJson(JSON.stringify(plan.content, null, 2)); }}>
          {editing ? "取消编辑" : "编辑策划"}
        </button>
        {editing && <button className="btn btn-small" disabled={!!busy} onClick={save}>{busy === "save" ? "保存中…" : "保存并回到草稿"}</button>}
      </div>

      {plan.status === "confirmed" && (
        <div className="notice notice-info mt">
          <div className="strong">复用历史素材创建新场景</div>
          <div className="form-grid mt">
            <Field label="新场景"><input value={reuseScene} onChange={(event) => setReuseScene(event.target.value)} /></Field>
          </div>
          {approvedImages.length > 0 && (
            <div className="pill-list mt">
              {approvedImages.map((output: any) => (
                <label key={output.id} className="row gap small" style={{ gap: 6 }}>
                  <input type="checkbox" checked={reuseOutputs.includes(output.id)}
                         onChange={(event) => setReuseOutputs((current) =>
                           event.target.checked ? [...current, output.id] : current.filter((id) => id !== output.id))} />
                  复用已审核商品图 {output.id.slice(0, 6)}
                </label>
              ))}
            </div>
          )}
          <div className="form-actions">
            <button className="btn btn-small btn-soft" disabled={!!busy || !reuseScene.trim()} onClick={reuse}>
              {busy === "reuse" ? "创建中…" : "创建复用策划"}
            </button>
          </div>
        </div>
      )}
    </Section>
  );
}

/* ---------------- 生产 ---------------- */

export function ProductionTab(props: TabProps) {
  const { detail, plans, outputs, runs, reload, productionKind } = props;
  const confirmed = plans.filter((plan: any) => plan.status === "confirmed");
  const [selectedId, setSelectedId] = useState("");
  useEffect(() => {
    if (!confirmed.find((plan: any) => plan.id === selectedId)) setSelectedId((confirmed.find((plan: any) => plan.is_current_version) || confirmed[0])?.id || "");
  }, [plans.map((plan: any) => `${plan.id}:${plan.status}`).join(",")]);
  const plan = confirmed.find((item: any) => item.id === selectedId);
  const [prompt, setPrompt] = useState("");
  const [ratio, setRatio] = useState("3:4");
  const [count, setCount] = useState(1);
  const [materials, setMaterials] = useState<string[]>([]);
  const [imageReferences, setImageReferences] = useState<string[]>([]);
  const [videoProvider, setVideoProvider] = useState("ffmpeg");
  const [busy, setBusy] = useState("");
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState<unknown>(null);
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (!plan) return;
    setPrompt(plan.content?.image_prompt || "");
    setMaterials((plan.source_ids || []).map((id: string) => `source:${id}`));
    setImageReferences((plan.source_ids || []).filter((id: string) => usableReferences.some((source: any) => source.id === id)).slice(0, 4));
    setError(null);
    setMessage("");
  }, [selectedId]);

  useEffect(() => {
    if (!busy) {
      setElapsed(0);
      return;
    }
    const timer = window.setInterval(() => setElapsed((value) => value + 1), 1000);
    return () => window.clearInterval(timer);
  }, [busy]);

  const planOutputs = outputs.filter((output: any) => output.plan_id === selectedId && (!productionKind || output.kind === productionKind));
  const approvedImages = outputs.filter((output: any) =>
    output.kind === "image" && output.status === "approved" && !output.needs_review);
  const usableReferences = detail.sources.filter((source: any) =>
    source.kind === "image" && source.view_angle && source.review_status === "confirmed");
  const selectedReferences = imageReferences.filter((id) => usableReferences.some((source: any) => source.id === id));
  const allMaterials = [
    ...usableReferences.map((item: any) => ({
      value: `source:${item.id}`, url: item.url, label: `${item.name}（${angleLabel(item.view_angle)}）`,
    })),
    ...approvedImages.map((output: any) => ({
      value: `output:${output.id}`, url: output.url, label: `已审核商品图 ${output.id.slice(0, 6)}`,
    })),
  ];
  const selectedMaterials = materials.filter((id) => allMaterials.some((item) => item.value === id));

  async function generate(kind: "image" | "video") {
    if (!plan) return;
    setBusy(kind);
    setError(null);
    setMessage("");
    try {
      const body = kind === "image" ? { prompt, ratio, count, reference_ids: selectedReferences } : { materials: selectedMaterials, provider: videoProvider };
      const result = await api.post(`/plans/${plan.id}/outputs/${kind}`, body);
      setMessage(kind === "image"
        ? `已生成 ${result.outputs.length} 张候选（尝试 ${result.attempts} 次），进入待审核队列`
        : `视频已生成，进入待审核队列`);
      await reload();
    } catch (err) {
      setError(err);
    } finally {
      setBusy("");
    }
  }

  if (!confirmed.length) {
    return <Section title="内容生产"><Empty title="没有已确认策划" hint="先在“策划”完成人工确认，才能调用生图或合成视频" /></Section>;
  }

  return (
    <>
      <Section title="生产任务" subtitle="真实调用生图服务；视频使用 FFmpeg 合成并通过 ffprobe 校验时长与画幅">
        <div className="filters">
          <Field label="选择已确认策划">
            <select value={selectedId} onChange={(event) => setSelectedId(event.target.value)}>
              {confirmed.map((item: any) => (
                <option key={item.id} value={item.id}>{item.scene}（v{item.version}）</option>
              ))}
            </select>
          </Field>
        </div>
        {plan && (
          <>
            <div className="muted small mb">商品版本 v{plan.version} · {plan.is_current_version ? "当前版本" : "非当前版本，不能生产"} · 分镜 {(plan.content.shots || []).length} 个</div>
            {!plan.is_current_version && <div className="record-links">
              <button className="btn btn-small btn-ghost" onClick={() => props.goTab("versions")}>查看资料变更</button>
              <button className="btn btn-small" onClick={() => props.goTab("plans")}>基于当前版本重新策划</button>
            </div>}
            <div className={productionKind ? "stack" : "grid two"}>
              {productionKind !== "video" && <div>
                <div className="strong mb">生成商品图</div>
                <p className="muted small">默认沿用策划中可用的参考图。可更换，最多 4 张，已选 {selectedReferences.length} 张。</p>
                <div className="reference-grid">
                  {usableReferences.map((source: any) => (
                    <label key={source.id} className="reference-tile">
                      <img src={source.url} alt={source.name} loading="lazy" />
                      <span><input type="checkbox" checked={selectedReferences.includes(source.id)}
                        disabled={!!busy || (!selectedReferences.includes(source.id) && selectedReferences.length >= 4)}
                        onChange={(event) => setImageReferences(event.target.checked
                          ? [...selectedReferences, source.id]
                          : selectedReferences.filter((id) => id !== source.id))} />
                        {angleLabel(source.view_angle)}
                      </span>
                    </label>
                  ))}
                </div>
                <Field label="提示词" required><textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} /></Field>
                <div className="form-grid mt">
                  <Field label="比例"><select value={ratio} onChange={(event) => setRatio(event.target.value)}>
                    <option value="3:4">3:4 竖版</option><option value="1:1">1:1 方图</option>
                    <option value="4:3">4:3 横版</option><option value="9:16">9:16 竖屏</option>
                  </select></Field>
                  <Field label="候选数量"><input type="number" min={1} max={4} value={count}
                                                 onChange={(event) => setCount(Number(event.target.value))} /></Field>
                </div>
                <div className="form-actions">
                  <button className="btn" disabled={!!busy || !plan.is_current_version || !prompt.trim() || !selectedReferences.length}
                          onClick={() => generate("image")}>
                    {busy === "image" ? `生成中… ${elapsed}s` : "生成商品图"}
                  </button>
                </div>
              </div>}
              {productionKind !== "image" && <div>
                <div className="strong mb">合成竖版短视频</div>
                <Field label="生成方式">
                  <select value={videoProvider} onChange={(event) => setVideoProvider(event.target.value)}>
                    <option value="ffmpeg">FFmpeg 合成（约 12 秒 · 720×1280，免费本地合成）</option>
                    <option value="seedance">Seedance AI 视频（图生视频，需已配置快跑视频模型）</option>
                  </select>
                </Field>
                <div className="muted small mb">
                  {videoProvider === "seedance"
                    ? "使用已审核商品图作为首帧，AI 生成动态视频；输出 9:16、720p 竖版。"
                    : "使用已审核商品图或原始参考图作为镜头素材；成品约 12 秒、720×1280。"}
                </div>
                <div className="reference-grid">
                  {allMaterials.length === 0 && <div className="muted small">没有可用镜头素材</div>}
                  {allMaterials.map((item) => (
                    <label key={item.value} className="reference-tile">
                      {item.url && <img src={item.url} alt={item.label} loading="lazy" />}
                      <span><input type="checkbox" checked={materials.includes(item.value)}
                             onChange={(event) => setMaterials((current) =>
                               event.target.checked ? [...current, item.value] : current.filter((value) => value !== item.value))} />
                      {item.label}</span>
                    </label>
                  ))}
                </div>
                <div className="form-actions">
                  <button className="btn" disabled={!!busy || !plan.is_current_version || selectedMaterials.length === 0}
                          onClick={() => generate("video")}>
                    {busy === "video" ? `生成中… ${elapsed}s` : (videoProvider === "seedance" ? "生成 AI 视频" : "合成 12 秒视频")}
                  </button>
                </div>
              </div>}
            </div>
            {error !== null && <div className="mt"><ErrorBox error={error} /></div>}
            {message && <div className="notice notice-success mt">{message}</div>}
          </>
        )}
      </Section>

      <Section title="本策划成品" subtitle="不合格结果保留在审核队列；通过后才进入正式交付">
        {planOutputs.length === 0 ? <Empty title="该策划还没有成品" /> : (
          <div className="grid two">
            {planOutputs.map((output: any) => <OutputCard key={output.id} output={output} onChanged={reload} />)}
          </div>
        )}
      </Section>

      <details className="card"><summary>执行记录</summary>
        {runs.length === 0 ? <Empty title="暂无执行记录" /> : (
          <div className="stack">
            {runs.filter((run: any) => !productionKind || run.workflow_type === `${productionKind}_generation`).slice(0, 6).map((run: any) => <RunSteps key={run.id} run={run} />)}
          </div>
        )}
      </details>
    </>
  );
}

/* ---------------- 审核 ---------------- */

export function QualityTab({ detail, outputs, reload }: TabProps) {
  const [kind, setKind] = useState("");
  const [status, setStatus] = useState("");
  const filtered = outputs.filter((output: any) =>
    (!kind || output.kind === kind) && (!status || output.status === status));
  const stale = outputs.filter((output: any) => output.needs_review).length;
  const sourceMap = new Map((detail.sources || []).map((source: any) => [source.id, source]));

  return (
    <>
      <Section title="内容成品" subtitle="预览成果、查看使用的商品版本与参考图，并人工审核交付">
        <div className="filters">
          <Field label="类型"><select value={kind} onChange={(event) => setKind(event.target.value)}>
            <option value="">全部</option><option value="image">商品图</option><option value="video">短视频</option>
          </select></Field>
          <Field label="状态"><select value={status} onChange={(event) => setStatus(event.target.value)}>
            <option value="">全部</option><option value="pending">待审核</option>
            <option value="approved">已通过</option><option value="rejected">已驳回</option>
          </select></Field>
        </div>
        {stale > 0 && <Notice tone="warn">有 {stale} 个成品因商品版本更新被暂停交付，需重新生成并复审。</Notice>}
      </Section>

      {filtered.length === 0 ? <Section title="成品"><Empty title="没有匹配的成品" /></Section> : (
        <div className="stack">
          {filtered.map((output: any) => (
            <Section key={output.id} title={`${output.kind === "video" ? "短视频" : "商品图"} · ${output.id.slice(0, 8)}`}
                     subtitle={`${output.plan?.scene} · 版本 v${output.plan?.version} · ${formatTime(output.created_at)}`}>
              <div className="row gap wrap mb">
                {output.sources?.slice(0, 4).map((item: any) => {
                  const source: any = sourceMap.get(item.id);
                  return source ? (
                    <div key={item.id} style={{ width: 84 }}>
                      <img className="thumb square" src={source.url} alt={source.name} />
                      <div className="muted small ellipsis" title={source.name}>{angleLabel(source.view_angle)}</div>
                    </div>
                  ) : null;
                })}
                <div className="muted small">参考图（左侧）与成品对照审核包型、颜色、材质、底托、肩带、五金与文案。</div>
              </div>
              <OutputCard output={output} onChanged={reload} />
            </Section>
          ))}
        </div>
      )}
    </>
  );
}
