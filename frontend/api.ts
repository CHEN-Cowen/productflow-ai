export class ApiError extends Error {
  code: string;
  hint: string;
  status: number;

  constructor(message: string, code = "error", hint = "", status = 0) {
    super(message);
    this.code = code;
    this.hint = hint;
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/v1${path}`, init);
  if (!response.ok) {
    let message = `请求失败（HTTP ${response.status}）`;
    let code = "http_error";
    let hint = "";
    try {
      const body = await response.json();
      const detail = body?.detail;
      if (typeof detail === "string") {
        message = detail;
      } else if (detail && typeof detail === "object") {
        message = detail.message || message;
        code = detail.code || code;
        hint = detail.hint || "";
      } else if (Array.isArray(detail)) {
        message = detail.map((item: any) => item.msg).join("；");
        code = "validation_error";
      }
    } catch {
      /* 非 JSON 错误体 */
    }
    throw new ApiError(message, code, hint, response.status);
  }
  if (response.status === 204) return undefined as T;
  const type = response.headers.get("content-type") || "";
  return (type.includes("application/json") ? response.json() : response.blob()) as Promise<T>;
}

export const api = {
  get: <T = any>(path: string) => request<T>(path),
  post: <T = any>(path: string, body?: any) =>
    request<T>(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    }),
  put: <T = any>(path: string, body?: any) =>
    request<T>(path, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    }),
  upload: <T = any>(path: string, form: FormData) => request<T>(path, { method: "POST", body: form }),
};

export function errorText(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "未知错误";
}

export function errorHint(error: unknown): string {
  return error instanceof ApiError ? error.hint : "";
}

export function errorCode(error: unknown): string {
  return error instanceof ApiError ? error.code : "";
}

export const ANGLES: { value: string; label: string }[] = [
  { value: "front", label: "正面" },
  { value: "back", label: "背面" },
  { value: "side", label: "侧面" },
  { value: "top", label: "顶部" },
  { value: "bottom", label: "底部" },
  { value: "interior", label: "内里" },
];

export const PURPOSES = [
  { value: "reference", label: "商品参考" },
  { value: "spec", label: "规格资料" },
  { value: "marketing", label: "营销素材" },
];

export function angleLabel(value: string): string {
  return ANGLES.find((item) => item.value === value)?.label || "未标注";
}

export function statusLabel(status: string): string {
  const map: Record<string, string> = {
    draft: "草稿",
    confirmed: "已确认",
    reviewing: "待审核",
    rejected: "已驳回",
    pending: "待审核",
    approved: "已通过",
    success: "成功",
    running: "进行中",
    failed: "失败",
    completed: "已完成",
    stored: "已保存",
  };
  return map[status] || status || "—";
}

export function formatTime(value?: string): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", { hour12: false });
}

export function formatSize(size?: number): string {
  if (!size) return "—";
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / 1024 / 1024).toFixed(2)} MB`;
}
