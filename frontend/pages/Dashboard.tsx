import { useEffect, useState } from "react";
import { api } from "../api";
import { ErrorBox, Loading, Notice, Section, Stat, statusTone, Badge } from "../ui";
import { navigate, productPath } from "../router";

function rate(value: any) {
  return value === null || value === undefined ? "未采集" : `${Math.round(value * 1000) / 10}%`;
}

export default function Dashboard() {
  const [stats, setStats] = useState<any>(null);
  const [products, setProducts] = useState<any[]>([]);
  const [pending, setPending] = useState<any[]>([]);
  const [models, setModels] = useState<any>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const [statsData, productData, pendingData, modelData] = await Promise.all([
        api.get("/stats"),
        api.get("/products"),
        api.get("/library/outputs?status=pending"),
        api.get("/models/status"),
      ]);
      setStats(statsData);
      setProducts(productData.items);
      setPending(pendingData.items);
      setModels(modelData);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  if (loading) return <Loading />;
  if (error) return <ErrorBox error={error} onRetry={load} />;

  return (
    <>
      <div className="hero">
        <h1>商品档案，从事实到成品</h1>
        <p>原始资料 → AI 抽取 → 规则校验 → 人工确认 → 六视角素材 → 场景策划 → 主图与短视频 → 审核交付 → 历史复用。</p>
        <div className="row">
          <button className="btn" onClick={() => navigate("/products")}>进入商品数据中心</button>
          <button className="btn btn-ghost" onClick={() => navigate("/reviews")}>处理待审核成品</button>
          <button className="btn btn-ghost" onClick={() => navigate("/library")}>打开资产库</button>
        </div>
      </div>

      <div className="grid four">
        <Stat label="商品" value={stats.products} hint={`${stats.confirmed_products} 个已确认版本`} />
        <Stat label="原始素材" value={stats.sources} hint="原件保存在本地并记录来源" />
        <Stat label="策划" value={stats.plans} hint={`复用 ${stats.reuse.plans_with_parent} 个`} />
        <Stat label="成品" value={stats.outputs.image + stats.outputs.video}
              hint={`图 ${stats.outputs.image} · 视频 ${stats.outputs.video}`} />
      </div>

      <div className="grid four mt">
        <Stat label="待审核成品" value={stats.review.pending} hint="未审核不得进入交付列表" />
        <Stat label="首轮审核通过率" value={rate(stats.first_pass_approval.value)}
              hint={`${stats.first_pass_approval.numerator}/${stats.first_pass_approval.denominator}，样本 ${stats.first_pass_approval.sample_size}`} />
        <Stat label="平均任务耗时" value={stats.avg_task_seconds.value === null ? "未采集" : `${stats.avg_task_seconds.value} 秒`}
              hint={`样本 ${stats.avg_task_seconds.sample_size}`} />
        <Stat label="素材复用率" value={rate(stats.reuse.rate)}
              hint={`${stats.reuse.plans_with_parent}/${stats.reuse.total_plans}`} />
      </div>

      <div className="grid two mt">
        <Section title="模型与依赖状态" subtitle="只检查配置是否存在，不发送真实请求，也不显示密钥">
          <div className="stack" style={{ gap: 8 }}>
            <div className="row gap wrap">
              <Badge tone={models.llm.configured ? "success" : "warn"}>
                文本模型 {models.llm.configured ? "已配置" : "未配置"}
              </Badge>
              <span className="muted small">{models.llm.model || "LLM_MODEL 未设置"}</span>
            </div>
            <div className="row gap wrap">
              <Badge tone={models.image.configured ? "success" : "warn"}>
                生图模型 {models.image.configured ? "已配置" : "未配置"}
              </Badge>
              <span className="muted small">{models.image.model || "IMAGE_MODEL 未设置"}</span>
            </div>
            <div className="row gap wrap">
              <Badge tone={models.ffmpeg.available ? "success" : "danger"}>
                FFmpeg {models.ffmpeg.available ? "可用" : "不可用"}
              </Badge>
              <Badge tone={models.ffmpeg.font ? "success" : "warn"}>
                中文字体 {models.ffmpeg.font ? "可用" : "缺失"}
              </Badge>
            </div>
            {!models.llm.configured && (
              <Notice tone="warn">
                文本模型未配置时无法进行 AI 抽取与自动策划。仍可使用“手工策划”（人工填写并确认）继续视频生产；
                真实生图需配置 IMAGE_URL / IMAGE_MODEL / IMAGE_API_KEY。
              </Notice>
            )}
          </div>
        </Section>

        <Section title="待审核队列" subtitle="驳回的成品保留在队列中供复盘，通过后才进入正式交付"
                 actions={<button className="btn btn-small btn-ghost" onClick={() => navigate("/reviews")}>查看全部</button>}>
          {pending.length === 0 ? (
            <div className="empty"><div className="empty-title">暂无待审核成品</div><div className="muted small">生成图片或视频后在此处理</div></div>
          ) : (
            <div>
              {pending.slice(0, 4).map((output) => (
                <div className="list-row" key={output.id}>
                  <div className="grow">
                    <div className="strong">{output.product_name} · {output.kind === "video" ? "短视频" : "商品图"}</div>
                    <div className="muted small">{output.plan?.scene} · 版本 v{output.plan?.version} · {output.kind}</div>
                  </div>
                  <Badge tone={statusTone(output.status)}>待审核</Badge>
                  <button className="btn btn-small btn-ghost"
                          onClick={() => navigate(productPath(output.product_id, "quality"))}>去审核</button>
                </div>
              ))}
            </div>
          )}
        </Section>
      </div>

      <Section title="商品档案" subtitle="同一商品详情页承载治理、素材、策划、生产与审核"
               actions={<button className="btn btn-small" onClick={() => navigate("/products")}>新建商品</button>}>
        {products.length === 0 ? (
          <div className="empty"><div className="empty-title">还没有商品</div><div className="muted small">先创建商品草稿，再上传原始资料</div></div>
        ) : (
          <table>
            <thead>
              <tr><th>商品编号</th><th>名称</th><th>品类</th><th>资料</th><th>版本</th><th>状态</th><th></th></tr>
            </thead>
            <tbody>
              {products.slice(0, 8).map((product) => (
                <tr key={product.id}>
                  <td className="mono">{product.id}</td>
                  <td>{product.name}</td>
                  <td>{product.category_id}</td>
                  <td>{product.source_count}</td>
                  <td>{product.version_count}</td>
                  <td><Badge tone={statusTone(product.status)}>{product.status === "confirmed" ? "已确认" : "草稿"}</Badge></td>
                  <td><a href={`#${productPath(product.id)}`}>查看详情</a></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Section>

      <Section title="失败类别" subtitle="来自真实工作流记录，用于判断是配置、额度、网络还是内容问题">
        {Object.keys(stats.failure_categories).length === 0 ? (
          <div className="muted small">暂无失败任务</div>
        ) : (
          <div className="pill-list">
            {Object.entries(stats.failure_categories).map(([code, count]) => (
              <Badge key={code} tone="danger">{code} × {String(count)}</Badge>
            ))}
          </div>
        )}
        <div className="muted small mt">成本指标：{stats.cost.status}。{stats.cost.note}</div>
      </Section>
    </>
  );
}
