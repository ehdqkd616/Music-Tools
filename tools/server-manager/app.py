"""Studio 서버 관리 GUI.

docker compose 스택(postgres/redis/minio/api/worker-*/web)을 버튼 클릭으로
시작·중지·재시작하고, 서비스별 상태와 실시간 로그를 한 창에서 확인한다.
표준 라이브러리(tkinter)만 사용 — 추가 설치 없이 `pythonw app.py`로 바로 실행된다.
"""

import json
import queue
import subprocess
import sys
import threading
import webbrowser
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, ttk
import tkinter as tk

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CREATIONFLAGS = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
WEB_URL = "http://localhost:3000"

STATE_KR = {
    "running": "실행 중",
    "exited": "중지됨",
    "created": "생성됨(중지)",
    "restarting": "재시작 중",
    "paused": "일시정지",
    "dead": "오류",
    "removing": "제거 중",
}

STATE_TAG = {
    "running": "running",
    "restarting": "restarting",
}


def run_compose(*args, timeout=None):
    """`docker compose <args>`를 동기 실행하고 (returncode, 합쳐진 출력)을 반환."""
    cmd = ["docker", "compose", *args]
    try:
        proc = subprocess.run(
            cmd,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=CREATIONFLAGS,
        )
        output = (proc.stdout or "") + (proc.stderr or "")
        return proc.returncode, output
    except FileNotFoundError:
        return 1, "docker 명령을 찾을 수 없습니다. Docker Desktop이 설치되어 있는지 확인하세요.\n"
    except subprocess.TimeoutExpired:
        return 1, "명령 실행이 시간 초과되었습니다.\n"


