import {useState} from "react";
import {useWorkspaceFeed,runLabel,runProgress} from "../workspace";
import {formatTime,statusLabel} from "../api";
import {Badge,Empty,ErrorBox,Loading,Section,statusTone} from "../ui";
import {RunSteps} from "../components";
import {productPath} from "../router";
export default function Tasks({initialStatus=""}:{initialStatus?:string}){
  const {runs,loading,error}=useWorkspaceFeed();
  const [query,setQuery]=useState(""),[status,setStatus]=useState(initialStatus),[kind,setKind]=useState("");
  const visible=runs.filter(r=>(!status||r.status===status)&&(!kind||r.workflow_type===kind)&&(r.product_id+" "+r.product_name+" "+r.id).toLowerCase().includes(query.trim().toLowerCase()));
  return <><div className="topbar"><h1>生产任务</h1></div><Section title="最近生产记录">
    <div className="filters"><input className="filter-search" aria-label="搜索任务" placeholder="商品名称、编号或任务编号" value={query} onChange={e=>setQuery(e.target.value)}/><select aria-label="任务状态" value={status} onChange={e=>setStatus(e.target.value)}><option value="">全部状态</option><option value="running">进行中</option><option value="success">已完成</option><option value="failed">失败</option></select><select aria-label="任务类型" value={kind} onChange={e=>setKind(e.target.value)}><option value="">全部类型</option><option value="image_generation">图片</option><option value="video_generation">视频</option></select></div>
    {loading?<Loading/>:error?<ErrorBox error={error}/>:!visible.length?<Empty title="没有匹配的任务"/>:visible.map(run=>{
      const p=runProgress(run);
      return <div className="task-record" key={run.id}><div className="row gap between wrap"><div><h3>{run.product_name} · {runLabel(run.workflow_type)}</h3><span className="muted">{formatTime(run.created_at)}</span></div><Badge tone={statusTone(run.status)}>{statusLabel(run.status)}</Badge></div><progress className="task-progress" max={p.total||1} value={p.done} aria-label={p.done+"/"+p.total+" 步完成"}/><div className="row gap between"><span>{p.done}/{p.total} 步</span><a className="btn btn-small btn-ghost" href={"#"+productPath(run.product_id,"production")}>{run.status==="failed"?"查看并重新生产":"查看商品任务"}</a></div><details><summary>执行详情</summary><RunSteps run={run}/></details></div>;
    })}
    <p className="muted mt">每件商品显示最近 20 条执行记录，每 5 秒更新。</p>
  </Section></>;
}
