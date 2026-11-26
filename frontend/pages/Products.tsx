import { useEffect, useState, type FormEvent } from "react";
import { api } from "../api";
import { Badge, ErrorBox, Field, Loading, Modal, Section, statusTone } from "../ui";
import { navigate, productPath } from "../router";

export default function Products({ initialSearch = "" }: { initialSearch?: string }) {
  const [products, setProducts] = useState<any[]>([]);
  const [categories, setCategories] = useState<any[]>([]);
  const [search, setSearch] = useState(initialSearch);
  const [showCreate, setShowCreate] = useState(false);
  const [filter, setFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [form, setForm] = useState({ id: "", name: "", category_id: "BAG", brand: "", origin: "", description: "" });
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<unknown>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const query = new URLSearchParams();
      if (search.trim()) query.set("search", search.trim());
      if (filter) query.set("category_id", filter);
      const [productData, categoryData] = await Promise.all([
        api.get(`/products?${query.toString()}`),
        api.get("/categories"),
      ]);
      setProducts(productData.items);
      setCategories(categoryData);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { const timer = setTimeout(() => { void load(); }, 250); return () => clearTimeout(timer); }, [filter, search]);

  async function create(event: FormEvent) {
    event.preventDefault();
    setCreating(true);
    setCreateError(null);
    try {
      const result = await api.post("/products", form);
      navigate(productPath(result.product.id));
    } catch (err) {
      setCreateError(err);
    } finally {
      setCreating(false);
    }
  }

  return (
    <>
      <div className="row between mb"><h2>全部商品</h2><button className="btn" onClick={() => setShowCreate(true)}>＋ 新建商品</button></div>

      {showCreate && <Modal title="新建商品" onClose={() => setShowCreate(false)}>
        <form onSubmit={create}>
          <div className="form-grid">
            <Field label="商品编号" required hint="1-32 位大写字母、数字或短横线，例如 BP01">
              <input value={form.id} onChange={(event) => setForm({ ...form, id: event.target.value.toUpperCase() })}
                     placeholder="BP01" required maxLength={32} />
            </Field>
            <Field label="商品名称" required hint="1-120 字">
              <input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })}
                     placeholder="女士双肩包" required maxLength={120} />
            </Field>
            <Field label="品类模板" required>
              <select value={form.category_id} onChange={(event) => setForm({ ...form, category_id: event.target.value })}>
                {categories.map((category) => (
                  <option key={category.id} value={category.id}>{category.name}（{category.id} v{category.version}）</option>
                ))}
              </select>
            </Field>
            <Field label="品牌"><input value={form.brand} onChange={(event) => setForm({ ...form, brand: event.target.value })} /></Field>
            <Field label="产地"><input value={form.origin} onChange={(event) => setForm({ ...form, origin: event.target.value })} /></Field>
            <Field label="备注描述">
              <input value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} />
            </Field>
          </div>
          {createError !== null && <div className="mt"><ErrorBox error={createError} /></div>}
          <div className="form-actions">
            <button className="btn" type="submit" disabled={creating || !form.id.trim() || !form.name.trim()}>
              {creating ? "创建中…" : "创建草稿"}
            </button>
          </div>
        </form>
      </Modal>}

      <Section title={`商品列表（${products.length}）`}
               actions={
                 <div className="toolbar">
                   <input style={{ width: 200 }} value={search} placeholder="搜索编号或名称"
                          onChange={(event) => setSearch(event.target.value)}
                          onKeyDown={(event) => { if (event.key === "Enter") load(); }} />
                   <select style={{ width: 140 }} value={filter} onChange={(event) => setFilter(event.target.value)}>
                     <option value="">全部品类</option>
                     {categories.map((category) => (
                       <option key={category.id} value={category.id}>{category.name}</option>
                     ))}
                   </select>
                   <button className="btn btn-small btn-ghost" onClick={load}>查询</button>
                 </div>
               }>
        {loading ? <Loading /> : error ? <ErrorBox error={error} onRetry={load} /> : products.length === 0 ? (
          <div className="empty"><div className="empty-title">没有匹配的商品</div><div className="muted small">调整搜索条件或新建商品</div></div>
        ) : (
          <div className="table-wrap"><table>
            <thead>
              <tr><th>商品编号</th><th>名称</th><th>品类</th><th>资料</th><th>版本</th><th>策划</th><th>成品</th><th>状态</th><th>更新时间</th><th></th></tr>
            </thead>
            <tbody>
              {products.map((product) => (
                <tr key={product.id}>
                  <td className="mono">{product.id}</td>
                  <td>{product.name}</td>
                  <td>{product.category_id}</td>
                  <td>{product.source_count}</td>
                  <td>{product.version_count}</td>
                  <td>{product.plan_count}</td>
                  <td>{product.output_count}</td>
                  <td><Badge tone={statusTone(product.status)}>{product.status === "confirmed" ? "已确认" : "草稿"}</Badge></td>
                  <td className="muted small nowrap">{product.updated_at?.slice(0, 19).replace("T", " ")}</td>
                  <td><a href={`#${productPath(product.id)}`}>打开详情</a></td>
                </tr>
              ))}
            </tbody>
          </table></div>
        )}
        {error !== null && !loading && <div className="mt"><ErrorBox error={error} onRetry={load} /></div>}
      </Section>
    </>
  );
}
