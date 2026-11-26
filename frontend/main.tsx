import { useEffect, useState, type ReactNode } from "react";
import { createRoot } from "react-dom/client";
import "./style.css";
import { api } from "./api";
import { useHashRoute } from "./router";
import Dashboard from "./pages/Dashboard";
import Products from "./pages/Products";
import ProductDetail from "./pages/ProductDetail";
import BatchImport from "./pages/BatchImport";
import Reviews from "./pages/Reviews";
import Library from "./pages/Library";
import Studio from "./pages/Studio";

const NAV = [
  { path: "/", label: "工作台", match: (path: string) => path === "/" },
  { path: "/products", label: "商品数据中心", match: (path: string) => path.startsWith("/products") },
  { path: "/imports", label: "数据导入", match: (path: string) => path.startsWith("/imports") },
  { path: "/studio", label: "内容生产", match: (path: string) => path.startsWith("/studio") },
  { path: "/reviews", label: "质量审核", match: (path: string) => path.startsWith("/reviews") },
  { path: "/library", label: "资产库", match: (path: string) => path.startsWith("/library") },
];

function App() {
  const route = useHashRoute();
  const [pending, setPending] = useState<number | null>(null);

  useEffect(() => {
    api.get("/stats").then((stats) => setPending(stats.review.pending)).catch(() => setPending(null));
  }, [route.path]);

  let page: ReactNode;
  if (route.segments.length === 0) {
    page = <Dashboard />;
  } else if (route.segments[0] === "products" && route.segments[1]) {
    page = <ProductDetail productId={decodeURIComponent(route.segments[1])}
                          tab={route.params.get("tab") || "overview"} />;
  } else if (route.segments[0] === "products") {
    page = <Products />;
  } else if (route.segments[0] === "imports") {
    page = <BatchImport />;
  } else if (route.segments[0] === "reviews") {
    page = <Reviews />;
  } else if (route.segments[0] === "library") {
    page = <Library />;
  } else if (route.segments[0] === "studio") {
    page = <Studio />;
  } else {
    page = (
      <div className="card">
        <h2>页面不存在</h2>
        <p className="muted">请从左侧导航进入。</p>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">P</div>
          <div className="brand-name">ProductFlow AI</div>
        </div>
        <div className="brand-sub">商品数据治理 · AI 内容生产</div>
        <nav className="nav">
          {NAV.map((item) => (
            <a key={item.path} href={`#${item.path}`} className={item.match(route.path) ? "active" : ""}>
              <span>{item.label}</span>
              {item.path === "/reviews" && pending !== null && pending > 0 && <span className="nav-count">{pending}</span>}
            </a>
          ))}
        </nav>
        <div className="sidebar-foot">
          <div><span className="dot">●</span> 本地模块化单体</div>
          <div>React + FastAPI + SQLite</div>
          <div>业务前缀 /api/v1</div>
          <div className="mt">密钥只由后端读取；<br />真实接口未配置时显示可行动错误。</div>
        </div>
      </aside>
      <main className="main">{page}</main>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
