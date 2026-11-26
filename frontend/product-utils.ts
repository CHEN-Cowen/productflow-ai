export function locatorText(locator: any): string {
  if (!locator || !locator.kind) return "—";
  if (locator.kind === "pdf") return `PDF 第 ${locator.page} 页`;
  if (locator.kind === "xlsx") return `工作表「${locator.sheet}」第 ${locator.row} 行`;
  if (locator.kind === "docx") {
    return locator.table ? `表格 ${locator.table} 第 ${locator.row} 行` : `第 ${locator.paragraph} 段`;
  }
  if (locator.kind === "image") return "OCR 识别文本";
  return JSON.stringify(locator);
}

export function fieldLabels(detail: any): Record<string, string> {
  const result: Record<string, string> = {};
  for (const attr of detail?.category?.schema?.attributes || []) {
    result[attr.key] = attr.label;
  }
  return result;
}

export function planTemplate(detail: any): string {
  const attrs = detail?.category?.schema?.attributes || [];
  const fields = detail?.latest_version?.fields || {};
  const used = attrs.filter((attr: any) => fields[attr.key]).slice(0, 2);
  const points = (used.length ? used : attrs.slice(0, 2)).map((attr: any, index: number) => ({
    text: index === 0 ? "请填写有事实依据的卖点" : "请填写第二个卖点",
    field: attr.key,
    evidence: String(fields[attr.key] || "填写该字段值中的原文片段").slice(0, 40),
  }));
  return JSON.stringify({
    theme: "请填写营销主题",
    selling_points: points,
    copy: "请填写投放文案，不得出现事实中没有的材质、功效或绝对化用语",
    visual: "请填写主视觉说明",
    image_prompt: "请填写图片提示词，保留已确认的颜色、材质、五金等事实",
    shots: [
      { caption: "第一镜字幕", angle: "front", duration: 4 },
      { caption: "第二镜字幕", angle: "side", duration: 4 },
      { caption: "第三镜字幕", angle: "bottom", duration: 4 },
    ],
    hashtags: ["春节年货节"],
  }, null, 2);
}

export function prettyLocator(locator: any): string {
  return locatorText(locator);
}

export function outputTargetLabel(output: any): string {
  return `${output.product_name} · ${output.kind === "video" ? "短视频" : "商品图"}`;
}
