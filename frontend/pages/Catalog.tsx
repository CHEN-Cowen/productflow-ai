import {useEffect,useState} from "react";
import {api} from "../api";
import {Empty,ErrorBox,Loading,Section,Badge,statusTone} from "../ui";
import {navigate,productPath} from "../router";
import Products from "./Products";
import BatchImport from "./BatchImport";
import ProductDetail from "./ProductDetail";

const TABS=[["list","商品资料"],["import","数据导入"],["clean","AI 清洗"],["quality","数据质量"]];
export default function Catalog({view,search=""}:{view:string;search?:string}){
  const current=TABS.some(t=>t[0]===view)?view:"list";
  return <><div className="topbar"><h1>商品库</h1></div><div className="tabs" aria-label="商品库功能">{TABS.map(([key,label])=><button key={key} className={current===key?"active":""} aria-pressed={current===key} onClick={()=>navigate("/products?view="+key)}>{label}</button>)}</div>
    {current==="list"?<Products initialSearch={search}/>:current==="import"?<BatchImport/>:<CatalogData mode={current}/>}
  </>;
}
function CatalogData({mode}:{mode:string}){
  const [products,setProducts]=useState<any[]>([]);
  const [details,setDetails]=useState<any[]>([]);
  const [selected,setSelected]=useState("");
  const [loading,setLoading]=useState(true);
  const [error,setError]=useState<unknown>(null);
  useEffect(()=>{
    let active=true;
    async function load(){
      try{
        const catalog=await api.get("/products");
        const records=mode==="quality"?await Promise.all(catalog.items.map((p:any)=>api.get("/products/"+encodeURIComponent(p.id)))):[];
        if(active){setProducts(catalog.items);setDetails(records);setSelected(catalog.items[0]?.id||"")}
      }catch(err){if(active)setError(err)}finally{if(active)setLoading(false)}
    }
    void load();return ()=>{active=false};
  },[mode]);
  if(loading)return <Loading/>;
  if(error)return <ErrorBox error={error}/>;
  if(!products.length)return <Empty title="请先创建商品或导入商品资料"/>;
  if(mode==="quality")return <Section title="商品资料质量"><div className="table-wrap"><table><thead><tr><th>商品</th><th>必填完整度</th><th>待补字段</th><th>确认状态</th><th>操作</th></tr></thead><tbody>{details.map(d=><tr key={d.product.id}><td><b>{d.product.name}</b><div className="muted">{d.product.id}</div></td><td>{d.completeness.required_filled}/{d.completeness.required_total}</td><td>{d.completeness.missing.join("、")||"已齐全"}</td><td><Badge tone={statusTone(d.product.status)}>{d.product.status==="confirmed"?"已确认":"待确认"}</Badge></td><td><a className="btn btn-small btn-ghost" href={"#"+productPath(d.product.id,"docs")}>查看并处理</a></td></tr>)}</tbody></table></div></Section>;
  return <><div className="filters"><label className="field"><span className="field-label">选择商品</span><select value={selected} onChange={e=>setSelected(e.target.value)}>{products.map(p=><option key={p.id} value={p.id}>{p.id} · {p.name}</option>)}</select></label></div>{selected&&<ProductDetail key={selected} productId={selected} tab="docs" embedded/>}</>;
}
