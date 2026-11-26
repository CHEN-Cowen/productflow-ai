import {useEffect,useState} from "react";
import {api} from "../api";
import {Empty,ErrorBox,Loading} from "../ui";
import ProductDetail from "./ProductDetail";
const MODES:Record<string,{title:string;tab:string;kind?:"image"|"video"}>={
  plans:{title:"内容策划",tab:"plans"},
  image:{title:"图片生产",tab:"production",kind:"image"},
  video:{title:"视频生产",tab:"production",kind:"video"}
};
export default function Studio({mode="plans"}:{mode?:string}){
  const current=MODES[mode]||MODES.plans;
  const [products,setProducts]=useState<any[]>([]),[selected,setSelected]=useState("");
  const [error,setError]=useState<unknown>(null),[loading,setLoading]=useState(true);
  useEffect(()=>{
    let active=true;
    api.get("/products").then(data=>{if(active){setProducts(data.items);setSelected(data.items.find((p:any)=>p.status==="confirmed")?.id||data.items[0]?.id||"")}})
      .catch(err=>{if(active)setError(err)}).finally(()=>{if(active)setLoading(false)});
    return ()=>{active=false};
  },[]);
  return <><div className="topbar"><h1>{current.title}</h1></div>{loading?<Loading/>:error?<ErrorBox error={error}/>:!products.length?<Empty title="请先在商品库建立商品档案"/>:<>
    <div className="filters"><label className="field"><span className="field-label">关联商品</span><select value={selected} onChange={e=>setSelected(e.target.value)}>{products.map(p=><option key={p.id} value={p.id}>{p.id} · {p.name}{p.status==="confirmed"?"":"（待确认）"}</option>)}</select></label></div>
    {selected&&<ProductDetail key={selected} productId={selected} tab={current.tab} productionKind={current.kind} embedded/>}
  </>}</>;
}
