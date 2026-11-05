"""ZX7 Studio native desktop for the independently running creative BODY.

This is not an AI filmmaking model and contains no film templates, genres,
forced effects, code execution, or long Markdown instructions. It talks ONLY
to the operator-owned loopback production service. The artist (human or AI)
still chooses the Film IR, assets, edit operations and visual direction.

Requires Tkinter (the platform's standard desktop GUI). Works with the
existing Python body client and saved authenticated local service token.
"""
from __future__ import annotations

import argparse
import json
import os
import queue
import re
import stat
import threading
from pathlib import Path

from .body_client import ZX7BodyClient


def private_operator_token(path=None,*,environ=None):
    env=os.environ if environ is None else environ
    token=env.get("ZX7_BODY_API_TOKEN")
    if isinstance(token,str) and len(token)>=32:
        return token
    private=Path(path) if path is not None else Path.home()/".config"/"zx7-studio"/"body.env"
    if private.is_symlink() or not private.is_file():
        raise ValueError("ZX7's operator-authenticated local service has no private token")
    if stat.S_IMODE(private.stat().st_mode)&0o077:
        raise PermissionError("Operator's local body secret is not private (requires chmod 600)")
    lines=private.read_text(encoding="ascii").splitlines()
    if len(lines)!=1 or not re.fullmatch(r"ZX7_BODY_API_TOKEN=[A-Za-z0-9_-]{32,128}",lines[0]):
        raise ValueError("Invalid independently configured studio secret file")
    return lines[0].split("=",1)[1]


def compact_tool_status(raw):
    if not isinstance(raw,dict):
        raise ValueError("Service did not return real creative tools")
    result=raw.get("tools")
    if not isinstance(result,list):
        raise ValueError("Original body service returned invalid tool inventory")
    lines=[]
    for item in result:
        if not isinstance(item,dict):
            raise ValueError("Malformed actual installed tool descriptor")
        identity=item.get("tool_id")
        if not isinstance(identity,str):
            raise ValueError("Tool has no trustworthy identity")
        status=item.get("status","unknown")
        capability=item.get("capability","")
        lines.append(f"{identity} | {status} | {capability}")
    return lines


def compact_job_status(item):
    if not isinstance(item,dict):
        raise ValueError("Malformed original production job")
    identifier=item.get("job_id")
    status=item.get("status")
    if not isinstance(identifier,str) or not isinstance(status,str):
        raise ValueError("No persisted physical job identity/status")
    return f"{identifier} | {status} | {item.get('workspace_id','')}"


