from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, TabbedContent, TabPane, Static, Button, Log
from textual.containers import Horizontal, Vertical
import subprocess
import psutil
import os

def get_service_status(service):
    result = subprocess.run(
        ["systemctl", "is-active", service],
        capture_output=True, text=True
    )
    return result.stdout.strip()

def status_indicator(service):
    status = get_service_status(service)
    if status == "active":
        return f"[green]● {service} RUNNING[/green]"
    else:
        return f"[red]● {service} DOWN[/red]"

def get_logs(service, lines=50):
    result = subprocess.run(
        ["journalctl", "-u", service, "-n", str(lines), "--no-pager"],
        capture_output=True, text=True
    )
    return result.stdout

class SystemStats(Static):
    def on_mount(self):
        self.update_stats()
        self.set_interval(3, self.update_stats)

    def update_stats(self):
        cpu = psutil.cpu_percent()
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        self.update(
            f"CPU: {cpu}%  |  "
            f"RAM: {ram.used // (1024**3)}GB / {ram.total // (1024**3)}GB ({ram.percent}%)  |  "
            f"Disk: {disk.used // (1024**3)}GB / {disk.total // (1024**3)}GB ({disk.percent}%)"
        )

class ServiceStatus(Static):
    def on_mount(self):
        self.update_services()
        self.set_interval(5, self.update_services)

    def update_services(self):
        services = ["vel", "vel-watchdog", "ollama", "docker", "cockpit.socket", "tailscaled", "sshd"]
        status_lines = [status_indicator(s) for s in services]
        self.update("\n".join(status_lines))

class ServicePane(Static):
    def __init__(self, service_name):
        super().__init__()
        self.service_name = service_name

    def compose(self):
        yield Static(id=f"{self.service_name}_status")
        with Horizontal():
            yield Button(f"Restart {self.service_name}", id=f"restart_{self.service_name}", variant="warning")
            yield Button("Refresh Logs", id=f"refresh_{self.service_name}", variant="default")
        yield Log(id=f"{self.service_name}_log")

    def on_mount(self):
        self.refresh_status()
        self.refresh_logs()
        self.set_interval(10, self.refresh_logs)
        self.set_interval(5, self.refresh_status)

    def refresh_status(self):
        self.query_one(f"#{self.service_name}_status", Static).update(
            status_indicator(self.service_name)
        )

    def refresh_logs(self):
        log = self.query_one(f"#{self.service_name}_log", Log)
        log.clear()
        log.write(get_logs(self.service_name))

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == f"restart_{self.service_name}":
            subprocess.run(["sudo", "systemctl", "restart", self.service_name])
            self.refresh_status()
            self.refresh_logs()
        elif event.button.id == f"refresh_{self.service_name}":
            self.refresh_logs()

