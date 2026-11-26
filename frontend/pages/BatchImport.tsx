import { useState } from "react";
import { api } from "../api";
import { Badge, ErrorBox, Field, Section, statusTone } from "../ui";
import { navigate, productPath } from "../router";

const SAMPLE = JSON.stringify([
  {
    product_id: "BATCH-DEMO-1",
    name: "批量导入演示双肩包",
    category_id: "BAG",
    fields: {
      body_material: "羊毛 70%、聚酯纤维 30%",
      lining_material: "棕色帆布",
      dimensions: "28 × 24 × 12 cm",
      color: "暖米白",
    },
  },
  {
    product_id: "BATCH-DEMO-2",
    name: "批量导入演示开衫",
    category_id: "APPAREL",
    fields: { fabric: "棉 80%、羊毛 20%", size: "M", color: "米白" },
  },
], null, 2);

export default function BatchImport() {
  const [mode, setMode] = useState<"json" | "csv">("json");
  const [text, setText] = useState(SAMPLE);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [job, setJob] = useState<any>(null);

  function parseRows(): any[] {
    if (mode === "json") {
      const value = JSON.parse(text);
      if (!Array.isArray(value)) throw new Error("JSON 顶层必须是数组");
      return value;
    }
    const lines = text.trim().split(/\r?\n/).filter(Boolean);
    if (lines.length < 2) throw new Error("CSV 至少需要表头和数据行");
    const header = lines[0].split(",").map((item) => item.trim());
    return lines.slice(1).map((line) => {
      const cells = line.split(",").map((item) => item.trim());
      const row: any = {};
      header.forEach((key, index) => {
        if (key === "fields") {
          row.fields = JSON.parse(cells[index] || "{}");
        } else {
          row[key] = cells[index] || "";
        }
      });
      return row;
    });
  }

  async function submit() {
    setBusy(true);
    setError(null);
    setJob(null);
    try {
      const rows = parseRows();
      const result = await api.post("/imports/batch", { rows });
      setJob(result);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  const failed = job?.results?.filter((item: any) => item.status === "failed") || [];

  return (
    <>
      <div className="topbar">
        <div>
          <div className="crumbs">数据导入</div>
          <h1>跨商品批量导入</h1>
          <p className="page-sub">逐行处理并保留成功与失败原因；同批次重复编号、字段缺失或类型错误进入异常队列。</p>
        </div>
      </div>

      <Section title="粘贴或上传数据" subtitle="JSON 行数组，或 CSV（表头 product_id,name,category_id,sku,fields；fields 为 JSON）">
        <div className="row gap mb">
          <label className="row gap small"><input type="radio" checked={mode === "json"} onChange={() => { setMode("json"); setText(SAMPLE); }} /> JSON</label>
          <label className="row gap small"><input type="radio" checked={mode === "csv"} onChange={() => { setMode("csv"); setText("product_id,name,category_id,sku,fields\nCSV-DEMO-1,CSV 演示箱包,BAG,CSV-DEMO-1-01,\"{\"\"body_material\"\":\"\"羊毛混纺\"\",\"\"lining_material\"\":\"\"帆布\"\",\"\"dimensions\"\":\"\"28 x 24 x 12 cm\"\",\"\"color\"\":\"\"暖米白\"\"}\""); }} /> CSV</label>
        </div>
        <Field label="数据内容" required>
          <textarea className="code" value={text} onChange={(event) => setText(event.target.value)} />
        </Field>
        {error !== null && <div className="mt"><ErrorBox error={error} /></div>}
        <div className="form-actions">
          <button className="btn" disabled={busy} onClick={submit}>{busy ? "逐行处理中…" : "开始批量导入"}</button>
        </div>
      </Section>

      {job && (
        <>
          <Section title="处理结果" subtitle={`任务 ${job.id.slice(0, 8)} · 成功 ${job.ok} · 失败 ${job.failed}`}>
            <table>
              <thead><tr><th>行号</th><th>商品编号</th><th>结果</th><th>说明</th><th></th></tr></thead>
              <tbody>
                {job.results.map((item: any) => (
                  <tr key={item.row}>
                    <td>{item.row}</td>
                    <td className="mono">{item.product_id || "—"}</td>
                    <td><Badge tone={item.status === "ok" ? "success" : "danger"}>{item.status === "ok" ? "已入库" : "失败"}</Badge></td>
                    <td className="small">{item.message}{item.code ? `（${item.code}）` : ""}</td>
                    <td>{item.status === "ok" && <a href={`#${productPath(item.product_id)}`}>打开商品</a>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Section>

          <Section title={`异常队列（${failed.length}）`} subtitle="失败行已保留原因，可修正后重新提交；不会中断其他行">
            {failed.length === 0 ? <div className="muted small">没有失败行</div> : (
              <div className="stack">
                {failed.map((item: any) => (
                  <div className="issue conflict" key={item.row}>
                    <div className="strong">第 {item.row} 行 · {item.product_id || "未填写编号"}</div>
                    <div>{item.message}</div>
                    <div className="muted small">错误类别：{item.code}</div>
                  </div>
                ))}
              </div>
            )}
            <div className="form-actions">
              <button className="btn btn-small btn-ghost" onClick={() => navigate("/products")}>查看商品列表</button>
            </div>
          </Section>
        </>
      )}
    </>
  );
}