class IndependentStudioDesktop:
    def __init__(self,window,client):
        import tkinter as tk
        from tkinter import ttk
        self.window=window
        self.client=client
        self.tk=tk
        self.ttk=ttk
        self.queue=queue.Queue()
        self.pending=0
        self.current_job=None
        self._jobs=[]
        self._artifacts=[]
        self._artifact_job=None
        self._closed=False
        self.window.protocol("WM_DELETE_WINDOW",self.close)
        self.window.title("ZX7 Studio — Independent Creative Body")
        self.window.geometry("1050x760")
        self.window.minsize(840,680)
        root=ttk.Frame(window,padding=12)
        root.pack(fill="both",expand=True)

        ttk.Label(root,text="ZX7 Studio | Local Production Body",
                  font=("TkDefaultFont",15,"bold")).pack(anchor="w",pady=(0,8))
        ttk.Label(root,text="Original films, trusted tools and real verified outputs. No cloud or subscription required.",wraplength=800).pack(anchor="w")
        self.status_text=tk.StringVar(value="Checking local body service…")
        ttk.Label(root,textvariable=self.status_text,wraplength=800).pack(side="bottom",fill="x",pady=(6,0))
        tabs=ttk.Notebook(root)
        tabs.pack(fill="both",expand=True,pady=10)
        self.diagnostics_page=ttk.Frame(tabs,padding=12)
        self.jobs_page=ttk.Frame(tabs,padding=12)
        self.tools_page=ttk.Frame(tabs,padding=12)
        self.assets_page=ttk.Frame(tabs,padding=12)
        tabs.add(self.diagnostics_page,text="System Diagnostics")
        tabs.add(self.jobs_page,text="Projects & Jobs")
        tabs.add(self.tools_page,text="Real Installed Tools")
        tabs.add(self.assets_page,text="Original Media")

        ttk.Label(self.diagnostics_page,text="Actual capabilities · model / BODY isolation",
                  font=("TkDefaultFont",13,"bold")).pack(anchor="w")
        ttk.Label(self.diagnostics_page,
                  text="No unverified global AI power score. Installed tools are not proven edits; "
                       "model creative skill requires independent trials.",
                  wraplength=800).pack(anchor="w",pady=5)
        self.diagnostic_summary=tk.StringVar(
            value="Measuring genuine local host state (not a benchmark)…")
        ttk.Label(self.diagnostics_page,textvariable=self.diagnostic_summary,
                  wraplength=800).pack(anchor="w",pady=8)
        ttk.Button(self.diagnostics_page,text="Refresh Actual Measurements",
                   command=self.refresh_diagnostics).pack(anchor="w",pady=(0,8))
        self.model_audition_button=ttk.Button(
            self.diagnostics_page,text="Test Local Model Tool-Use (3 cases)",
            command=self.start_model_audition)
        self.model_audition_button.pack(anchor="w",pady=(0,8))
        self.model_audition_button.state(["disabled"])
        columns=("family","installed","needs_setup")
        self.diagnostics_tree=ttk.Treeview(self.diagnostics_page,columns=columns,
                                            show="headings",height=10)
        for key,title,width in (("family","Capability family",340),
                                ("installed","Installed operations",145),
                                ("needs_setup","Needs setup",130)):
            self.diagnostics_tree.heading(key,text=title)
            self.diagnostics_tree.column(key,width=width,stretch=(key=="family"))
        self.diagnostics_tree.pack(fill="both",expand=True)
        ttk.Label(self.diagnostics_page,text="Evidence and next checks").pack(
            anchor="w",pady=(8,0))
        self.diagnostic_issues=tk.Text(self.diagnostics_page,height=6,
                                        wrap="word",state="disabled")
        self.diagnostic_issues.pack(fill="both",expand=True,pady=5)

        submit=ttk.LabelFrame(self.jobs_page,text="Submit the artist's original Film IR",padding=12)
        submit.pack(fill="x")
        ttk.Label(submit,text="Workspace ID:").grid(row=0,column=0,sticky="w")
        self.workspace=tk.StringVar(value="original-film")
        ttk.Entry(submit,textvariable=self.workspace,width=36).grid(row=0,column=1,sticky="w",padx=8)
        ttk.Label(submit,text="Original film plan JSON:").grid(row=1,column=0,sticky="w",pady=5)
        self.film_plan=tk.StringVar()
        ttk.Entry(submit,textvariable=self.film_plan,width=70).grid(row=1,column=1,pady=5,padx=8,sticky="ew")
        ttk.Button(submit,text="Choose...",command=self.choose_plan).grid(row=1,column=2,padx=6)
        ttk.Button(submit,text="Submit Film",command=self.submit).grid(row=2,column=1,sticky="w",pady=6)
        submit.columnconfigure(1,weight=1)

        review=ttk.LabelFrame(self.jobs_page,text="Saved project history",padding=10)
        review.pack(fill="both",expand=True,pady=12)
        controls=ttk.Frame(review);controls.pack(fill="x")
        ttk.Button(controls,text="Refresh Jobs",command=self.refresh_jobs).pack(side="left")
        ttk.Button(controls,text="Review Selected Job",command=self.inspect_job).pack(side="left",padx=6)
        ttk.Button(controls,text="Retry Unchanged Work",command=self.retry).pack(side="left",padx=6)
        ttk.Button(controls,text="Pause",command=lambda:self.control("pause")).pack(side="left",padx=3)
        ttk.Button(controls,text="Resume",command=lambda:self.control("resume")).pack(side="left",padx=3)
        ttk.Button(controls,text="Cancel",command=lambda:self.control("cancel")).pack(side="left",padx=3)
        self.job_list=tk.Listbox(review,height=4,exportselection=False)
        self.job_list.pack(fill="both",expand=True,pady=6)
        self.job_list.bind("<<ListboxSelect>>",lambda event:self._selected_job())
        self.job_detail=tk.Text(review,height=5,wrap="word")
        self.job_detail.pack(fill="both",expand=True)
        ttk.Button(review,text="List Selected Job's Actual Media",command=self.load_artifacts).pack(anchor="w",pady=5)
        self.artifact_list=tk.Listbox(review,height=3,exportselection=False)
        self.artifact_list.pack(fill="x")
        self.download_button=ttk.Button(review,text="Download Selected Real File",command=self.download)
        self.download_button.pack(anchor="w",pady=6)

        tool_area=ttk.Frame(self.tools_page)
        tool_area.pack(fill="both",expand=True)
        ttk.Button(tool_area,text="Check Real Tool Capabilities",command=self.refresh_tools).pack(anchor="w")
        self.tools_list=tk.Listbox(tool_area,height=17)
        self.tools_list.pack(fill="both",expand=True,pady=8)
        self.tools_list.bind("<<ListboxSelect>>",lambda event:self.inspect_tool())
        self.tool_detail=tk.Text(tool_area,height=13,wrap="word")
        self.tool_detail.pack(fill="both",expand=True)

        evidence=ttk.LabelFrame(self.assets_page,text="Import original, licensed media",padding=12)
        evidence.pack(fill="x")
        ttk.Label(evidence,text="Workspace ID:").grid(row=0,column=0,sticky="w")
        self.asset_workspace=tk.StringVar(value="original-film")
        ttk.Entry(evidence,textvariable=self.asset_workspace,width=30).grid(row=0,column=1)
        ttk.Label(evidence,text="Original image, video, 3D asset or sound:").grid(row=1,column=0,sticky="w")
        self.asset_path=tk.StringVar()
        ttk.Entry(evidence,textvariable=self.asset_path,width=50).grid(row=1,column=1)
        ttk.Button(evidence,text="Browse...",command=self.choose_asset).grid(row=1,column=2)
        ttk.Label(evidence,text="Your actual source ID:").grid(row=2,column=0,sticky="w")
        self.asset_source_id=tk.StringVar()
        ttk.Entry(evidence,textvariable=self.asset_source_id,width=45).grid(row=2,column=1)
        ttk.Label(evidence,text="Evidence that you own/license it:").grid(row=3,column=0,sticky="w")
        self.rights=tk.StringVar()
        ttk.Entry(evidence,textvariable=self.rights,width=70).grid(row=3,column=1)
        ttk.Button(evidence,text="Verify and Import",command=self.upload).grid(row=4,column=1,sticky="w",pady=8)

        self.window.after(100,self._pump)
        self.refresh_diagnostics()
        self.refresh_jobs()
        self.refresh_tools()

    def _run(self,description,action,done):
        self.pending+=1
        self.status_text.set(description)
        def worker():
            try:
                value=action()
            except BaseException as exc:
                self.queue.put((done,None,type(exc).__name__+": "+str(exc)))
            else:self.queue.put((done,value,None))
        threading.Thread(target=worker,daemon=True).start()

    def _pump(self):
        if self._closed:return
        from tkinter import messagebox
        while True:
            try:callback,result,error=self.queue.get_nowait()
            except queue.Empty:break
            self.pending-=1
            if error:
                self.status_text.set(error)
                messagebox.showerror("ZX7 Body operation could not complete",error)
            else:
                try:callback(result)
                except (TypeError,ValueError,KeyError) as exc:
                    self.status_text.set(str(exc))
                else:self.status_text.set("Real local studio result received.")
        if not self._closed:self.window.after(100,self._pump)

    def close(self):
        self._closed=True
        self.window.destroy()

    def _display(self,widget,data):
        widget.delete("1.0","end")
        widget.insert("1.0",json.dumps(data,ensure_ascii=False,indent=2))

    def start_model_audition(self):
        from tkinter import messagebox
        if not messagebox.askyesno("Run real local model checks",
              "Run three bounded local model inference tests? "
              "This uses host CPU but NEVER executes a creative BODY tool "
              "or claims artistic competence."):
            return
        def done(record):
            self.diagnostic_summary.set(
                "Local tool-use audition queued: "+record["run_id"]+
                ". Refresh actual measurements to inspect receipts.")
            self.refresh_diagnostics()
        self._run("Starting explicit, no-tool-mutation model diagnostic…",
                  self.client.start_model_audition,done)

    def refresh_diagnostics(self):
        """Show only factual host receipts, not estimated creative ability."""
        def done(report):
            if not isinstance(report,dict) or report.get("schema")!=1:
                raise ValueError("Service returned an unknown diagnostic contract")
            body=report["body"];model=report["model"]
            self.model_audition_button.state(
                ["!disabled"] if model["configured"] else ["disabled"])
            jobs=report["jobs"];comparisons=report["controlled_comparisons"]
            trace=report.get("execution_traces",{})
            aptitude=model.get("operator_initiated_tool_audition",{})
            counts=jobs.get("by_state",{})
            failed=counts.get("blocked",0)+counts.get("failed",0)
            self.diagnostic_summary.set(
                f"BODY {body['installed_operations']} installed operations / "
                f"{body['capability_families']} families · "
                f"Model: {'configured' if model['configured'] else 'not configured'} "
                f"(creative ability {model['independent_creativity']}) · "
                f"Blocked/failed jobs: {failed} · "
                f"Verified control comparisons: {comparisons['observed_pairs']} · "
                f"Durable stage events: {trace.get('observed_event_count',0)} · "
                f"Model tool audition: {aptitude.get('status','unmeasured')}")
            for item in self.diagnostics_tree.get_children():
                self.diagnostics_tree.delete(item)
            for family in body.get("capabilities",[]):
                self.diagnostics_tree.insert("","end",values=(
                    family["name"], family["installed_operations"],
                    family["needs_setup_operations"]))
            lines=[]
            if aptitude.get("summary"):
                stats=aptitude["summary"]
                lines.append(
                    f"LOCAL MODEL TOOL CONTRACTS: "
                    f"{stats['matching_tool_and_schema_count']}/"
                    f"{stats['evaluated_case_count']} tested cases matched; "
                    "creative quality NOT measured.")
            for issue in report.get("diagnostics",[])[:30]:
                lines.append(f"{issue['layer']}: {issue['code']} — "
                             f"{issue.get('next_check','Inspect recorded evidence')}")
            for event in trace.get("recent_events",[])[:12]:
                lines.append(f"STAGE {event['phase']}: {event['outcome']} "
                             f"[{event['capability_id']}] — {event['code']}")
            for issue in report.get("unresolved",[]):
                lines.append("UNMEASURED: "+str(issue))
            self.diagnostic_issues.configure(state="normal")
            self.diagnostic_issues.delete("1.0","end")
            self.diagnostic_issues.insert("1.0","\n".join(lines))
            self.diagnostic_issues.configure(state="disabled")
        self._run("Reading actual local capability evidence…",
                  self.client.diagnostics,done)

    def choose_plan(self):
        from tkinter import filedialog
        selected=filedialog.askopenfilename(title="Original artist-authored Film IR",
                                            filetypes=[("Film IR JSON","*.json")])
        if selected:self.film_plan.set(selected)

    def submit(self):
        workspace=self.workspace.get().strip()
        source=self.film_plan.get().strip()
        if not source or not workspace:
            self.status_text.set("Choose an original Film IR and workspace.")
            return
        def saved(receipt):
            self.refresh_jobs()
            self.current_job=receipt["job_id"]
            self._display(self.job_detail,receipt)
        self._run("Submitting immutable original Film IR…",
                  lambda:self.client.submit(source,workspace),saved)

    def refresh_jobs(self):
        def done(raw):
            self._jobs=raw["jobs"]
            self.job_list.delete(0,"end")
            for job in self._jobs:self.job_list.insert("end",compact_job_status(job))
        self._run("Reading saved original jobs…",self.client.jobs,done)

    def _selected_job(self):
        choice=self.job_list.curselection()
        if choice and choice[0]<len(self._jobs):
            selected=self._jobs[choice[0]]["job_id"]
            if selected!=self.current_job:
                self._artifacts=[]
                self._artifact_job=None
                self.artifact_list.delete(0,"end")
            self.current_job=selected

    def inspect_job(self):
        self._selected_job()
        if self.current_job:
            job=self.current_job
            self._run("Reading factual persisted job status…",
                      lambda:self.client.status(job),
                      lambda result:self._display(self.job_detail,result))

    def retry(self):
        from tkinter import messagebox
        self._selected_job()
        if not self.current_job:
            self.status_text.set("Select a blocked/failed job.");return
        if not messagebox.askyesno("Retry original film",
           "Resume this SAME film using verified previously completed tool stages? Nothing will be reauthored."):
            return
        job=self.current_job
        self._run("Resuming previously saved original film…",
            lambda:self.client.retry(job),
            lambda result:(self._display(self.job_detail,result),self.refresh_jobs()))

    def control(self,action):
        self._selected_job()
        if not self.current_job:
            self.status_text.set("Select a saved production job.");return
        job=self.current_job
        self._run(action.capitalize()+" original production at a safe tool boundary…",
            lambda:getattr(self.client,action)(job),
            lambda result:(self._display(self.job_detail,result),self.refresh_jobs()))

    def load_artifacts(self):
        self._selected_job()
        if not self.current_job:return
        job=self.current_job
        def done(raw):
            if job!=self.current_job:return
            self._artifacts=raw["assets"]
            self._artifact_job=job
            self.artifact_list.delete(0,"end")
            for asset in self._artifacts:
                self.artifact_list.insert("end",
                     f"{asset['path']} | {asset['bytes']} bytes")
        self._run("Listing actually stored media…",
                  lambda:self.client.artifacts(job),done)

    def download(self):
        from tkinter import filedialog
        self._selected_job()
        chosen=self.artifact_list.curselection()
        if not self.current_job or not chosen or self._artifact_job!=self.current_job:return
        job=self.current_job
        relative=self._artifacts[chosen[0]]["path"]
        destination=filedialog.asksaveasfilename(initialfile=Path(relative).name)
        if destination:
            self._run("Downloading SHA-verified original media…",
                lambda:self.client.download(job,relative,destination),
                lambda x:self._display(self.job_detail,x))

    def refresh_tools(self):
        def done(raw):
            self._tools=raw["tools"]
            self.tools_list.delete(0,"end")
            for line in compact_tool_status(raw):
                self.tools_list.insert("end",line)
        self._run("Checking genuinely installed tools…",self.client.tools,done)

    def inspect_tool(self):
        chosen=self.tools_list.curselection()
        if not chosen or chosen[0]>=len(getattr(self,"_tools",[])):return
        selected=self._tools[chosen[0]]["tool_id"]
        self._run("Checking "+selected+" actual execution contract…",
                  lambda:self.client.tool(selected),
                  lambda x:self._display(self.tool_detail,x))

    def choose_asset(self):
        from tkinter import filedialog
        selected=filedialog.askopenfilename(title="Choose actual original media")
        if selected:self.asset_path.set(selected)

    def upload(self):
        import mimetypes
        source=Path(self.asset_path.get().strip())
        mime=mimetypes.guess_type(source.name)[0]
        manual={".glb":"model/gltf-binary",".svg":"image/svg+xml",
                ".bin":"application/octet-stream"}
        mime=manual.get(source.suffix.lower(),mime)
        if not mime:
            self.status_text.set("Media type is unsupported by installed body.")
            return
        workspace=self.asset_workspace.get().strip()
        source_id=self.asset_source_id.get().strip()
        evidence=self.rights.get().strip()
        def done(saved):
            self._display(self.job_detail,saved)
            self.asset_source_id.set("")
            self.rights.set("")
        self._run("Streaming and verifying original source media…",
            lambda:self.client.upload(workspace,source,
                source_id=source_id,rights_evidence=evidence,mime=mime),done)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api",default="http://127.0.0.1:8765")
    args=parser.parse_args(argv)
    try:import tkinter as tk
    except ImportError as exc:
        raise SystemExit("Your desktop Python has no Tkinter support. Install python3-tk first.") from exc
    secret=private_operator_token()
    client=ZX7BodyClient(endpoint=args.api,token=secret)
    window=tk.Tk()
    IndependentStudioDesktop(window,client)
    window.mainloop()


if __name__=="__main__":main()
