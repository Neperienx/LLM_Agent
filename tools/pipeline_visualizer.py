"""Tkinter-based GUI for exploring pipeline prompts and dependencies.

This lightweight visualiser loads the JSON pipelines that power the local
agent playground and renders a simple dashboard showing how each step
relates to the others. It highlights the prompt template used in every
``llm_call`` step so that users can quickly understand which templates are
involved and how data flows between the steps.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

try:  # pragma: no cover - Tkinter is provided by the runtime, not the tests
    import tkinter as tk
    from tkinter import ttk
except ImportError as exc:  # pragma: no cover - defensive programming
    raise RuntimeError(
        "Tkinter is required to launch the pipeline visualiser but it is not "
        "available in this Python installation."
    ) from exc

from core.pipeline_loader import PipelineLoader


BASE_DIR = Path(__file__).resolve().parent.parent
PIPELINES_DIR = BASE_DIR / "pipelines"
TEMPLATES_DIR = BASE_DIR / "templates"


def _extract_dependencies(step: dict[str, Any]) -> list[str]:
    """Return a sorted list of step identifiers referenced by this step."""

    refs: set[str] = set()
    for reference in step.get("inputs", {}).values():
        target = reference.split(".", 1)[0]
        if target and target != "inputs":
            refs.add(target)
    return sorted(refs)


def _format_outputs(step: dict[str, Any]) -> str:
    outputs = step.get("outputs")
    if not outputs:
        return ""
    if isinstance(outputs, dict):
        return ", ".join(outputs.keys())
    if isinstance(outputs, Iterable) and not isinstance(outputs, (str, bytes)):
        return ", ".join(str(item) for item in outputs)
    return str(outputs)


class PipelineVisualizerApp:
    """Main Tkinter application window."""

    def __init__(self, master: tk.Tk) -> None:
        self.master = master
        self.master.title("LLM Pipeline Visualiser")
        self.master.geometry("960x640")
        self.master.minsize(820, 520)

        self.loader = PipelineLoader(base_dir=PIPELINES_DIR)
        self.pipeline_index = self.loader.list_pipelines()
        self.loaded_pipelines: dict[str, dict[str, Any]] = {}
        self.current_steps: list[dict[str, Any]] = []

        self._build_layout()
        self._populate_pipeline_list()

        if self.pipeline_list.size() > 0:
            self.pipeline_list.selection_set(0)
            self._on_pipeline_select()

    # ------------------------------------------------------------------
    # GUI construction helpers
    # ------------------------------------------------------------------
    def _build_layout(self) -> None:
        self.master.columnconfigure(1, weight=1)
        self.master.rowconfigure(0, weight=1)

        sidebar = ttk.Frame(self.master, padding=10)
        sidebar.grid(row=0, column=0, sticky="ns")
        sidebar.rowconfigure(1, weight=1)

        ttk.Label(sidebar, text="Pipelines", font=("TkDefaultFont", 11, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        self.pipeline_list = tk.Listbox(sidebar, exportselection=False, height=18)
        self.pipeline_list.grid(row=1, column=0, sticky="nsew", pady=(6, 0))
        self.pipeline_list.bind("<<ListboxSelect>>", lambda _: self._on_pipeline_select())

        main_panel = ttk.Frame(self.master, padding=10)
        main_panel.grid(row=0, column=1, sticky="nsew")
        main_panel.columnconfigure(0, weight=1)
        main_panel.rowconfigure(2, weight=1)
        main_panel.rowconfigure(3, weight=1)

        self.pipeline_title_var = tk.StringVar()
        self.pipeline_desc_var = tk.StringVar()
        self.pipeline_inputs_var = tk.StringVar()

        ttk.Label(main_panel, textvariable=self.pipeline_title_var, font=(
            "TkDefaultFont",
            13,
            "bold",
        )).grid(row=0, column=0, sticky="w")
        ttk.Label(main_panel, textvariable=self.pipeline_desc_var, wraplength=540).grid(
            row=1, column=0, sticky="w", pady=(0, 8)
        )

        ttk.Label(main_panel, text="Inputs", font=("TkDefaultFont", 10, "bold")).grid(
            row=2, column=0, sticky="w"
        )
        self.inputs_label = ttk.Label(
            main_panel,
            textvariable=self.pipeline_inputs_var,
            wraplength=540,
            justify="left",
        )
        self.inputs_label.grid(row=3, column=0, sticky="nsew")

        steps_frame = ttk.Frame(main_panel)
        steps_frame.grid(row=4, column=0, sticky="nsew", pady=(16, 6))
        steps_frame.columnconfigure(0, weight=1)
        steps_frame.rowconfigure(0, weight=1)

        ttk.Label(steps_frame, text="Steps", font=("TkDefaultFont", 10, "bold")).grid(
            row=0, column=0, sticky="w"
        )

        self.step_tree = ttk.Treeview(
            steps_frame,
            columns=("type", "details", "dependencies", "outputs"),
            show="headings",
            height=8,
        )
        self.step_tree.grid(row=1, column=0, sticky="nsew", pady=(6, 0))
        self.step_tree.heading("type", text="Type")
        self.step_tree.heading("details", text="Details")
        self.step_tree.heading("dependencies", text="Depends on")
        self.step_tree.heading("outputs", text="Outputs")
        self.step_tree.column("type", width=90, anchor="w")
        self.step_tree.column("details", width=220, anchor="w")
        self.step_tree.column("dependencies", width=150, anchor="w")
        self.step_tree.column("outputs", width=150, anchor="w")
        self.step_tree.bind("<<TreeviewSelect>>", lambda _: self._on_step_select())

        details_frame = ttk.Frame(main_panel)
        details_frame.grid(row=5, column=0, sticky="nsew")
        details_frame.columnconfigure(0, weight=1)
        details_frame.rowconfigure(1, weight=1)

        ttk.Label(details_frame, text="Step Details", font=("TkDefaultFont", 10, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        self.details_text = tk.Text(details_frame, height=12, wrap="word")
        self.details_text.grid(row=1, column=0, sticky="nsew", pady=(6, 0))
        self.details_text.configure(state=tk.DISABLED)

    def _populate_pipeline_list(self) -> None:
        self.pipeline_list.delete(0, tk.END)
        if not self.pipeline_index:
            self.pipeline_list.insert(tk.END, "No pipelines found")
            self.pipeline_list.configure(state=tk.DISABLED)
            self.pipeline_title_var.set("No pipelines are available")
            self.pipeline_desc_var.set(
                "Add JSON files to the 'pipelines/' directory to explore them here."
            )
            return

        for pipeline in self.pipeline_index:
            self.pipeline_list.insert(tk.END, pipeline["name"])

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------
    def _on_pipeline_select(self) -> None:
        if not self.pipeline_index:
            return
        selection = self.pipeline_list.curselection()
        if not selection:
            return
        index = selection[0]
        pipeline_meta = self.pipeline_index[index]
        path = pipeline_meta["path"]
        if path not in self.loaded_pipelines:
            self.loaded_pipelines[path] = self.loader.load(path)
        pipeline = self.loaded_pipelines[path]
        self.current_steps = list(pipeline.get("steps", []))

        title = pipeline.get("name", Path(path).stem)
        description = pipeline.get("description", "")
        inputs = pipeline.get("inputs", {})

        self.pipeline_title_var.set(title)
        self.pipeline_desc_var.set(description or "")
        if inputs:
            formatted_inputs = [f"• {name}: {dtype}" for name, dtype in inputs.items()]
            self.pipeline_inputs_var.set("\n".join(formatted_inputs))
        else:
            self.pipeline_inputs_var.set("(No declared inputs)")

        self._populate_steps()
        self._clear_step_details()

    def _populate_steps(self) -> None:
        for row in self.step_tree.get_children():
            self.step_tree.delete(row)

        for step in self.current_steps:
            step_id = step.get("id", "")
            step_type = step.get("type", "")
            if step_type == "llm_call":
                details = f"Prompt: {step.get('prompt', '—')}"
            elif step_type == "transform":
                details = f"Transform: {step.get('code', '—')}"
            elif step_type == "store":
                details = f"Store as: {step.get('filename', '—')}"
            else:
                details = ""

            deps = ", ".join(_extract_dependencies(step))
            outputs = _format_outputs(step)

            self.step_tree.insert(
                "",
                tk.END,
                iid=step_id,
                values=(step_type, details, deps, outputs),
            )

    def _on_step_select(self) -> None:
        selection = self.step_tree.selection()
        if not selection:
            return
        step_id = selection[0]
        step = next((s for s in self.current_steps if s.get("id") == step_id), None)
        if not step:
            return
        self._display_step_details(step)

    # ------------------------------------------------------------------
    # Rendering helpers
    # ------------------------------------------------------------------
    def _clear_step_details(self) -> None:
        self.details_text.configure(state=tk.NORMAL)
        self.details_text.delete("1.0", tk.END)
        self.details_text.configure(state=tk.DISABLED)

    def _display_step_details(self, step: dict[str, Any]) -> None:
        lines: list[str] = [f"Step ID: {step.get('id', '—')}", f"Type: {step.get('type', '—')}"]

        if step.get("type") == "llm_call":
            prompt_name = step.get("prompt")
            lines.append(f"Prompt template: {prompt_name}")
            if prompt_name:
                prompt_path = TEMPLATES_DIR / prompt_name
                if prompt_path.exists():
                    lines.append("")
                    lines.append("Prompt contents:")
                    lines.append("""----------------------------------------""")
                    lines.append(prompt_path.read_text(encoding="utf-8"))
                else:
                    lines.append("(Prompt file not found)")
        elif step.get("type") == "transform":
            lines.append(f"Python callable: {step.get('code', '—')}")
        elif step.get("type") == "store":
            lines.append(f"Filename: {step.get('filename', '—')}")
            content_key = step.get("content_key")
            if content_key:
                lines.append(f"Content key: {content_key}")

        if step.get("inputs"):
            lines.append("")
            lines.append("Inputs:")
            for key, value in step["inputs"].items():
                lines.append(f"  - {key} ← {value}")

        if step.get("outputs"):
            lines.append("")
            lines.append("Outputs:")
            for key, value in step["outputs"].items():
                lines.append(f"  - {key} → {value}")

        self.details_text.configure(state=tk.NORMAL)
        self.details_text.delete("1.0", tk.END)
        self.details_text.insert("1.0", "\n".join(lines))
        self.details_text.configure(state=tk.DISABLED)


def launch() -> None:
    """Start the pipeline visualiser GUI."""

    root = tk.Tk()
    PipelineVisualizerApp(root)
    root.mainloop()


if __name__ == "__main__":  # pragma: no cover - manual usage only
    launch()