class ServerManager(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Studio 서버 관리")
        self.geometry("1000x700")
        self.minsize(780, 540)

        self.log_queue: queue.Queue[str] = queue.Queue()
        self.log_proc: subprocess.Popen | None = None
        self.services: list[str] = []
        self.selected_service: str | None = None
        self.global_buttons: list[ttk.Button] = []
        self.per_service_buttons: list[ttk.Button] = []

        self._build_style()
        self._build_ui()

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(100, self._poll_log_queue)
        self.refresh_status()
        self._start_log_stream("전체")
        self.after(5000, self._auto_refresh)

    # ---------------------------------------------------------- UI 구성
    def _build_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Treeview", rowheight=26, font=("맑은 고딕", 10))
        style.configure("Treeview.Heading", font=("맑은 고딕", 10, "bold"))
        style.configure("TButton", padding=6)

    def _build_ui(self):
        root_pad = ttk.Frame(self, padding=10)
        root_pad.pack(fill="both", expand=True)

        # --- 상단: 전체 제어 버튼 ---
        top = ttk.LabelFrame(root_pad, text="전체 제어", padding=8)
        top.pack(fill="x", pady=(0, 8))

        def add_global(label, command):
            b = ttk.Button(top, text=label, command=command)
            b.pack(side="left", padx=4)
            self.global_buttons.append(b)
            return b

        add_global("▶ 전체 시작", self.on_start_all)
        add_global("⏹ 전체 중지", self.on_stop_all)
        add_global("🔨 이미지 빌드", self.on_build_all)
        add_global("🔄 상태 새로고침", self.refresh_status)
        add_global("🗑 컨테이너 삭제", self.on_down_all)
        ttk.Separator(top, orient="vertical").pack(side="left", fill="y", padx=6)
        add_global("🌐 브라우저 열기", self.on_open_browser)

        self.status_var = tk.StringVar(value="준비됨")
        ttk.Label(top, textvariable=self.status_var, foreground="#2563eb").pack(side="left", padx=12)

        self.last_refresh_var = tk.StringVar(value="")
        ttk.Label(root_pad, textvariable=self.last_refresh_var, foreground="#6b7280").pack(
            anchor="e", pady=(0, 4)
        )

        # --- 중단: 서비스 상태 테이블 ---
        mid = ttk.LabelFrame(root_pad, text="서비스 상태", padding=8)
        mid.pack(fill="both", expand=False, pady=(0, 8))

        columns = ("service", "status", "container", "detail")
        self.tree = ttk.Treeview(mid, columns=columns, show="headings", height=8, selectmode="browse")
        headings = {"service": "서비스", "status": "상태", "container": "컨테이너", "detail": "세부정보"}
        widths = {"service": 160, "status": 110, "container": 220, "detail": 300}
        for col in columns:
            self.tree.heading(col, text=headings[col])
            self.tree.column(col, width=widths[col], anchor="w")
        self.tree.tag_configure("running", foreground="#16a34a")
        self.tree.tag_configure("stopped", foreground="#6b7280")
        self.tree.tag_configure("notcreated", foreground="#9ca3af")
        self.tree.tag_configure("restarting", foreground="#d97706")
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        tree_scroll = ttk.Scrollbar(mid, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="left", fill="y")

        side = ttk.Frame(mid, padding=(10, 0))
        side.pack(side="left", fill="y")
        self.selected_label_var = tk.StringVar(value="선택된 서비스 없음")
        ttk.Label(side, textvariable=self.selected_label_var, wraplength=140).pack(anchor="w", pady=(0, 8))

        def add_per_service(label, command):
            b = ttk.Button(side, text=label, command=command, width=16)
            b.pack(anchor="w", pady=2)
            b.state(["disabled"])
            self.per_service_buttons.append(b)
            return b

        add_per_service("시작", self.on_start_selected)
        add_per_service("중지", self.on_stop_selected)
        add_per_service("재시작", self.on_restart_selected)
        add_per_service("로그 보기", self.on_view_selected_logs)

        # --- 하단: 로그 뷰어 ---
        bottom = ttk.LabelFrame(root_pad, text="로그", padding=8)
        bottom.pack(fill="both", expand=True)

        controls = ttk.Frame(bottom)
        controls.pack(fill="x", pady=(0, 6))
        ttk.Label(controls, text="로그 대상:").pack(side="left")
        self.log_target_var = tk.StringVar(value="전체")
        self.log_target_combo = ttk.Combobox(
            controls, textvariable=self.log_target_var, state="readonly", width=24, values=["전체"]
        )
        self.log_target_combo.pack(side="left", padx=6)
        self.log_target_combo.bind("<<ComboboxSelected>>", self._on_log_target_change)

        self.autoscroll_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(controls, text="자동 스크롤", variable=self.autoscroll_var).pack(
            side="left", padx=12
        )
        ttk.Button(controls, text="지우기", command=self._clear_log).pack(side="left", padx=4)

        text_frame = ttk.Frame(bottom)
        text_frame.pack(fill="both", expand=True)
        self.log_text = tk.Text(
            text_frame, state="disabled", wrap="none", font=("Consolas", 9), background="#0f1115",
            foreground="#e5e7eb", insertbackground="#e5e7eb",
        )
        self.log_text.tag_configure("err", foreground="#f87171")
        self.log_text.tag_configure("warn", foreground="#fbbf24")
        log_scroll_y = ttk.Scrollbar(text_frame, orient="vertical", command=self.log_text.yview)
        log_scroll_x = ttk.Scrollbar(bottom, orient="horizontal", command=self.log_text.xview)
        self.log_text.configure(yscrollcommand=log_scroll_y.set, xscrollcommand=log_scroll_x.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        log_scroll_y.pack(side="left", fill="y")
        log_scroll_x.pack(fill="x")

    # ---------------------------------------------------------- 선택 처리
    def _on_select(self, _event=None):
        sel = self.tree.selection()
        if not sel or sel[0] not in self.services:
            self.selected_service = None
            self.selected_label_var.set("선택된 서비스 없음")
            for b in self.per_service_buttons:
                b.state(["disabled"])
            return
        self.selected_service = sel[0]
        self.selected_label_var.set(f"선택됨: {self.selected_service}")
        for b in self.per_service_buttons:
            b.state(["!disabled"])

    # ---------------------------------------------------------- 버튼 핸들러
    def on_start_all(self):
        self._run_action_async(["up", "-d"], "전체 시작")

    def on_stop_all(self):
        self._run_action_async(["stop"], "전체 중지")

    def on_build_all(self):
        self._run_action_async(["build"], "이미지 빌드", timeout=1800)

    def on_down_all(self):
        if not messagebox.askyesno(
            "확인",
            "컨테이너와 네트워크를 삭제합니다 (볼륨/DB 데이터는 유지됩니다). 계속할까요?",
        ):
            return
        self._run_action_async(["down"], "컨테이너 삭제")

    def on_start_selected(self):
        if self.selected_service:
            self._run_action_async(["start", self.selected_service], f"{self.selected_service} 시작")

    def on_stop_selected(self):
        if self.selected_service:
            self._run_action_async(["stop", self.selected_service], f"{self.selected_service} 중지")

    def on_restart_selected(self):
        if self.selected_service:
            self._run_action_async(["restart", self.selected_service], f"{self.selected_service} 재시작")

    def on_view_selected_logs(self):
        if self.selected_service:
            self.log_target_var.set(self.selected_service)
            self._start_log_stream(self.selected_service)

    def on_open_browser(self):
        webbrowser.open(WEB_URL)
        self.status_var.set(f"브라우저에서 {WEB_URL} 열기 요청함")

    # ---------------------------------------------------------- 액션 실행
    def _set_busy(self, busy: bool, description: str | None = None):
        state = ["disabled"] if busy else ["!disabled"]
        for b in self.global_buttons:
            b.state(state)
        if busy:
            for b in self.per_service_buttons:
                b.state(["disabled"])
            self.status_var.set(f"작업 중: {description}...")
        else:
            self._on_select()  # 선택 상태에 맞게 per-service 버튼 복원

    def _run_action_async(self, args, description, timeout=600):
        self._append_log_lines([f"\n=== {description} 실행: docker compose {' '.join(args)} ===\n"])
        self._set_busy(True, description)

        def worker():
            code, output = run_compose(*args, timeout=timeout)
            self.log_queue.put(output)
            self.after(0, lambda: self._action_done(code, description))

        threading.Thread(target=worker, daemon=True).start()

    def _action_done(self, code, description):
        self._set_busy(False)
        if code == 0:
            self.status_var.set(f"{description} 완료")
        else:
            self.status_var.set(f"{description} 실패 (코드 {code})")
            messagebox.showerror("오류", f"{description} 중 오류가 발생했습니다. 로그 창을 확인하세요.")
        self.refresh_status()

    # ---------------------------------------------------------- 상태 새로고침
    def refresh_status(self):
        def worker():
            code1, services_out = run_compose("config", "--services", timeout=15)
            services = [s.strip() for s in services_out.splitlines() if s.strip()] if code1 == 0 else []

            code2, ps_out = run_compose("ps", "--all", "--format", "json", timeout=15)
            rows = {}
            if code2 == 0:
                for line in ps_out.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                        rows[obj.get("Service")] = obj
                    except json.JSONDecodeError:
                        continue
            self.after(0, lambda: self._update_table(services, rows, code1, code2))

        threading.Thread(target=worker, daemon=True).start()

    def _update_table(self, services, rows, code1, code2):
        if code1 != 0 or code2 != 0:
            self.status_var.set("Docker 상태를 가져오지 못했습니다 — Docker Desktop이 실행 중인지 확인하세요.")

        self.services = services
        values = ["전체"] + services
        self.log_target_combo["values"] = values
        if self.log_target_var.get() not in values:
            self.log_target_var.set("전체")

        selected = self.tree.selection()
        self.tree.delete(*self.tree.get_children())
        for svc in services:
            info = rows.get(svc)
            if info:
                state = info.get("State", "")
                status_kr = STATE_KR.get(state, state or "알 수 없음")
                name = info.get("Name", "-")
                detail = info.get("Status", "-")
                tag = STATE_TAG.get(state, "stopped")
            else:
                status_kr, name, detail, tag = "생성 안 됨", "-", "-", "notcreated"
            self.tree.insert("", "end", iid=svc, values=(svc, status_kr, name, detail), tags=(tag,))

        if selected and selected[0] in services:
            self.tree.selection_set(selected[0])
        self._on_select()
        self.last_refresh_var.set(f"마지막 새로고침: {datetime.now().strftime('%H:%M:%S')}")

    def _auto_refresh(self):
        self.refresh_status()
        self.after(5000, self._auto_refresh)

    # ---------------------------------------------------------- 로그 스트리밍
    def _start_log_stream(self, target: str):
        self._stop_log_stream()
        args = ["logs", "-f", "--tail", "200"]
        if target != "전체":
            args.append(target)
        cmd = ["docker", "compose", *args]
        try:
            self.log_proc = subprocess.Popen(
                cmd,
                cwd=PROJECT_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=CREATIONFLAGS,
            )
        except FileNotFoundError:
            self._append_log_lines(["docker 명령을 찾을 수 없습니다.\n"])
            return

        self._append_log_lines([f"\n=== 로그 스트리밍 시작: {target} ===\n"])
        proc = self.log_proc

        def reader():
            try:
                for line in proc.stdout:
                    self.log_queue.put(line)
            except Exception:
                pass

        threading.Thread(target=reader, daemon=True).start()

    def _stop_log_stream(self):
        if self.log_proc and self.log_proc.poll() is None:
            try:
                self.log_proc.terminate()
            except Exception:
                pass
        self.log_proc = None

    def _on_log_target_change(self, _event=None):
        self._start_log_stream(self.log_target_var.get())

    def _poll_log_queue(self):
        drained = []
        try:
            while True:
                drained.append(self.log_queue.get_nowait())
        except queue.Empty:
            pass
        if drained:
            self._append_log_lines(drained)
        self.after(100, self._poll_log_queue)

    def _append_log_lines(self, lines):
        self.log_text.configure(state="normal")
        for line in lines:
            lower = line.lower()
            if "error" in lower or "traceback" in lower:
                self.log_text.insert("end", line, ("err",))
            elif "warn" in lower:
                self.log_text.insert("end", line, ("warn",))
            else:
                self.log_text.insert("end", line)

        total_lines = int(self.log_text.index("end-1c").split(".")[0])
        if total_lines > 4000:
            self.log_text.delete("1.0", f"{total_lines - 3000}.0")

        if self.autoscroll_var.get():
            self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _clear_log(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    # ---------------------------------------------------------- 종료
    def _on_close(self):
        self._stop_log_stream()
        self.destroy()


if __name__ == "__main__":
    ServerManager().mainloop()
