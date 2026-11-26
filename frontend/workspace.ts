import { useEffect, useState } from "react";
import { api } from "./api";
export function runLabel(type:string){return ({image_generation:"图片生产",video_generation:"视频生产",planning:"内容策划"} as Record<string,string>)[type]||"资料处理";}
export function runProgress(run:any){
  const steps=run.steps||[];
  return {done:steps.filter((s:any)=>s.status==="success").length,total:steps.length};
}
export function useWorkspaceFeed(){
  const [products,setProducts]=useState<any[]>([]);
  const [runs,setRuns]=useState<any[]>([]);
  const [pending,setPending]=useState<any[]>([]);
  const [loading,setLoading]=useState(true);
  const [error,setError]=useState<unknown>(null);
  useEffect(()=>{
    let stopped=false;
    let timer:ReturnType<typeof setTimeout>;
    async function refresh(){
      try{
        const [catalog,outputs]=await Promise.all([api.get("/products"),api.get("/library/outputs?status=pending")]);
        const records=await Promise.all(catalog.items.map(async(p:any)=>{
          const items=await api.get("/products/"+encodeURIComponent(p.id)+"/runs");
          return items.map((run:any)=>({...run,product_name:p.name}));
        }));
        if(stopped)return;
        setProducts(catalog.items);setPending(outputs.items);
        setRuns(records.flat().filter(r=>["image_generation","video_generation"].includes(r.workflow_type)).sort((a,b)=>b.created_at.localeCompare(a.created_at)));
        setError(null);
      }catch(err){if(!stopped)setError(err)}
      finally{if(!stopped){setLoading(false);timer=setTimeout(refresh,5000)}}
    }
    void refresh();
    return ()=>{stopped=true;clearTimeout(timer)};
  },[]);
  return {products,runs,pending,loading,error};
}