class ScraperPane(Static):
    def compose(self):
        yield Static(id="scraper_info")
        with Horizontal():
            yield Button("Run Scraper", id="run_scraper", variant="success")
            yield Button("Run Discovery", id="run_discovery", variant="success")
            yield Button("Run Cleaner", id="run_cleaner", variant="warning")
            yield Button("Ingest Files", id="run_ingest", variant="success")
        with Horizontal():
            yield Button("Rebuild Index", id="rebuild_index", variant="warning")
            yield Button("Full Pipeline", id="full_pipeline", variant="error")
        yield Log(id="scraper_log")

    def on_mount(self):
        self.refresh_info()
        self.set_interval(30, self.refresh_info)

    def refresh_info(self):
        try:
            import pandas as pd
            import json
            df = pd.read_csv("/home/_homeos/engine-analysis/engine_specs.csv")
            engine_count = df["engine"].nunique()
            row_count = len(df)
        except:
            engine_count = 0
            row_count = 0

        try:
            import pandas as pd
            mods_df = pd.read_csv("/home/_homeos/engine-analysis/mods_specs.csv")
            mods_count = mods_df["mod"].nunique()
        except:
            mods_count = 0

        try:
            with open("/home/_homeos/engine-analysis/scraper.log") as f:
                lines = f.readlines()
            last_scrape = lines[-1].strip() if lines else "Never"
        except:
            last_scrape = "Never"

        try:
            with open("/home/_homeos/engine-analysis/cleaner.log") as f:
                lines = f.readlines()
            last_clean = lines[-1].strip() if lines else "Never"
        except:
            last_clean = "Never"

        try:
            import json
            with open("/home/_homeos/engine-analysis/index_manifest.json") as f:
                manifest = json.load(f)
            index_version = manifest.get("version", 0)
            last_built = manifest.get("last_built", "Never")
        except:
            index_version = 0
            last_built = "Never"

        self.query_one("#scraper_info", Static).update(
            f"[bold]Engines:[/bold] {engine_count}  |  "
            f"[bold]Mods:[/bold] {mods_count}  |  "
            f"[bold]Rows:[/bold] {row_count}  |  "
            f"[bold]Index v{index_version}[/bold]\n"
            f"[bold]Last scrape:[/bold] {last_scrape}\n"
            f"[bold]Last clean:[/bold] {last_clean}\n"
            f"[bold]Last built:[/bold] {last_built}\n"
        )

    def on_button_pressed(self, event: Button.Pressed):
        log = self.query_one("#scraper_log", Log)
        if event.button.id == "run_scraper":
            log.write("Running scraper...\n")
            result = subprocess.run(["python3", "/home/_homeos/engine-analysis/scraper.py"], capture_output=True, text=True)
            log.write(result.stdout)
            log.write(result.stderr)
        elif event.button.id == "run_discovery":
            log.write("Running discovery...\n")
            result = subprocess.run(["python3", "/home/_homeos/engine-analysis/discovery.py"], capture_output=True, text=True)
            log.write(result.stdout)
            log.write(result.stderr)
        elif event.button.id == "run_cleaner":
            log.write("Running cleaner...\n")
            result = subprocess.run(["python3", "/home/_homeos/engine-analysis/cleaner.py"], capture_output=True, text=True)
            log.write(result.stdout)
            log.write(result.stderr)
        elif event.button.id == "run_ingest":
            log.write("Running ingestion...\n")
            result = subprocess.run(["python3", "/home/_homeos/engine-analysis/ingest.py"], capture_output=True, text=True)
            log.write(result.stdout)
            log.write(result.stderr)
        elif event.button.id == "rebuild_index":
            log.write("Rebuilding index...\n")
            subprocess.run(["rm", "-rf", "/home/_homeos/engine-analysis/storage"])
            subprocess.run(["rm", "-f", "/home/_homeos/engine-analysis/index_manifest.json"])
            result = subprocess.run(["python3", "/home/_homeos/engine-analysis/rag.py"], capture_output=True, text=True)
            log.write(result.stdout)
            subprocess.run(["sudo", "systemctl", "restart", "vel"])
            log.write("Vel restarted.\n")
        elif event.button.id == "full_pipeline":
            log.write("Running full pipeline: backup → scrape → discover → clean → ingest → rebuild...\n")
            for script in ["backup.py", "scraper.py", "discovery.py", "cleaner.py", "ingest.py"]:
                log.write(f"Running {script}...\n")
                result = subprocess.run(["python3", f"/home/_homeos/engine-analysis/{script}"], capture_output=True, text=True)
                log.write(result.stdout)
            log.write("Rebuilding index...\n")
            subprocess.run(["rm", "-rf", "/home/_homeos/engine-analysis/storage"])
            subprocess.run(["rm", "-f", "/home/_homeos/engine-analysis/index_manifest.json"])
            result = subprocess.run(["python3", "/home/_homeos/engine-analysis/rag.py"], capture_output=True, text=True)
            log.write(result.stdout)
            subprocess.run(["sudo", "systemctl", "restart", "vel"])
            log.write("Full pipeline complete, Vel restarted.\n")
        self.refresh_info()

