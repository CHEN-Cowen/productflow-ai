import {useWorkspaceFeed,runLabel,runProgress} from "../workspace";
import {Badge,Empty,ErrorBox,Loading,Section,Stat,statusTone} from "../ui";
import {productPath} from "../router";
import {statusLabel} from "../api";
export default function Dashboard(){
  const {products,runs,pending,loading,error}=useWorkspaceFeed();
  if(loading)return <Loading/>;
  if(error)return <ErrorBox error={error}/>;
  const incomplete=products.filter(p=>p.status!=="confirmed"),failed=runs.filter(r=>r.status==="failed");
  return <>
    <div className="topbar"><h1>工作台</h1></div>
    <div className="grid four"><Stat label="待审核内容" value={pending.length}/><Stat label="最近任务 · 生产中" value={runs.filter(r=>r.status==="running").length}/><Stat label="最近任务 · 异常" value={failed.length}/><Stat label="待确认商品" value={incomplete.length}/></div>
    <div className="grid dashboard-grid mt">
      <Section title="最近任务进度" actions={<a className="btn btn-small btn-ghost" href="#/tasks">查看任务</a>}>
        {!runs.length?<Empty title="暂无生产任务"/>:runs.slice(0,5).map(run=>{
          const p=runProgress(run);
          return <div className="list-row" key={run.id}><div className="task-symbol" aria-hidden="true">{run.workflow_type==="video_generation"?"▷":"▧"}</div><div className="grow"><h3>{run.product_name} · {runLabel(run.workflow_type)}</h3><progress className="task-progress" max={p.total||1} value={p.done} aria-label={p.done+"/"+p.total+" 步完成"}/><span className="muted">{p.done}/{p.total} 步</span></div><Badge tone={statusTone(run.status)}>{statusLabel(run.status)}</Badge><a className="btn btn-small btn-ghost" href={"#"+productPath(run.product_id,"production")}>详情</a></div>;
        })}
      </Section>
      <Section title="我的待办">
        {pending.length>0&&<div className="list-row"><div className="grow"><h3>审核待交付内容</h3><Badge tone="warn">{pending.length} 项待审核</Badge></div><a className="btn btn-small btn-ghost" href="#/reviews">去审核</a></div>}
        {failed.length>0&&<div className="list-row"><div className="grow"><h3>处理生产异常</h3><Badge tone="warn">{failed.length} 项异常记录</Badge></div><a className="btn btn-small btn-ghost" href="#/tasks?status=failed">查看异常</a></div>}
        {incomplete.length>0&&<div className="list-row"><div className="grow"><h3>确认商品资料</h3><Badge tone="warn">{incomplete.length} 件待确认</Badge></div><a className="btn btn-small btn-ghost" href="#/products?view=quality">查看商品</a></div>}
        {!pending.length&&!failed.length&&!incomplete.length&&<Empty title="待办已全部处理"/>}
      </Section>
    </div>
  </>;
}
