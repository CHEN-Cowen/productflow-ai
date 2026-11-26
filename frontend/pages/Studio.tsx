import { useEffect, useState } from "react";
import { api } from "../api";
import { Badge, Empty, ErrorBox, Loading, Notice, Section } from "../ui";
import { navigate, productPath } from "../router";

export default function Studio() {
  const [products, setProducts] = useState<any[]>([]);
  const [models, setModels] = useState<any>(null);
  const [pending, setPending] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const [productData, modelData, pendingData] = await Promise.all([
        api.get("/products"),
        api.get("/models/status"),
        api.get("/library/outputs?status=pending"),
      ]);
      setProducts(productData.items);
      setModels(modelData);
      setPending(pendingData.items);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  if (loading) return <Loading />;
  if (error) return <ErrorBox error={error} onRetry={load} />;

  const confirmed = products.filter((product) => product.status === "confirmed");
  const pendingByProduct = new Map<string, number>();
  for (const output of pending) {
    pendingByProduct.set(output.product_id, (pendingByProduct.get(output.product_id) || 0) + 1);
  }

  return (
    <>
      <div className="topbar">
        <div>
          <div className="crumbs">内容生产</div>
          <h1>生产工作台</h1>
          <p className="page-sub">读取已确认策划与素材，调用真实生图接口，或用 FFmpeg 合成竖屏短视频。</p>
        </div>
        <div className="toolbar">
          <button className="btn btn-small btn-ghost" onClick={() => navigate("/reviews")}>待审核 {pending.length}</button>
        </div>
      </div>

      <Section title="生产条件" subtitle="配置与依赖状态；未配置的真实接口会返回可行动的错误类别，不会用模拟结果冒充成品">
        <div className="grid three">
          <div className="candidate">
            <Badge tone={models.llm.configured ? "success" : "warn"}>文本模型</Badge>
            <div className="small mt">{models.llm.configured ? `已配置 ${models.llm.model}` : "未配置：AI 抽取/策划不可用，可改用手工策划"}</div>
          </div>
          <div className="candidate">
            <Badge tone={models.image.configured ? "success" : "warn"}>生图模型</Badge>
            <div className="small mt">{models.image.configured ? `已配置 ${models.image.model}` : "未配置：真实生图会返回配置错误并记录任务"}</div>
          </div>
          <div className="candidate">
            <Badge tone={models.ffmpeg.available && models.ffmpeg.font ? "success" : "danger"}>视频合成</Badge>
            <div className="small mt">
              FFmpeg {models.ffmpeg.available ? "可用" : "不可用"} · 字体 {models.ffmpeg.font ? "可用" : "缺失"} · ffprobe {models.ffmpeg.ffprobe ? "可用" : "缺失"}
            </div>
          </div>
        </div>
        {!models.image.configured && (
          <Notice tone="warn"><div className="mt">真实生图需要 IMAGE_URL、IMAGE_MODEL、IMAGE_API_KEY；额度恢复后可在商品详情“生产”页重试。</div></Notice>
        )}
      </Section>

      <Section title={`可生产商品（${confirmed.length}）`} subtitle="只有完成人工确认的商品版本才能进入策划与生产">
        {confirmed.length === 0 ? (
          <Empty title="还没有已确认商品" hint="完成一次资料导入并人工确认后，商品状态变为已确认" />
        ) : (
          <table>
            <thead><tr><th>商品</th><th>品类</th><th>策划</th><th>成品</th><th>待审核</th><th>入口</th></tr></thead>
            <tbody>
              {confirmed.map((product) => (
                <tr key={product.id}>
                  <td><div className="strong">{product.name}</div><div className="mono muted small">{product.id}</div></td>
                  <td>{product.category_id}</td>
                  <td>{product.plan_count}</td>
                  <td>{product.output_count}</td>
                  <td>{pendingByProduct.get(product.id) || 0}</td>
                  <td>
                    <div className="toolbar">
                      <button className="btn btn-small btn-ghost" onClick={() => navigate(productPath(product.id, "plans"))}>策划</button>
                      <button className="btn btn-small" onClick={() => navigate(productPath(product.id, "production"))}>生产</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Section>

      <Section title="待审核成品" subtitle="生产完成后先进入审核队列，通过后才可正式交付">
        {pending.length === 0 ? <Empty title="没有待审核成品" /> : (
          <table>
            <thead><tr><th>商品</th><th>类型</th><th>场景</th><th>版本</th><th></th></tr></thead>
            <tbody>
              {pending.map((output) => (
                <tr key={output.id}>
                  <td>{output.product_name}</td>
                  <td>{output.kind === "video" ? "短视频" : "商品图"}</td>
                  <td>{output.plan?.scene}</td>
                  <td>v{output.plan?.version}</td>
                  <td><button className="btn btn-small btn-ghost" onClick={() => navigate(productPath(output.product_id, "quality"))}>审核</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Section>
    </>
  );
}