class QueryHistoryPane(Static):
    def compose(self):
        yield Static(id="query_stats")
        yield Button("Refresh", id="refresh_queries", variant="default")
        yield Log(id="query_log_display")

    def on_mount(self):
        self.refresh_queries()
        self.set_interval(30, self.refresh_queries)

    def refresh_queries(self):
        try:
            with open("/home/_homeos/engine-analysis/query.log") as f:
                lines = f.readlines()
            total = len(lines)
            self.query_one("#query_stats", Static).update(
                f"[bold]Total queries:[/bold] {total}"
            )
            log = self.query_one("#query_log_display", Log)
            log.clear()
            for line in lines[-50:]:
                log.write(line.strip())
        except:
            self.query_one("#query_stats", Static).update("No queries yet")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "refresh_queries":
            self.refresh_queries()

class VelFrame(App):
    CSS = """
    Screen {
        background: $surface;
    }
    SystemStats {
        height: 1;
        background: $panel;
        padding: 0 1;
    }
    ServiceStatus {
        padding: 1;
    }
    ServicePane {
        padding: 1;
    }
    ScraperPane {
        padding: 1;
    }
    QueryHistoryPane {
        padding: 1;
    }
    Button {
        margin: 1;
        min-width: 16;
    }
    Log {
        height: 25;
        border: solid $primary;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "action_refresh", "Refresh"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield SystemStats()
        with TabbedContent():
            with TabPane("Overview", id="overview"):
                yield Static("[bold]Velframe — Aveltura Control Panel[/bold]\n")
                yield ServiceStatus()
                with Horizontal():
                    yield Button("Restart Vel", id="restart_vel_all", variant="warning")
                    yield Button("Restart Ollama", id="restart_ollama_all", variant="warning")
                    yield Button("Restart All", id="restart_all", variant="error")
                    yield Button("Reset Faillock", id="reset_faillock", variant="default")
            with TabPane("Vel", id="tab_vel"):
                yield ServicePane("vel")
            with TabPane("Ollama", id="tab_ollama"):
                yield ServicePane("ollama")
            with TabPane("Watchdog", id="tab_watchdog"):
                yield ServicePane("vel-watchdog")
            with TabPane("Docker", id="tab_docker"):
                yield ServicePane("docker")
            with TabPane("Scraper", id="tab_scraper"):
                yield ScraperPane()
            with TabPane("Query History", id="tab_queries"):
                yield QueryHistoryPane()
            with TabPane("System", id="system"):
                yield Static(id="system_info")
        yield Footer()

    def on_mount(self):
        self.update_system_info()
        self.set_interval(5, self.update_system_info)

    def update_system_info(self):
        cpu_freq = psutil.cpu_freq()
        info = (
            f"[bold]CPU:[/bold] {psutil.cpu_count()} cores @ {cpu_freq.current:.0f}MHz\n"
            f"[bold]RAM:[/bold] {psutil.virtual_memory().total // (1024**3)}GB total\n"
            f"[bold]Swap:[/bold] {psutil.swap_memory().total // (1024**3)}GB total\n"
            f"[bold]Uptime:[/bold] {subprocess.run(['uptime', '-p'], capture_output=True, text=True).stdout.strip()}\n"
        )
        self.query_one("#system_info", Static).update(info)

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "restart_vel_all":
            subprocess.run(["sudo", "systemctl", "restart", "vel"])
        elif event.button.id == "restart_ollama_all":
            subprocess.run(["sudo", "systemctl", "restart", "ollama"])
        elif event.button.id == "restart_all":
            for service in ["ollama", "vel", "vel-watchdog"]:
                subprocess.run(["sudo", "systemctl", "restart", service])
        elif event.button.id == "reset_faillock":
            subprocess.run(["sudo", "faillock", "--user", "_homeos", "--reset"])

    def action_refresh(self):
        self.update_system_info()

if __name__ == "__main__":
    app = VelFrame()
    app.run()
