import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { Activity, AlertTriangle, ArrowUpRight, BadgeCheck, Building2, ChevronRight, ClipboardList, FileText, Gauge, LayoutDashboard, Menu, Package, RefreshCw, ShieldCheck, Users, X } from 'lucide-react'
import { useState } from 'react'

const nav = [
  { label: 'Overview', path: '/', icon: LayoutDashboard, group: 'Workspace' },
  { label: 'Applicants', path: '/applicants', icon: Users, group: 'Workspace' },
  { label: 'Products', path: '/products', icon: Package, group: 'Workspace' },
  { label: 'Quotes', path: '/quotes', icon: FileText, group: 'Underwriting' },
  { label: 'Review queue', path: '/underwriting', icon: ClipboardList, group: 'Underwriting' },
  { label: 'Policies', path: '/policies', icon: ShieldCheck, group: 'Policy lifecycle' },
  { label: 'Endorsements', path: '/endorsements', icon: BadgeCheck, group: 'Policy lifecycle' },
  { label: 'Renewals', path: '/renewals', icon: RefreshCw, group: 'Policy lifecycle' },
  { label: 'Anomalies', path: '/anomalies', icon: AlertTriangle, group: 'Governance' },
 
  { label: 'Documents', path: '/documents', icon: FileText, group: 'Governance' },
  { label: 'Reports', path: '/reports', icon: Gauge, group: 'Governance' },
  { label: 'Users', path: '/users', icon: Users, group: 'Administration' },
]
export default function Layout({user,onLogout}:{user:any;onLogout:()=>void}) {
  const [open, setOpen] = useState(false)
  const location = useLocation()
  const current = nav.find(n => n.path === location.pathname)?.label || 'Workspace'
  const visibleNav = nav.filter(n => user.role !== 'CUSTOMER' || n.path === '/')
  const groups = [...new Set(visibleNav.map(n => n.group))]
  return <div className="min-h-screen bg-canvas">
    {open && <button className="fixed inset-0 z-30 bg-slate-950/30 lg:hidden" onClick={() => setOpen(false)} aria-label="Close menu"/>}
    <aside className={`fixed inset-y-0 left-0 z-40 flex w-[260px] flex-col border-r border-slate-200 bg-white transition-transform lg:translate-x-0 ${open ? 'translate-x-0' : '-translate-x-full'}`}>
      <div className="flex h-[82px] items-center gap-3 border-b border-slate-100 px-6">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-navy text-white"><Building2 size={21}/></div>
        <div><p className="font-display text-[17px] font-extrabold tracking-tight text-ink">YottaFlex<span className="text-teal">.</span></p><p className="text-[10px] font-bold uppercase tracking-[.15em] text-slate-400">Underwriting suite</p></div>
        <button className="ml-auto lg:hidden" onClick={() => setOpen(false)}><X size={18}/></button>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-4 py-5" style={{ scrollbarGutter: 'stable' }}> 
        <div className="mb-3 rounded-xl bg-slate-50 p-3"><div className="flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-emerald-500"/><span className="text-xs font-semibold text-slate-700">Operations environment</span></div><p className="mt-1 pl-4 text-[10px] text-slate-400">Local API connection</p></div>
        {groups.filter(group => user.role==='ADMIN' || group!=='Administration').map(group => <div key={group} className="mb-5">
          <p className="mb-2 px-3 text-[10px] font-bold uppercase tracking-[.16em] text-slate-400">{group}</p>
          <div className="space-y-1">{visibleNav.filter(n => n.group === group && (user.role==='ADMIN' || n.label!=='Users')).map(item => { const Icon = item.icon; return <NavLink key={item.path} to={item.path} end={item.path === '/'} onClick={() => setOpen(false)} className={({isActive}) => `flex items-center gap-3 rounded-xl px-3 py-2.5 text-[13px] font-semibold transition ${isActive ? 'bg-navy text-white shadow-md shadow-navy/10' : 'text-slate-600 hover:bg-slate-50 hover:text-ink'}`}><Icon size={17}/>{item.label}{item.path === '/anomalies' && <span className="ml-auto h-1.5 w-1.5 rounded-full bg-amber-400"/>}</NavLink>})}</div>
        </div>)}
      </div>
      <div className="shrink-0 border-t border-slate-100 p-4"><div className="rounded-xl bg-[#f1f8f7] p-3"><div className="flex items-center gap-2 text-teal"><Activity size={15}/><span className="text-xs font-bold">Audit-first workflow</span></div><p className="mt-1 text-[11px] leading-5 text-slate-500">Decisions, changes and exceptions remain traceable.</p></div><p className="mt-4 text-center text-[10px] text-slate-400">YottaFlex • Internal prototype</p></div>
    </aside>
    <main className="min-h-screen lg:pl-[260px]">
      <header className="sticky top-0 z-20 flex h-[70px] items-center justify-between border-b border-slate-200/80 bg-white/90 px-5 backdrop-blur-xl sm:px-8">
        <div className="flex items-center gap-3"><button onClick={() => setOpen(true)} className="rounded-lg p-2 text-slate-500 hover:bg-slate-100 lg:hidden"><Menu size={19}/></button><div><p className="text-[11px] text-slate-400">Workspace <ChevronRight className="mx-1 inline" size={11}/><span className="font-semibold text-slate-600">{current}</span></p><p className="mt-0.5 text-sm font-bold text-ink">{current === 'Overview' ? 'Good work starts with visibility.' : `${current} management`}</p></div></div>
        <div className="flex items-center gap-3"><div className="hidden text-right sm:block"><p className="text-xs font-bold text-slate-700">{user.full_name}</p><p className="text-[10px] text-slate-400">{String(user.role).replaceAll("_"," ")}</p></div><button onClick={onLogout} className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-600">Sign out</button><div className="flex h-9 w-9 items-center justify-center rounded-full bg-[#e8f4f2] text-xs font-extrabold text-teal">{String(user.full_name||"U").split(" ").map((x:string)=>x[0]).join("").slice(0,2)}</div></div>
      </header>
      <div className="mx-auto max-w-[1500px] p-5 sm:p-8"><Outlet/></div>
      <footer className="px-8 pb-6 text-center text-[10px] text-slate-400">YottaFlex Underwriting Workspace · API-driven operational interface</footer>
    </main>
  </div>
}