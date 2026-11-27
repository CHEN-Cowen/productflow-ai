import { useEffect, useState, type ReactNode } from "react";
import { createRoot } from "react-dom/client";
import "./style.css";
import { api } from "./api";
import { navigate, useHashRoute } from "./router";
import Dashboard from "./pages/Dashboard";
import Catalog from "./pages/Catalog";
import ProductDetail from "./pages/ProductDetail";
import Reviews from "./pages/Reviews";
import Library from "./pages/Library";
import Studio from "./pages/Studio";
import Tasks from "./pages/Tasks";

function Icon({name}:{name:string}) {
  const paths:Record<string,ReactNode>={
    home:<><rect x="3" y="3" width="18" height="18" rx="3"/><path d="M9 3v18M9 10h12"/></>,
    products:<path d="m12 3 9 5-9 5-9-5 9-5ZM3 8v9l9 5 9-5V8M12 13v9"/>,
    factory:<path d="m12 2 2.5 7.5L22 12l-7.5 2.5L12 22l-2.5-7.5L2 12l7.5-2.5L12 2Z"/>,
    plan:<><rect x="4" y="3" width="16" height="18" rx="2"/><path d="M8 8h8M8 12h8M8 16h5"/></>,
    image:<><rect x="3" y="3" width="18" height="18" rx="3"/><circle cx="8" cy="8" r="1.5"/><path d="m3 17 6-6 4 4 3-3 5 5"/></>,
    video:<><rect x="3" y="4" width="18" height="16" rx="3"/><path d="m10 8 6 4-6 4V8Z"/></>,
    tasks:<><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></>,
    assets:<><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></>,
    reviews:<><rect x="4" y="3" width="16" height="18" rx="2"/><path d="m8 12 3 3 5-6"/></>
  };
  return <svg className="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>;
}
const FACTORY=[
  {path:"/studio/plans",label:"内容策划",icon:"plan"},
  {path:"/studio/image",label:"图片生产",icon:"image"},
  {path:"/studio/video",label:"视频生产",icon:"video"},
  {path:"/tasks",label:"生产任务",icon:"tasks"}
];
function App(){
  const route=useHashRoute();
  const factoryActive=route.path.startsWith("/studio")||route.path==="/tasks";
  const [factoryOpen,setFactoryOpen]=useState(factoryActive);
  const [mobileOpen,setMobileOpen]=useState(false);
  const [pending,setPending]=useState<number|null>(null);
  const [search,setSearch]=useState("");
  useEffect(()=>{setMobileOpen(false);if(factoryActive)setFactoryOpen(true)},[route.hash]);
  useEffect(()=>{
    let active=true;
    api.get("/stats").then(s=>{if(active)setPending(s.review.pending)}).catch(()=>{if(active)setPending(null)});
    return ()=>{active=false};
  },[route.hash]);
  function nav(path:string,label:string,icon:string,active:boolean){
    return <a href={"#"+path} className={active?"active":""} aria-current={active?"page":undefined}><Icon name={icon}/><span className="grow">{label}</span>{path==="/reviews"&&pending!==null&&pending>0&&<span className="nav-count">{pending}</span>}</a>;
  }
  let page:ReactNode;
  if(!route.segments.length)page=<Dashboard/>;
  else if(route.segments[0]==="products"&&route.segments[1])page=<ProductDetail key={route.segments[1]} productId={decodeURIComponent(route.segments[1])} tab={route.params.get("tab")||"overview"}/>;
  else if(["products","imports"].includes(route.segments[0]))page=<Catalog key={route.hash} view={route.path==="/imports"?"import":route.params.get("view")||"list"} search={route.params.get("search")||""}/>;
  else if(route.segments[0]==="studio")page=<Studio key={route.hash} mode={route.segments[1]||"plans"}/>;
  else if(route.segments[0]==="tasks")page=<Tasks key={route.hash} initialStatus={route.params.get("status")||""}/>;
  else if(route.segments[0]==="reviews")page=<Reviews/>;
  else if(route.segments[0]==="library")page=<Library key={route.params.get("view") || "outputs"} initialView={route.params.get("view") === "sources" ? "sources" : "outputs"}/>;
  else page=<div className="card"><h1>页面不存在</h1><a href="#/">返回工作台</a></div>;
  return <div className="app-shell">
    {mobileOpen&&<button className="sidebar-backdrop" aria-label="关闭导航" onClick={()=>setMobileOpen(false)}/>}
    <aside className={"sidebar "+(mobileOpen?"is-open":"")} aria-label="主导航">
      <a className="brand" href="#/"><div className="brand-mark">✳</div><div className="brand-name">ProductFlow <span>AI</span></div></a>
      <nav className="nav">
        {nav("/","工作台","home",route.path==="/")}
        {nav("/products","商品库","products",["products","imports"].includes(route.segments[0]))}
        <button className={"nav-parent "+(factoryActive?"current":"")} aria-expanded={factoryOpen} aria-controls="factory-navigation" onClick={()=>setFactoryOpen(v=>!v)}><Icon name="factory"/><span className="grow">AI 内容工厂</span><span className={"nav-chevron "+(factoryOpen?"expanded":"")} aria-hidden="true">›</span></button>
        <div id="factory-navigation" className="nav-children" hidden={!factoryOpen}>{FACTORY.map(i=><div key={i.path}>{nav(i.path,i.label,i.icon,route.path===i.path||(route.path==="/studio"&&i.path==="/studio/plans"))}</div>)}</div>
        {nav("/library?view=sources","商品素材库","assets",route.path==="/library" && route.params.get("view")==="sources")}
        {nav("/library","内容成品库","assets",route.path==="/library" && route.params.get("view")!=="sources")}
        {nav("/reviews","质量与交付","reviews",route.path==="/reviews")}
      </nav>
    </aside>
    <div className="workspace"><header className="workspace-header">
      <button className="btn btn-ghost menu-toggle" aria-label={mobileOpen?"关闭导航":"展开导航"} aria-expanded={mobileOpen} onClick={()=>setMobileOpen(v=>!v)}>☰</button>
      <form className="global-search" onSubmit={e=>{e.preventDefault();navigate("/products?search="+encodeURIComponent(search.trim()))}}><input aria-label="搜索商品编号或名称" placeholder="搜索商品编号或名称…" value={search} onChange={e=>setSearch(e.target.value)}/></form>
      <span className="internal-label">内部工作台</span><a className="btn btn-ghost btn-small" href="#/reviews">待审核{pending!==null?" "+pending:""}</a>
    </header><main className="main" id="main-content">{page}</main></div>
  </div>;
}
createRoot(document.getElementById("root")!).render(<App/>);
