import { useEffect, useState, type FormEvent } from "react";

type Candidate = { source_id: string; name: string; page: number; quote: string; value: string };
type Import = { id: string; category: string; candidates: Record<string, Candidate[]> };
type Version = { id: number; category: string; sku: string; fields: Record<string, string> };
type Plan = { id: string; version_id: number; scene: string; source_ids: string[];
  script: { image_prompt: string; shots: string[] } };
type Output = { id: string; plan_id: string; kind: string; status: string; note: string; needs_review: boolean };
type State = { versions: Version[]; imports: Import[]; tags: Record<string, string>; plans: Plan[]; outputs: Output[] };
type Product = { id: string; sources: { id: string; name: string; mime: string }[] };
const api = "/api/v1";
const angles = { front: "正面", back: "背面", side: "侧面", top: "顶部", bottom: "底部", interior: "内里" };

async function call<T>(path: string, method = "GET", body?: unknown): Promise<T> {
  const response = await fetch(api + path, {
    method,
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "请求失败，请核对输入");
  return data;
}

export function Workflow({ product }: { product: Product }) {
  const path = "/products/" + encodeURIComponent(product.id);
  const [data, setData] = useState<State>();
  const [templates, setTemplates] = useState<Record<string, Record<string, string>>>({});
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [reuse, setReuse] = useState<Plan>();
  const [activeImport, setActiveImport] = useState("");
  const [activePreview, setActivePreview] = useState("");
  useEffect(() => {
    Promise.all([call<State>(path + "/workflow"), call<typeof templates>("/templates")])
      .then(([workflow, available]) => { setData(workflow); setTemplates(available); })
      .catch((failure: Error) => setError(failure.message));
  }, [path]);

  async function action(url: string, method: string, payload?: unknown) {
    setBusy(true);
    setNotice("");
    setError("");
    try {
      await call(url, method, payload);
      setData(await call<State>(path + "/workflow"));
      setNotice("操作已完成");
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "操作失败");
    } finally {
      setBusy(false);
    }
  }

  function submit(event: FormEvent<HTMLFormElement>, run: (form: FormData) => void) {
    event.preventDefault();
    run(new FormData(event.currentTarget));
  }

  if (!data) return <p role={error ? "alert" : "status"}>{error || "正在读取商品工作流…"}</p>;
  const imported = data.imports.find((entry) => entry.id === activeImport) ?? data.imports[0];
  const docs = product.sources.filter((source) => source.mime === "application/pdf");
  const images = product.sources.filter((source) => source.mime.startsWith("image/"));
  return <>
    {busy && <p role="status">正在处理，请稍候…</p>}
    {notice && <p role="status">{notice}</p>}
    {error && <p className="error" role="alert">{error}</p>}
    <fieldset disabled={busy} className="workflow">
      <section>
        <h2>资料提取与入库</h2>
        {docs.length ? <form onSubmit={(event) => submit(event, (form) => {
          setActiveImport("");
          void action(path + "/imports", "POST", { category: form.get("category"), source_ids: form.getAll("source") });
        })}>
          <label>品类<select name="category"><option value="bag">箱包</option><option value="apparel">服饰</option></select></label>
          {docs.map((doc) => <label className="check" key={doc.id}><input name="source" type="checkbox" value={doc.id} />{doc.name}</label>)}
          <button>从选中资料提取字段</button>
        </form> : <p>先上传带文字层的 PDF 商品资料。</p>}
        {imported && <form key={imported.id} onSubmit={(event) => submit(event, (form) =>
          void action(path + "/versions", "POST", {
            import_id: imported.id, sku: form.get("sku"),
            fields: Object.fromEntries(Object.keys(imported.candidates).map((field) => [field, form.get(field)])),
          }))}>
          <label>提取记录<select value={imported.id} onChange={(event) => setActiveImport(event.currentTarget.value)}>
            {data.imports.map((entry, index) => <option key={entry.id} value={entry.id}>记录 {data.imports.length - index}</option>)}
          </select></label>
          {Object.entries(imported.candidates).map(([key, items]) => {
            const values = [...new Set(items.map((item) => item.value))];
            return <div key={key}>
              <label>{templates[imported.category]?.[key] || key}
                {values.length === 0 && " · 待补充"}{values.length > 1 && " · 有冲突"}
                <input name={key} required maxLength={300} defaultValue={values.length === 1 ? values[0] : ""} />
              </label>
              {items.map((item, index) => <p key={index}><a target="_blank" rel="noreferrer"
                href={api + path + "/sources/" + item.source_id + "#page=" + item.page}>{item.name} · 第 {item.page} 页</a>
                {" · "}{item.value} · {item.quote}</p>)}
            </div>;
          })}
          <label>SKU（选填）<input name="sku" maxLength={80} /></label>
          <button>确认并保存商品版本</button>
        </form>}
        {data.versions.map((version, index) => <details key={version.id} open={index === 0}>
          <summary>商品版本 {version.id}{index === 0 ? " · 当前" : ""}{version.sku && " · " + version.sku}</summary>
          {Object.entries(version.fields).map(([key, value]) => <p key={key}>{templates[version.category]?.[key] || key}：{value}</p>)}
        </details>)}
      </section>
      <section>
        <h2>参考素材与策划</h2>
        {images.map((image) => <label key={image.id}>{image.name}
          <select value={data.tags[image.id] || ""} onChange={(event) =>
            void action(path + "/references/" + image.id + "?angle=" + event.currentTarget.value, "PUT")}>
            <option value="" disabled>选择视角</option>
            {Object.entries(angles).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </label>)}
        {data.versions.length > 0 && Object.keys(data.tags).length > 0 ?
          <form id="plan-form" key={reuse?.id || "new"} onSubmit={(event) => submit(event, (form) =>
            void action(path + "/plans", "POST", { scene: form.get("scene"), source_ids: form.getAll("reference") }))}>
            <label>营销场景<input name="scene" required maxLength={300} placeholder="例如抖音春节年货节" /></label>
            {images.filter((image) => data.tags[image.id]).map((image) => <label className="check" key={image.id}>
              <input name="reference" type="checkbox" value={image.id} defaultChecked={reuse?.source_ids.includes(image.id)} />
              {image.name}
            </label>)}
            <button>生成策划</button>
          </form> : <p>确认商品版本并标记至少一张图片后，即可生成策划。</p>}
        {data.plans.map((plan) => <details key={plan.id}>
          <summary>{plan.scene} · 商品版本 {plan.version_id}</summary>
          <form onSubmit={(event) => submit(event, (form) => void action("/plans/" + plan.id, "PUT", {
            image_prompt: form.get("prompt"), shots: String(form.get("shots")).split("\n").map((line) => line.trim()).filter(Boolean),
          }))}>
            <label>图片提示词<textarea name="prompt" defaultValue={plan.script.image_prompt} required maxLength={3000} /></label>
            <label>分镜文案（每行一个，最多六个）<textarea name="shots" defaultValue={plan.script.shots.join("\n")} required /></label>
            <button>保存策划</button>
          </form>
          <div className="actions">
            <button onClick={() => void action("/plans/" + plan.id + "/outputs/image", "POST")}>生成商品图</button>
            <button onClick={() => void action("/plans/" + plan.id + "/outputs/video", "POST")}>合成竖屏视频</button>
            <button onClick={() => { setReuse(plan); requestAnimationFrame(() => document.getElementById("plan-form")?.scrollIntoView()); }}>复用此任务素材</button>
          </div>
        </details>)}
      </section>
      <section>
        <h2>成品审核与交付</h2>
        {!data.outputs.length && <p>生成的图片和视频会在这里等待审核。</p>}
        {data.outputs.map((output) => {
          const url = api + "/outputs/" + output.id;
          const plan = data.plans.find((entry) => entry.id === output.plan_id);
          const firstReference = plan?.source_ids[0];
          return <article key={output.id}>
            <h3>{output.kind === "video" ? "竖屏视频" : "商品图"} · {
              output.needs_review ? "关联商品版本已更新" : ({ pending: "待审核", approved: "已通过", rejected: "已驳回" })[output.status]}</h3>
            {output.note && <p>{output.note}</p>}
            <button onClick={() => setActivePreview(activePreview === output.id ? "" : output.id)}>
              {activePreview === output.id ? "收起预览" : "预览"}
            </button>
            {output.status === "approved" && !output.needs_review && <a href={url + "?download=true"}>下载成品</a>}
            {activePreview === output.id && <div className="preview">{output.kind === "video" ?
              <video src={url} controls /> : <div className="comparison">
                {firstReference && <figure><figcaption>参考图</figcaption>
                  <img src={api + path + "/sources/" + firstReference} alt="商品参考图" />
                </figure>}
                <figure><figcaption>生成结果</figcaption><img src={url} alt="待审核商品图" /></figure>
              </div>}</div>}
            <form onSubmit={(event) => {
              const button = (event.nativeEvent as SubmitEvent).submitter as HTMLButtonElement;
              submit(event, (form) => void action("/outputs/" + output.id + "/review?" + new URLSearchParams({
                approved: button.value, note: String(form.get("note")),
              }), "PUT"));
            }}>
              <label>审核说明<input name="note" maxLength={500} /></label>
              <div className="actions"><button value="true">通过</button><button value="false">驳回</button></div>
            </form>
          </article>;
        })}
      </section>
    </fieldset>
  </>;
}
