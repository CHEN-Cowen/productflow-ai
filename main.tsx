import { useEffect, useState, type FormEvent } from "react";
import { createRoot } from "react-dom/client";
import "./style.css";
import { Workflow } from "./workflow";

type Source = { id: string; name: string; mime: string };
type Product = { id: string; name: string; status: string; sources: Source[] };
const endpoint = "/api/v1/products";

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, options);
  const body = await response.json();
  if (!response.ok) throw new Error(typeof body.detail === "string" ? body.detail : "请检查填写内容后重试");
  return body as T;
}

function App() {
  const [product, setProduct] = useState<Product>();
  const [preview, setPreview] = useState<Source>();
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");
  const [loadFailed, setLoadFailed] = useState(false);
  const [notice, setNotice] = useState("");

  useEffect(() => {
    const id = new URLSearchParams(location.search).get("product");
    if (!id) {
      setBusy(false);
      return;
    }
    request<Product>(endpoint + "/" + encodeURIComponent(id))
      .then(setProduct)
      .catch((failure: Error) => { setError(failure.message); setLoadFailed(true); })
      .finally(() => setBusy(false));
  }, []);

  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await action();
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "操作失败");
    } finally {
      setBusy(false);
    }
  }

  function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    void run(async () => {
      const draft = await request<Product>(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(Object.fromEntries(form)),
      });
      history.replaceState(null, "", "?product=" + encodeURIComponent(draft.id));
      setProduct(draft);
      setNotice("草稿已保存");
    });
  }

  function upload(event: FormEvent<HTMLFormElement>, draft: Product) {
    event.preventDefault();
    const element = event.currentTarget;
    const form = new FormData(element);
    void run(async () => {
      const source = await request<Source>(endpoint + "/" + draft.id + "/sources", { method: "POST", body: form });
      setProduct({ ...draft, sources: [...draft.sources, source] });
      setPreview(source);
      element.reset();
      setNotice("原始资料已上传");
    });
  }

  const previewUrl = product && preview ? endpoint + "/" + product.id + "/sources/" + preview.id : "";
  return <main>
    <header>ProductFlow AI</header>
    <h1>商品档案</h1>
    {error && <p className="error" role="alert">{error}</p>}
    {notice && <p role="status">{notice}</p>}
    {loadFailed && <a href="/">返回新建草稿</a>}
    {!product && !loadFailed && (busy ? <p>正在读取草稿…</p> : <form onSubmit={create}>
      <h2>新建商品草稿</h2>
      <label>商品编号<input name="id" defaultValue="BP01" required pattern="[A-Z0-9][A-Z0-9\-]{0,31}" /></label>
      <label>商品名称<input name="name" defaultValue="女士双肩包" required maxLength={120} /></label>
      <button>保存草稿</button>
    </form>)}
    {product && <>
      <section><h2>{product.name}</h2><p>{product.id}</p><a href="/">新建其他商品</a></section>
      <section>
        <h2>原始资料</h2>
        <form className="upload" onSubmit={(event) => upload(event, product)}>
          <label>选择资料 <small>PDF、PNG 或 JPEG，最多 10 MB</small>
            <input name="file" type="file" accept=".pdf,.png,.jpeg,.jpg" required disabled={busy} />
          </label>
          <button disabled={busy}>{busy ? "正在上传…" : "上传资料"}</button>
        </form>
        {product.sources.length === 0 ? <p>已上传的资料会显示在这里。</p> :
          <ul>{product.sources.map((source) => <li key={source.id}>
            <button className="link" onClick={() => setPreview(source)} aria-pressed={preview?.id === source.id}>{source.name}</button>
          </li>)}</ul>}
        {preview && <div className="preview">
          <h3>{preview.name}</h3>
          <a href={previewUrl} target="_blank" rel="noreferrer">在新标签页打开</a>
          {preview.mime === "application/pdf" ? <iframe title={preview.name} src={previewUrl} /> :
            <img src={previewUrl} alt={preview.name} />}
        </div>}
      </section>
      <Workflow key={product.id} product={product} />
    </>}
  </main>;
}
createRoot(document.getElementById("root")!).render(<App />);
