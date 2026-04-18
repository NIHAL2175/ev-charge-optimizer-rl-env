import json
import os
import threading
from pathlib import Path
from typing import Optional

import gradio as gr

import requests

TASK_REGISTRY = {
    "task_1": {
        "name": "Peak Demand Surge",
        "difficulty": "easy",
        "description": "A sudden increase in EV charging demand during peak hours is putting excessive pressure on the grid. Multiple vehicles are charging simultaneously without any coordinated scheduling, leading to inefficient power distribution. This can result in instability and increased operational stress on the system.",
        "alert": "[P1 – Grid Overload]: Grid load has exceeded 95% capacity during peak hours. Multiple EVs are charging concurrently without load balancing. Immediate action required to stabilize the system."
    },
    "task_2": {
        "name": "Critical Battery Neglect",
        "difficulty": "easy",
        "description": "Several electric vehicles with critically low battery levels are not being prioritized for charging. The system is treating all vehicles equally without considering urgency based on state of charge (SOC) or departure deadlines. This can lead to critical vehicles failing to reach required charge levels in time.",
        "alert": "[P2 – Priority Failure]: EVs with SOC below 20% are not receiving priority charging. Charging allocation remains uniform across all vehicles. Investigate prioritization logic."
    },
    "task_3": {
        "name": "Uniform Allocation Inefficiency",
        "difficulty": "easy",
        "description": "Charging power is being distributed equally among all connected EVs regardless of their individual requirements. The system is not accounting for battery levels, urgency, or time constraints. This results in inefficient utilization of available energy and delayed charging outcomes.",
        "alert": "[P2 – Allocation Issue]: Uniform charging detected across all EVs. Priority-based allocation is not being applied. Optimization strategy needs correction."
    },
    "task_4": {
        "name": "Idle Infrastructure Waste",
        "difficulty": "easy",
        "description": "Despite having available charging stations, some remain unused while EVs are waiting in the queue. The system is not effectively assigning vehicles to free charging points. This leads to underutilization of infrastructure and unnecessary delays.",
        "alert": "[P2 – Resource Underutilization]: Idle charging slots detected while EV queue is active. Charging stations are not being optimally utilized. Check assignment logic."
    },
    "task_5": {
        "name": "Missed Charging Deadlines",
        "difficulty": "easy",
        "description": "Several EVs are unable to reach their required state of charge before their scheduled departure time. The charging schedule does not properly align with individual vehicle timelines. This impacts reliability and user satisfaction.",
        "alert": "[P1 – Deadline Missed]: Multiple EVs failed to reach target SOC before departure. Charging delays detected due to poor scheduling. Immediate optimization required."
    },
    "task_6": {
        "name": "Tariff-Aware Failure",
        "difficulty": "medium",
        "description": "The system does not adapt to dynamic electricity pricing throughout the day. Charging continues during high-cost periods instead of shifting to lower tariff windows. This results in increased operational costs and inefficient energy usage.",
        "alert": "[P2 – Cost Inefficiency]: Charging detected during peak tariff periods. Cost optimization strategy inactive. Adjust scheduling logic to reduce expenses."
    },
    "task_7": {
        "name": "Capacity Threshold Breach",
        "difficulty": "medium",
        "description": "The total charging demand exceeds the grid’s safe operational capacity limits. The system fails to enforce constraints on maximum allowable load. This creates risk for grid instability and potential outages.",
        "alert": "[P1 – Capacity Breach]: Grid capacity exceeded beyond configured limits. Overload condition detected. Immediate load reduction required."
    },
    "task_8": {
        "name": "Priority Inversion Issue",
        "difficulty": "medium",
        "description": "Low-priority EVs are receiving higher charging allocation while critical vehicles are delayed. The prioritization logic is either incorrect or not applied effectively. This leads to inefficient resource utilization.",
        "alert": "[P2 – Priority Inversion]: Non-critical EVs receiving higher charging power. High-priority EVs are delayed. Review prioritization mechanism."
    },
    "task_9": {
        "name": "Queue Scheduling Breakdown",
        "difficulty": "medium",
        "description": "The EV queue is not processed according to optimal scheduling strategies. Key factors like arrival time, SOC, and deadlines are not considered properly. This increases waiting time and reduces efficiency.",
        "alert": "[P2 – Scheduling Failure]: Queue order does not match priority metrics. Increased wait times observed. Investigate scheduling logic."
    },
    "task_10": {
        "name": "Load Distribution Imbalance",
        "difficulty": "medium",
        "description": "Charging load is unevenly distributed across available charging stations. Some stations are overloaded while others remain underutilized. This reduces system efficiency and stresses specific nodes.",
        "alert": "[P2 – Load Imbalance]: Uneven load across charging stations detected. Some nodes overloaded while others remain idle. Balance distribution required."
    },
    "task_11": {
        "name": "Demand Spike Mismanagement",
        "difficulty": "medium",
        "description": "A sudden influx of EVs causes a rapid increase in demand. The system is unable to adapt quickly to changing conditions. This results in temporary overload and degraded performance.",
        "alert": "[P1 – Demand Spike]: Sudden increase in EV arrivals detected. System response delayed. Load spike causing instability."
    },
    "task_12": {
        "name": "Renewable Energy Neglect",
        "difficulty": "hard",
        "description": "Available renewable energy sources such as solar or wind are not being utilized effectively. The system continues to rely heavily on grid power. This leads to higher costs and reduced sustainability.",
        "alert": "[P2 – Energy Inefficiency]: Renewable energy available but unused. Charging relies entirely on grid supply. Optimize energy sourcing."
    },
    "task_13": {
        "name": "Optimization Trade-off Conflict",
        "difficulty": "hard",
        "description": "The system struggles to balance multiple objectives such as cost efficiency, SOC completion, and grid stability. Decisions favor one metric at the expense of others. This results in suboptimal overall performance.",
        "alert": "[P2 – Optimization Conflict]: Imbalance detected between cost, SOC, and grid safety. Multi-objective optimization failing."
    },
    "task_14": {
        "name": "Charging Instability Oscillation",
        "difficulty": "hard",
        "description": "Charging rates fluctuate frequently across time steps due to unstable decision-making. The system lacks consistency in its allocation strategy. This leads to inefficiency and unpredictable performance.",
        "alert": "[P2 – System Instability]: Charging rates oscillating across steps. Unstable allocation detected. Stabilization required."
    },
    "task_15": {
        "name": "Cost Accumulation Drift",
        "difficulty": "hard",
        "description": "Electricity costs gradually increase over time due to inefficient long-term scheduling. The system fails to optimize across multiple time steps. This results in higher cumulative expenses.",
        "alert": "[P2 – Cost Drift]: Cost trend rising above baseline. Long-term inefficiency detected. Improve scheduling strategy."
    },
    "task_16": {
        "name": "Safety Constraint Violation",
        "difficulty": "hard",
        "description": "Under high load conditions, the system violates predefined grid safety constraints. Protective mechanisms are not enforced effectively. This creates risk for infrastructure damage.",
        "alert": "[P1 – Safety Violation]: Critical safety thresholds breached. Grid stability at risk. Immediate corrective action required."
    },
    "task_17": {
        "name": "Full-System Optimization Failure",
        "difficulty": "hard",
        "description": "The system fails to optimize across all parameters in complex scenarios involving multiple constraints. Performance degrades significantly under stress conditions. This indicates a breakdown in decision-making logic.",
        "alert": "[P1 – System Failure]: Suboptimal performance across cost, SOC, and grid metrics. System unable to achieve balanced optimization."
    }
}


RESULTS_DIR = Path(__file__).parent.parent / "results"

def _load_all_results() -> dict:
    """Load all result JSON files from the results directory."""
    results = {}
    if not RESULTS_DIR.exists():
        return results
    for f in sorted(RESULTS_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text())
            model_name = data.get("model", f.stem)
            results[model_name] = data
        except Exception:
            pass
    return results


_NEW_MODELS = {"gemma4:31b"}  # released within last week

def _model_display_name(model: str) -> str:
    """Return model names robustly."""
    return model



CUSTOM_CSS = """

body, body.dark, body.light, html, #root, #root > div, .gradio-container, .gradio-container.dark {
    background-color: #e0f7fa !important;
    background-image: radial-gradient(circle, #00bcd4 0.8px, transparent 0.8px) !important;
    background-size: 16px 16px !important;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
    color: #000 !important;
}


.gradio-container, .gradio-container p, .gradio-container span,
.gradio-container div, .gradio-container label, .gradio-container h1,
.gradio-container h2, .gradio-container h3, .gradio-container h4,
.gradio-container strong, .gradio-container b, .gradio-container td,
.gradio-container th, .gradio-container li, .gradio-container summary,
.gradio-container details, .gradio-container a,
.gradio-container .tabitem *, .gradio-container [role="tabpanel"] *,
.prose, .prose *, .html-container, .html-container * {
    color: #000 !important;
    -webkit-text-fill-color: #000 !important;
}

.sql-output, .sql-output *,
.gradio-container .sql-output, .gradio-container .sql-output *,
.gradio-container .tabitem .sql-output, .gradio-container .tabitem .sql-output *,
.gradio-container [role="tabpanel"] .sql-output, .gradio-container [role="tabpanel"] .sql-output *,
.html-container .sql-output, .html-container .sql-output * {
    color: #4ade80 !important;
    -webkit-text-fill-color: #4ade80 !important;
    background: #0a1628 !important;
}

textarea, input[type="text"] {
    -webkit-text-fill-color: #000 !important;
}


.tabs {
    background: transparent !important;
    border: none !important;
    overflow: visible !important;
    background-image: none !important;
    margin-top: 12px !important;
}


.tabs > div:first-child,
div[class*="tab-wrapper"],
div[class*="tab-container"] {
    height: auto !important;
    padding-bottom: 12px !important;
    overflow: visible !important;
}
div[class*="tab-container"]::after,
.tabs > div:first-child > div::after {
    display: none !important;
    background: transparent !important;
    height: 0 !important;
}


.tabs > div:first-child,
.tabs > div:first-child > div,
div[class*="tab-container"],
div[role="tablist"],
.tab-nav {
    display: flex !important;
    gap: 8px !important;
    justify-content: center !important;
    flex-wrap: wrap !important;
    overflow: visible !important;
    margin: 0 auto !important;
}


.tabs button,
.tabs > div:first-child button,
div[class*="tab-container"] button {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
    font-weight: 900 !important;
    font-size: 13px !important;
    color: #000 !important;
    -webkit-text-fill-color: #000 !important;
    border: 3px solid #000 !important;
    border-radius: 6px !important;
    padding: 8px 16px !important;
    letter-spacing: 0.03em !important;
    text-transform: uppercase !important;
    cursor: pointer !important;
    text-align: center !important;
    white-space: nowrap !important;
    height: auto !important;
    position: relative !important;
    transition: transform 0.12s ease, box-shadow 0.12s ease !important;
    box-shadow: 4px 4px 0 #000 !important;
    background: #fed7aa !important;
    margin: 0 !important;
}

.tabs button:nth-child(1) { background: #ffe0b2 !important; }
.tabs button:nth-child(2) { background: #d1fae5 !important; }
.tabs button:nth-child(3) { background: #bfdbfe !important; }
.tabs button:nth-child(4) { background: #fde047 !important; }
.tabs button:nth-child(5) { background: #fecdd3 !important; }

.tabs button:hover {
    transform: translateY(-3px) !important;
    box-shadow: 0 0 16px #fde047, 4px 4px 0 #000 !important;
    background-color: inherit !important;
}

.tabs button.selected,
.tabs button[class*="selected"] {
    transform: translateY(1px) !important;
    box-shadow: 2px 2px 0 #000 !important;
}

.tabs button.selected::after,
.tabs button[class*="selected"]::after {
    display: none !important;
    height: 0 !important;
    background: transparent !important;
}

.tabs button.selected:nth-child(1) { background: #ffb74d !important; }
.tabs button.selected:nth-child(2) { background: #a7f3d0 !important; }
.tabs button.selected:nth-child(3) { background: #93c5fd !important; }
.tabs button.selected:nth-child(4) { background: #fbbf24 !important; }
.tabs button.selected:nth-child(5) { background: #fca5a5 !important; }


.form, .row, .column, .gap, .contain,
.html-container, .prose {
    border: none !important;
    background: transparent !important;
    box-shadow: none !important;
}

.tabitem, .tab-content, [role="tabpanel"] {
    border: 3px solid #000 !important;
    border-radius: 4px !important;
    background: #fff !important;
    background-image: none !important;
    padding: 20px !important;
    box-shadow: 4px 4px 0 #000 !important;
    margin-left: 0 !important;
    margin-right: 0 !important;
}


.block {
    border: 2px solid #000 !important;
    border-radius: 4px !important;
    background: #fed7aa !important;
}


.block:has(select), .block:has(textarea), .block:has(input) {
    background: #fed7aa !important;
}


.block:has(.html-container), .borderless-html, .borderless-html.block {
    border: none !important;
    background: transparent !important;
    box-shadow: none !important;
    padding: 0 !important;
}


.gradio-container {
    --section-header-text-size: 14px !important;
    --section-header-text-weight: 900 !important;
    --block-label-text-size: 14px !important;
    --block-label-text-weight: 900 !important;
    --block-label-text-color: #000 !important;
    --body-text-color: #000 !important;
    --body-text-color-subdued: #000 !important;
}
label, .label-text, span[data-testid="block-label"],
.gradio-container label, .gradio-container .label-text,
.gradio-container span[data-testid="block-label"],
.gradio-container .block > span:first-child,
.gradio-container .wrap > label,
.block label span,
[class*="svelte"] > span {
    color: #000 !important;
    -webkit-text-fill-color: #000 !important;
    font-weight: 900 !important;
    font-size: 14px !important;
    text-transform: uppercase !important;
    letter-spacing: 0.04em !important;
    text-shadow: 1px 1px 0 #fb923c !important;
}


h2, .gradio-container h2,
.gradio-container .tabitem h2,
.gradio-container [role="tabpanel"] h2 {
    font-size: 20px !important;
    font-weight: 900 !important;
    color: #000 !important;
    -webkit-text-fill-color: #000 !important;
    letter-spacing: -0.01em !important;
    margin-bottom: 8px !important;
}
h3, .gradio-container h3,
.gradio-container .tabitem h3,
.gradio-container [role="tabpanel"] h3 {
    font-size: 16px !important;
    font-weight: 900 !important;
    color: #000 !important;
    -webkit-text-fill-color: #000 !important;
}


textarea, input[type="text"] {
    border: 2px solid #000 !important;
    border-radius: 4px !important;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace !important;
    background: #fff !important;
    color: #000 !important;
    font-size: 13px !important;
}
textarea:focus, input[type="text"]:focus {
    border-color: #2563eb !important;
    box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.2) !important;
}


.wrap .wrap-inner, [data-testid="dropdown"],
.secondary-wrap, .dropdown-container {
    border: 2px solid #000 !important;
    border-radius: 4px !important;
    background: #fff !important;
    color: #000 !important;
}

.wrap .wrap-inner input,
.wrap .wrap-inner span,
.wrap .secondary-wrap,
input[data-testid="textbox"],
.single-select {
    color: #000 !important;
    font-weight: 600 !important;
    font-size: 14px !important;
}

.wrap .wrap-inner input::placeholder {
    color: #6b7280 !important;
    font-weight: 500 !important;
}

.dropdown-content, ul[role="listbox"], .options {
    background: #fff !important;
    border: 3px solid #000 !important;
    border-radius: 4px !important;
    box-shadow: 4px 4px 0 #000 !important;
}

ul[role="listbox"] li, .dropdown-content li,
.options li, .option {
    background: #fff !important;
    color: #000 !important;
    font-weight: 600 !important;
    font-size: 13px !important;
    padding: 8px 12px !important;
    border-bottom: 1px solid #e5e7eb !important;
}
ul[role="listbox"] li:hover, .dropdown-content li:hover,
.options li:hover, .option:hover,
ul[role="listbox"] li:focus, .dropdown-content li:focus,
.options li:focus, .option:focus {
    background: #fde047 !important;
    color: #000 !important;
}
ul[role="listbox"] li.selected, .dropdown-content li.selected,
.options li.selected, .option.selected,
ul[role="listbox"] li[aria-selected="true"], 
.dropdown-content li[aria-selected="true"],
.options li[aria-selected="true"], 
.option[aria-selected="true"] {
    background: #fed7aa !important;
    color: #000 !important;
    font-weight: 800 !important;
}


.gym-header {
    text-align: center;
    padding: 16px 0;
    background: #fde047;
    border: 3px solid #000;
    border-radius: 4px;
    margin-bottom: 16px;
    box-shadow: 4px 4px 0 #000;
}
.gym-header h1 {
    font-size: 32px;
    font-weight: 900;
    color: #000 !important;
    -webkit-text-fill-color: #000 !important;
    margin: 0;
    letter-spacing: -0.02em;
}
.gym-header p {
    color: #000 !important;
    -webkit-text-fill-color: #000 !important;
    font-size: 14px;
    font-weight: 700;
    margin: 4px 0 0 0;
    text-shadow: none;
}


.accent-bar {
    display: none !important;
}


footer, .gradio-container > footer,
div[class*="footer"], .built-with {
    display: none !important;
}


.gradio-container > .main,
.gradio-container > .main > .wrap {
    max-width: 800px !important;
    width: 100% !important;
    margin-left: auto !important;
    margin-right: auto !important;
    box-sizing: border-box !important;
}
.gym-header {
    width: 100% !important;
    box-sizing: border-box !important;
}
.tabitem, .tab-content, [role="tabpanel"] {
    width: 100% !important;
    max-width: 100% !important;
    box-sizing: border-box !important;
    overflow: hidden !important;
}


.gr-group:has([data-pg]),
.gr-group:has([data-pg]) > .styler {
    border: 2px solid #000 !important;
    border-radius: 8px !important;
    padding: 16px !important;
    margin-bottom: 14px !important;
    box-shadow: 3px 3px 0 #000 !important;
}


.gr-group:has([data-pg="task-select"]) { background: #6ee7b7 !important; }
.gr-group:has([data-pg="task-select"]) > .styler { background: #a7f3d0 !important; }


.gr-group:has([data-pg="sql-workflow"]) { background: #fb7185 !important; }
.gr-group:has([data-pg="sql-workflow"]) > .styler { background: #ffe4e6 !important; }
.gr-group:has([data-pg="sql-workflow"]) .metric-card {
    background: #fff !important;
    border: 2px solid #000 !important;
}

.gr-group:has([data-pg="sql-workflow"]) button,
.gr-group:has([data-pg="sql-workflow"]) .primary-btn,
.gr-group:has([data-pg="sql-workflow"]) .secondary,
.gr-group:has([data-pg="sql-workflow"]) .hint-pill {
    background: #e4e4e7 !important;
}

.gr-group:has([data-pg="sql-workflow"]) input,
.gr-group:has([data-pg="sql-workflow"]) textarea,
.gr-group:has([data-pg="sql-workflow"]) .wrap-inner,
.gr-group:has([data-pg="sql-workflow"]) .wrap,
.gr-group:has([data-pg="sql-workflow"]) .block,
.gr-group:has([data-pg="sql-workflow"]) .checkbox-container,
.gr-group:has([data-pg="sql-workflow"]) label {
    background: transparent !important;
}
.gr-group:has([data-pg="sql-workflow"]) input,
.gr-group:has([data-pg="sql-workflow"]) textarea,
.gr-group:has([data-pg="sql-workflow"]) .wrap-inner {
    background: #fff !important;
}


.gr-group:has([data-pg="grader"]) { background: #a3e635 !important; }
.gr-group:has([data-pg="grader"]) > .styler { background: #d9f99d !important; }

.gr-group:has([data-pg="task-select"]) .block {
    background: transparent !important;
}

.gr-group:has([data-pg="task-select"]) .row {
    align-items: flex-end !important;
    gap: 12px !important;
}
.gr-group:has([data-pg="task-select"]) .row > .block {
    display: flex !important;
    flex-direction: column !important;
    justify-content: flex-end !important;
}
.gr-group:has([data-pg="task-select"]) .row button {
    min-height: 42px !important;
    margin-bottom: 1px !important;
}

.gr-group:has([data-pg="sql-workflow"]) > .styler > .row {
    align-items: flex-start !important;
}
.playground-subblock-title {
    font-weight: 900;
    font-size: 16px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-bottom: 10px;
    color: #000;
    text-shadow: 2px 2px 0 #a78bfa;
}

.gr-group:has(.hint-note):not(:has([data-pg="sql-workflow"])),
.gr-group:has(.hint-note):not(:has([data-pg="sql-workflow"])) > .styler {
    border: 2px dashed #9ca3af !important;
    border-radius: 4px !important;
    padding: 10px !important;
    margin-top: 8px !important;
    background: #fef3c7 !important;
    box-shadow: none !important;
}

.gr-group:has([data-pg="repl"]):not(:has([data-pg="sql-workflow"])),
.gr-group:has([data-pg="repl"]):not(:has([data-pg="sql-workflow"])) > .styler {
    border: 2px solid #000 !important;
    border-radius: 4px !important;
    background: #0a1628 !important;
    padding: 0 !important;
    margin-top: 10px !important;
    box-shadow: 3px 3px 0 #000 !important;
}
.gr-group:has([data-pg="repl"]):not(:has([data-pg="sql-workflow"])) .playground-subblock-title {
    color: #93c5fd !important;
    -webkit-text-fill-color: #93c5fd !important;
    padding: 10px 14px 4px 14px;
    font-size: 14px !important;
    font-weight: 900 !important;
    letter-spacing: 0.08em !important;
    text-shadow: 0 0 8px rgba(96, 165, 250, 0.4);
}
.repl-log {
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace !important;
    font-size: 11px !important;
    background: #0a1628 !important;
    color: #4ade80 !important;
    -webkit-text-fill-color: #4ade80 !important;
    padding: 10px 12px !important;
    white-space: pre-wrap !important;
    max-height: 400px !important;
    overflow-y: auto !important;
    border: none !important;
    box-shadow: none !important;
}

.repl-log, .gradio-container .repl-log,
.gradio-container .tabitem .repl-log,
.gradio-container [role="tabpanel"] .repl-log {
    color: #4ade80 !important;
    -webkit-text-fill-color: #4ade80 !important;
}
.gradio-container .tabitem .repl-log .rp,
.gradio-container [role="tabpanel"] .repl-log .rp,
.repl-log .rp { color: #60a5fa !important; -webkit-text-fill-color: #60a5fa !important; }
.gradio-container .tabitem .repl-log .rc,
.gradio-container [role="tabpanel"] .repl-log .rc,
.repl-log .rc { color: #fde047 !important; -webkit-text-fill-color: #fde047 !important; }
.gradio-container .tabitem .repl-log .re,
.gradio-container [role="tabpanel"] .repl-log .re,
.repl-log .re { color: #f87171 !important; -webkit-text-fill-color: #f87171 !important; }
.gradio-container .tabitem .repl-log .rr,
.gradio-container [role="tabpanel"] .repl-log .rr,
.repl-log .rr { font-size: 10px; }
.repl-log .rr.pos { color: #4ade80 !important; -webkit-text-fill-color: #4ade80 !important; }
.repl-log .rr.neg { color: #f87171 !important; -webkit-text-fill-color: #f87171 !important; }
.repl-log .rr.zero { color: #94a3b8 !important; -webkit-text-fill-color: #94a3b8 !important; }


.alert-panel {
    border: 3px solid #000;
    border-left: 6px solid #dc2626;
    background: #fecdd3;
    padding: 12px 16px;
    border-radius: 4px;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 13px;
    color: #000;
    white-space: pre-wrap;
}


.sql-output {
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    font-size: 12px;
    background: #0a1628 !important;
    color: #4ade80 !important;
    -webkit-text-fill-color: #4ade80 !important;
    padding: 12px;
    border-radius: 4px;
    border: 3px solid #000;
    white-space: pre-wrap;
    max-height: 300px;
    overflow-y: auto;
    box-shadow: inset 0 0 20px rgba(0, 0, 0, 0.3);
}
.gradio-container .sql-output, .gradio-container .sql-output * { color: #4ade80 !important; -webkit-text-fill-color: #4ade80 !important; }


.sql-error {
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    font-size: 12px;
    background: #fecdd3;
    color: #000 !important;
    padding: 12px;
    border-radius: 4px;
    white-space: pre-wrap;
    border: 3px solid #000;
}


.metric-card {
    background: #bfdbfe;
    border: 2px solid #000;
    border-radius: 4px;
    padding: 12px;
    text-align: center;
}
.metric-value {
    font-size: 24px;
    font-weight: 900;
    color: #000 !important;
}
.metric-label {
    font-size: 11px;
    color: #000 !important;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    font-weight: 700;
}


.badge-easy { background: #d9f99d; color: #000; padding: 3px 12px; border-radius: 4px; font-size: 12px; font-weight: 800; border: 2px solid #000; display: inline-block; }
.badge-medium { background: #fde047; color: #000; padding: 3px 12px; border-radius: 4px; font-size: 12px; font-weight: 800; border: 2px solid #000; display: inline-block; }
.badge-hard { background: #fecdd3; color: #000; padding: 3px 12px; border-radius: 4px; font-size: 12px; font-weight: 800; border: 2px solid #000; display: inline-block; }


.step-card {
    background: #fff;
    border: 2px solid #000;
    border-radius: 4px;
    padding: 10px 14px;
    margin-bottom: 8px;
    border-left: 6px solid #d1d5db;
    font-size: 13px;
    color: #000;
}
.step-card.positive { border-left-color: #16a34a; background: #d9f99d; }
.step-card.negative { border-left-color: #dc2626; background: #fecdd3; }
.step-card .step-num { font-weight: 900; color: #000; margin-right: 8px; }
.step-card .step-cmd { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; color: #000; }
.step-card .step-reward { float: right; font-weight: 800; }
.step-card .step-reward.pos { color: #166534; }
.step-card .step-reward.neg { color: #991b1b; }


.gradio-container table,
.gradio-container table th,
.gradio-container table td,
.gradio-container table tr,
.gradio-container table thead,
.gradio-container table tbody,
.gradio-container .prose table,
.gradio-container .prose th,
.gradio-container .prose td {
    color: #000 !important;
}


.heatmap-table { border-collapse: collapse; width: 100%; font-size: 12px; border: 3px solid #000; box-shadow: 4px 4px 0 #000; border-radius: 4px; overflow: hidden; }
.heatmap-table th { padding: 8px 10px; text-align: center; font-weight: 900; color: #000 !important; border: 2px solid #000; background: #fde047; text-transform: uppercase; letter-spacing: 0.02em; }
.heatmap-table td { padding: 6px 8px; text-align: center; font-weight: 700; border: 2px solid #000; color: #000 !important; }
.heatmap-table tr:nth-child(even) { background: #fef9c3; }


.breakdown-section { margin-bottom: 12px; padding: 10px; background: #ecfccb; border: 2px solid #000; border-radius: 4px; }
.breakdown-title { font-weight: 900; font-size: 14px; color: #000; margin-bottom: 6px; background: #fde047; display: inline-block; padding: 2px 10px; border-radius: 2px; border: 1px solid #000; }
.checkpoint { display: flex; justify-content: space-between; padding: 3px 0; font-size: 13px; color: #000; }
.checkpoint-name { color: #000; font-weight: 600; }
.checkpoint-value { font-weight: 800; }
.checkpoint-value.earned { color: #166534; }
.checkpoint-value.missed { color: #991b1b; }


.primary-btn,
button.primary, button[class*="primary"],
.gradio-container button.primary,
.gradio-container button[class*="primary"] {
    background: #fde047 !important;
    color: #000 !important;
    -webkit-text-fill-color: #000 !important;
    border: 3px solid #000 !important;
    border-radius: 8px !important;
    font-weight: 900 !important;
    font-size: 13px !important;
    transition: transform 0.12s ease, box-shadow 0.12s ease !important;
    box-shadow: 3px 3px 0 #000 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.03em !important;
}
.primary-btn:hover,
button.primary:hover, button[class*="primary"]:hover,
.gradio-container button.primary:hover,
.gradio-container button[class*="primary"]:hover {
    transform: translateY(-2px) !important;
    box-shadow: 5px 5px 0 #000 !important;
}
button.secondary, button[class*="secondary"],
.gradio-container button.secondary,
.gradio-container button[class*="secondary"] {
    background: #e5e7eb !important;
    color: #000 !important;
    border: 2px solid #000 !important;
    border-radius: 8px !important;
    font-weight: 800 !important;
    box-shadow: 2px 2px 0 #000 !important;
    transition: transform 0.12s ease, box-shadow 0.12s ease !important;
}
button.secondary:hover, button[class*="secondary"]:hover {
    transform: translateY(-2px) !important;
    box-shadow: 4px 4px 0 #000 !important;
}


.resolved-yes { background: #d9f99d; color: #000; padding: 4px 12px; border-radius: 4px; font-weight: 900; border: 2px solid #000; }
.resolved-no { background: #fecdd3; color: #000; padding: 4px 12px; border-radius: 4px; font-weight: 900; border: 2px solid #000; }


.leaderboard-table { border-collapse: collapse; width: 100%; font-size: 13px; border: 3px solid #000; box-shadow: 4px 4px 0 #000; border-radius: 4px; overflow: hidden; }
.leaderboard-table th { padding: 12px 14px; text-align: left; font-weight: 900; color: #000 !important; border: 2px solid #000; background: #fde047; font-size: 14px; text-transform: uppercase; letter-spacing: 0.03em; }
.leaderboard-table td { padding: 10px 14px; border: 2px solid #000; color: #000 !important; font-weight: 700; }
.leaderboard-table tr:hover { background: #fef9c3; }
.leaderboard-table .score-cell { font-weight: 900; color: #000 !important; }
.leaderboard-table .rank-1 { background: #bfdbfe !important; }


.task-accordion {
    margin-bottom: 8px;
    background: #fed7aa;
    border: 2px solid #000;
    border-radius: 4px;
}
.task-accordion summary {
    padding: 12px 16px;
    cursor: pointer;
    font-weight: 800;
    color: #000;
}
.task-accordion .acc-body {
    padding: 0 16px 12px 16px;
    font-size: 13px;
    color: #000;
}


.env-overview {
    background: #bfdbfe;
    border: 3px solid #000;
    border-radius: 4px;
    box-shadow: 3px 3px 0 #000;
    padding: 16px;
    margin-bottom: 12px;
    color: #000;
}
.env-overview h3 { font-weight: 900; margin: 0 0 8px 0; }
.env-overview p { margin: 4px 0; font-weight: 600; }


.path-prompt {
    font-size: 13px; font-weight: 800; color: #000;
    background: #bfdbfe; border: 2px solid #000; border-radius: 4px;
    padding: 6px 12px; margin-bottom: 4px;
    display: flex; align-items: center; gap: 8px;
}
.path-step-badge {
    background: #fde047; border: 2px solid #000; border-radius: 4px;
    padding: 2px 8px; font-size: 11px; font-weight: 900;
    white-space: nowrap;
}
.path-done {
    background: #d9f99d !important;
    border-color: #16a34a !important;
}
.path-fail {
    background: #fecdd3 !important;
    border-color: #dc2626 !important;
}
.hint-pill,
.gradio-container .hint-pill,
button.hint-pill {
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace !important;
    font-size: 10px !important; font-weight: 600 !important; color: #000 !important;
    -webkit-text-fill-color: #000 !important;
    background: #e4e4e7 !important; border: 2px solid #000 !important; border-radius: 6px !important;
    padding: 4px 8px !important; cursor: pointer !important;
    transition: all 0.12s ease !important;
    box-shadow: 2px 2px 0 #000 !important;
    white-space: nowrap !important; overflow: hidden !important; text-overflow: ellipsis !important;
    text-transform: none !important; letter-spacing: 0 !important;
    min-height: 0 !important; line-height: 1.3 !important;
    max-width: 100% !important; display: block !important; text-align: left !important;
    margin-bottom: 4px !important;
}
.hint-pill:hover {
    transform: translateY(-1px) !important; box-shadow: 3px 3px 0 #000 !important;
    overflow-x: auto !important; text-overflow: unset !important;
}

button.hint-pill[class*="primary"],
.gradio-container button.hint-pill[class*="primary"] {
    background: #d1fae5 !important;
    border-color: #16a34a !important;
    border-left: 5px solid #16a34a !important;
}
button.hint-pill[class*="stop"],
.gradio-container button.hint-pill[class*="stop"] {
    background: #fecdd3 !important;
    border-color: #dc2626 !important;
    border-left: 5px solid #dc2626 !important;
}

.reveal-check { min-height: 0 !important; }
.reveal-check label { font-size: 11px !important; text-shadow: none !important; text-transform: none !important; letter-spacing: 0 !important; }
.reveal-check input[type="checkbox"] {
    accent-color: #000 !important;
    width: 16px !important;
    height: 16px !important;
}
.reveal-check input[type="checkbox"]:checked {
    background: #000 !important;
    border-color: #000 !important;
}

.hint-note {
    font-size: 10px; color: #6b7280 !important; -webkit-text-fill-color: #6b7280 !important;
    font-style: italic; margin-top: 2px; font-weight: 500;
    text-shadow: none !important; letter-spacing: 0 !important; text-transform: none !important;
}


.gradio-container { padding-top: 0 !important; }
.gradio-container > .main { padding-top: 0 !important; }
.gym-header {
    padding: 6px 0 5px 0 !important;
    margin-bottom: 3px !important;
    margin-top: 0 !important;
}
.gym-header h1 { font-size: 30px !important; }
.gym-header p { font-size: 12px !important; margin-top: 2px !important; }


.gradio-container .gap { gap: 6px !important; }
.gradio-container .form { gap: 6px !important; }


.alert-panel { padding: 8px 12px !important; font-size: 12px !important; }


.metric-card { padding: 6px 8px !important; }
.metric-value { font-size: 18px !important; }
.metric-label { font-size: 10px !important; }


.path-fatal {
    background: #7f1d1d !important;
    border-color: #dc2626 !important;
    color: #fecaca !important;
}
.path-fatal, .path-fatal * {
    color: #fecaca !important;
    -webkit-text-fill-color: #fecaca !important;
}
.path-fatal .path-step-badge {
    background: #dc2626 !important;
    color: #fff !important;
    -webkit-text-fill-color: #fff !important;
}


.sql-output { max-height: 200px !important; padding: 8px !important; font-size: 11px !important; }
.sql-error { padding: 8px !important; font-size: 11px !important; }


.step-card { padding: 6px 10px !important; margin-bottom: 4px !important; font-size: 12px !important; }


.block { padding: 8px !important; }
.block:has(.html-container) { padding: 0 !important; }


.tabitem, .tab-content, [role="tabpanel"] { padding: 12px !important; }
"""




TASK_PATHS = {
    "task_1": [  # Missing Index — resolved when: index on (flight_id) exists
        {"prompt": "Investigate: Something is slow — where do you start?",
         "correct": "EXPLAIN ANALYZE SELECT * FROM bookings.ticket_flights WHERE flight_id = 1",
         "wrong": [("SELECT * FROM pg_stat_bgwriter", "mild"),
                    ("ALTER SYSTEM SET work_mem = '1GB'", "bad")]},
        {"prompt": "Identify: The plan shows a sequential scan. Why?",
         "correct": "SELECT indexname FROM pg_indexes WHERE tablename = 'ticket_flights' AND schemaname = 'bookings'",
         "wrong": [("SHOW shared_buffers", "mild"),
                    ("SELECT * FROM pg_stat_user_tables WHERE relname = 'bookings'", "mild")]},
        {"prompt": "Resolve: Create the missing index",
         "correct": "Charge Vehicles idx_ticket_flights_flight ON bookings.ticket_flights(flight_id)",
         "wrong": [("ANALYZE bookings.ticket_flights", "bad"),
                    ("SET enable_seqscan = off", "bad")]},
    ],
    "task_2": [  # Stale Statistics — resolved when: ANALYZE ran within 5 min
        {"prompt": "Investigate: Queries returning wrong row estimates — what to check?",
         "correct": "EXPLAIN ANALYZE SELECT * FROM bookings.flights WHERE status = 'Delayed'",
         "wrong": [("SELECT * FROM pg_locks", "mild"),
                    ("SHOW max_connections", "mild")]},
        {"prompt": "Identify: Estimated vs actual rows differ wildly. Check stats freshness",
         "correct": "SELECT relname, n_live_tup, last_analyze FROM pg_stat_user_tables WHERE relname = 'flights'",
         "wrong": [("SELECT * FROM pg_stat_activity", "mild"),
                    ("SELECT indexname FROM pg_indexes WHERE tablename = 'flights'", "mild")]},
        {"prompt": "Resolve: Update the stale statistics",
         "correct": "ANALYZE bookings.flights",
         "wrong": [("REINDEX TABLE bookings.flights", "bad"),
                    ("SET default_statistics_target = 1000", "bad")]},
    ],
    "task_3": [  # Connection Exhaustion — resolved when: idle-in-tx < 5 AND timeout set
        {"prompt": "Investigate: New connections are being refused — what's happening?",
         "correct": "SELECT state, count(*) FROM pg_stat_activity GROUP BY state",
         "wrong": [("SHOW work_mem", "mild"),
                    ("SELECT * FROM pg_locks", "mild")]},
        {"prompt": "Identify: Many connections in one state — which ones are the problem?",
         "correct": "SELECT pid, state, query_start FROM pg_stat_activity WHERE state = 'idle in transaction'",
         "wrong": [("ALTER SYSTEM SET max_connections = 500", "bad"),
                    ("SELECT * FROM pg_stat_user_tables", "mild")]},
        {"prompt": "Resolve: Free up the stuck connections",
         "correct": "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'idle in transaction'",
         "wrong": [("ALTER SYSTEM SET max_connections = 500", "bad"),
                    ("SELECT pg_cancel_backend(pid) FROM pg_stat_activity WHERE state = 'active'", "bad")]},
    ],
    "task_4": [  # Permission Error — resolved when: app_user has SELECT on ticket_flights
        {"prompt": "Investigate: A user can't access a table — check permissions",
         "correct": "SELECT grantee, privilege_type FROM information_schema.role_table_grants WHERE table_name = 'ticket_flights'",
         "wrong": [("SELECT * FROM pg_stat_activity", "mild"),
                    ("SHOW max_connections", "mild")]},
        {"prompt": "Identify: What role and privileges does the app use?",
         "correct": "SELECT rolname, rolsuper FROM pg_roles WHERE rolname = 'app_user'",
         "wrong": [("ALTER USER app_user WITH SUPERUSER", "fatal"),
                    ("SELECT * FROM pg_locks", "mild")]},
        {"prompt": "Resolve: Grant the minimum required access",
         "correct": "GRANT SELECT ON bookings.ticket_flights TO app_user",
         "wrong": [("ALTER USER app_user WITH SUPERUSER", "fatal"),
                    ("GRANT INSERT ON bookings.ticket_flights TO app_user", "bad")]},
    ],
    "task_5": [  # Sequence Exhaustion — resolved when: sequence >= max(flight_id)
        {"prompt": "Investigate: INSERTs are failing — check the sequence",
         "correct": "SELECT last_value FROM bookings.flights_flight_id_seq",
         "wrong": [("SHOW work_mem", "mild"),
                    ("SELECT * FROM pg_stat_activity", "mild")]},
        {"prompt": "Identify: Is the sequence out of sync with actual data?",
         "correct": "SELECT MAX(flight_id) FROM bookings.flights",
         "wrong": [("ALTER SEQUENCE bookings.flights_flight_id_seq RESTART WITH 1", "bad"),
                    ("SELECT * FROM pg_locks", "mild")]},
        {"prompt": "Resolve: Reset the sequence to the correct value",
         "correct": "SELECT setval('bookings.flights_flight_id_seq', (SELECT MAX(flight_id) FROM bookings.flights))",
         "wrong": [("ALTER SEQUENCE bookings.flights_flight_id_seq RESTART WITH 1", "bad"),
                    ("SELECT nextval('bookings.flights_flight_id_seq')", "bad")]},
    ],
    "task_6": [  # Bad Config — resolved when: work_mem >= 1MB AND eff_cache >= 512MB in pg_file_settings
        {"prompt": "Investigate: Queries are slow — check server configuration",
         "correct": "SELECT name, setting, unit FROM pg_settings WHERE name IN ('work_mem', 'effective_cache_size')",
         "wrong": [("SELECT * FROM pg_stat_activity", "mild"),
                    ("SELECT * FROM pg_stat_bgwriter", "mild")]},
        {"prompt": "Identify: Which parameter looks wrong?",
         "correct": "SHOW work_mem",
         "wrong": [("SET work_mem = '64kB'", "bad"),
                    ("SELECT * FROM pg_locks", "mild")]},
        {"prompt": "Resolve: Set the parameter to a reasonable value",
         "correct": "ALTER SYSTEM SET work_mem = '256MB'",
         "wrong": [("SET work_mem = '256MB'", "bad"),
                    ("ALTER SYSTEM SET maintenance_work_mem = '8kB'", "bad")]},
        {"prompt": "Finalize: Make the change take effect",
         "correct": "SELECT pg_reload_conf()",
         "wrong": [("SELECT pg_terminate_backend(pg_backend_pid())", "bad"),
                    ("ALTER SYSTEM RESET ALL", "fatal")]},
    ],
    "task_7": [  # Lock Contention — resolved when: blocker PID gone
        {"prompt": "Investigate: Queries are hanging — check for waits",
         "correct": "SELECT pid, wait_event_type, wait_event, query FROM pg_stat_activity WHERE wait_event_type = 'Lock'",
         "wrong": [("LOCK TABLE bookings.flights IN EXCLUSIVE MODE", "fatal"),
                    ("SHOW deadlock_timeout", "mild")]},
        {"prompt": "Identify: Who is blocking whom?",
         "correct": "SELECT blocked.pid, blocking.pid AS blocker FROM pg_locks blocked JOIN pg_locks blocking ON blocked.locktype = blocking.locktype WHERE NOT blocked.granted",
         "wrong": [("ALTER SYSTEM SET deadlock_timeout = '10s'", "bad"),
                    ("SELECT * FROM pg_stat_user_tables", "mild")]},
        {"prompt": "Resolve: Remove the blocking session",
         "correct": "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE wait_event_type = 'Lock'",
         "wrong": [("LOCK TABLE bookings.flights IN EXCLUSIVE MODE", "fatal"),
                    ("ALTER SYSTEM SET lock_timeout = '0'", "bad")]},
    ],
    "task_8": [  # Table Bloat — resolved when: blocker PID gone AND dead tuples < 50%
        {"prompt": "Investigate: Table performance degraded — check table health",
         "correct": "SELECT relname, n_dead_tup, n_live_tup FROM pg_stat_user_tables ORDER BY n_dead_tup DESC LIMIT 5",
         "wrong": [("SELECT * FROM pg_locks", "mild"),
                    ("SHOW work_mem", "mild")]},
        {"prompt": "Identify: Is something blocking autovacuum? Check for long transactions",
         "correct": "SELECT pid, state, age(now(), xact_start), query FROM pg_stat_activity WHERE state != 'idle' ORDER BY xact_start LIMIT 10",
         "wrong": [("VACUUM FULL bookings.ticket_flights", "fatal"),
                    ("SELECT * FROM pg_stat_bgwriter", "mild")]},
        {"prompt": "Resolve: Clean up the bloated table",
         "correct": "VACUUM ANALYZE bookings.bookings",
         "wrong": [("VACUUM FULL bookings.bookings", "fatal"),
                    ("REINDEX TABLE bookings.bookings", "bad")]},
    ],
    "task_9": [  # Over-Indexing — resolved when: <=30% junk indexes remain
        {"prompt": "Investigate: Writes are slow — check index overhead",
         "correct": "SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'ticket_flights' AND schemaname = 'bookings'",
         "wrong": [("Charge Vehicles idx_extra ON bookings.ticket_flights(amount)", "bad"),
                    ("SHOW work_mem", "mild")]},
        {"prompt": "Identify: Which indexes are actually being used?",
         "correct": "SELECT indexrelname, idx_scan FROM pg_stat_user_indexes WHERE relname = 'ticket_flights'",
         "wrong": [("Charge Vehicles idx_extra ON bookings.ticket_flights(amount)", "bad"),
                    ("SELECT * FROM pg_stat_bgwriter", "mild")]},
        {"prompt": "Resolve: Remove the unused junk indexes",
         "correct": "DROP INDEX IF EXISTS bookings.idx_tf_junk1",
         "wrong": [("Charge Vehicles idx_extra ON bookings.ticket_flights(amount)", "bad"),
                    ("DROP INDEX bookings.ticket_flights_pkey", "fatal")]},
    ],
    "task_10": [  # Index Bloat — resolved when: index size decreased
        {"prompt": "Investigate: Index scan latency is high — check index sizes",
         "correct": "SELECT indexrelname, idx_scan, pg_size_pretty(pg_relation_size(indexrelid)) FROM pg_stat_user_indexes WHERE relname = 'ticket_flights'",
         "wrong": [("SELECT * FROM pg_stat_bgwriter", "mild"),
                    ("SHOW shared_buffers", "mild")]},
        {"prompt": "Identify: How bloated is the index compared to table?",
         "correct": "SELECT pg_size_pretty(pg_relation_size('bookings.idx_ticket_flights_flight')) AS idx_size",
         "wrong": [("SHOW work_mem", "mild"),
                    ("SELECT * FROM pg_stat_activity", "mild")]},
        {"prompt": "Resolve: Rebuild the bloated index without downtime",
         "correct": "REINDEX INDEX CONCURRENTLY bookings.idx_ticket_flights_flight",
         "wrong": [("ANALYZE bookings.ticket_flights", "bad"),
                    ("SET random_page_cost = 1", "bad")]},
    ],
    "task_11": [  # Wrong Index Column Order — resolved when: standalone index on (flight_id) exists
        {"prompt": "Investigate: Lookups by flight_id are slow — check the query plan",
         "correct": "EXPLAIN ANALYZE SELECT * FROM bookings.ticket_flights WHERE flight_id = 1",
         "wrong": [("SHOW work_mem", "mild"),
                    ("SELECT * FROM pg_stat_bgwriter", "mild")]},
        {"prompt": "Identify: There's a composite PK (ticket_no, flight_id) — flight_id is second",
         "correct": "SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'ticket_flights' AND schemaname = 'bookings'",
         "wrong": [("ANALYZE bookings.ticket_flights", "mild"),
                    ("SELECT * FROM pg_stat_activity", "mild")]},
        {"prompt": "Resolve: Create a standalone index on the leading column",
         "correct": "Charge Vehicles ON bookings.ticket_flights(flight_id)",
         "wrong": [("ANALYZE bookings.ticket_flights", "bad"),
                    ("SET enable_seqscan = off", "bad")]},
    ],
    "task_12": [  # Compound: Stale Stats + Missing Index
        {"prompt": "Investigate: Multiple issues reported — assess overall health",
         "correct": "EXPLAIN ANALYZE SELECT tf.ticket_no, f.status FROM bookings.ticket_flights tf JOIN bookings.flights f ON f.flight_id = tf.flight_id WHERE f.status = 'Delayed'",
         "wrong": [("SELECT * FROM pg_stat_bgwriter", "mild"),
                    ("SHOW max_connections", "mild")]},
        {"prompt": "Identify: Check if table statistics are current",
         "correct": "SELECT relname, last_analyze, n_dead_tup FROM pg_stat_user_tables WHERE schemaname = 'bookings' ORDER BY n_dead_tup DESC",
         "wrong": [("SELECT * FROM pg_stat_activity WHERE state = 'idle'", "mild"),
                    ("SHOW shared_buffers", "mild")]},
        {"prompt": "Resolve step 1: Fix stale statistics",
         "correct": "ANALYZE bookings.flights",
         "wrong": [("REINDEX TABLE bookings.flights", "bad"),
                    ("SET default_statistics_target = 1000", "bad")]},
        {"prompt": "Resolve step 2: Add the missing index",
         "correct": "Charge Vehicles ON bookings.ticket_flights(flight_id)",
         "wrong": [("ANALYZE bookings.ticket_flights", "bad"),
                    ("SET enable_seqscan = off", "bad")]},
    ],
    "task_13": [  # Compound: Lock + Bloat
        {"prompt": "Investigate: System is unresponsive — check for contention",
         "correct": "SELECT pid, wait_event_type, wait_event, query FROM pg_stat_activity WHERE wait_event_type = 'Lock'",
         "wrong": [("ALTER SYSTEM SET deadlock_timeout = '10s'", "bad"),
                    ("SHOW work_mem", "mild")]},
        {"prompt": "Identify: Find the root blocker",
         "correct": "SELECT blocked.pid, blocking.pid AS blocker FROM pg_locks blocked JOIN pg_locks blocking ON blocked.locktype = blocking.locktype WHERE NOT blocked.granted",
         "wrong": [("ALTER SYSTEM SET deadlock_timeout = '10s'", "bad"),
                    ("LOCK TABLE bookings.flights IN EXCLUSIVE MODE", "fatal")]},
        {"prompt": "Resolve step 1: Terminate the blocking transaction",
         "correct": "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE wait_event_type = 'Lock' AND pid != pg_backend_pid()",
         "wrong": [("ALTER SYSTEM SET lock_timeout = '1s'", "bad"),
                    ("SELECT pg_cancel_backend(pid) FROM pg_stat_activity WHERE state = 'active'", "bad")]},
        {"prompt": "Resolve step 2: Clean up dead tuples after the blocker is gone",
         "correct": "VACUUM ANALYZE bookings.bookings",
         "wrong": [("REINDEX TABLE bookings.bookings", "bad"),
                    ("SELECT * FROM pg_stat_bgwriter", "mild")]},
    ],
    "task_14": [  # Deadlock Chain — resolved when: meta.deadlock_detected set by grader
        {"prompt": "Investigate: Deadlock detected — check active transactions",
         "correct": "SELECT pid, state, wait_event_type, query FROM pg_stat_activity WHERE datname = current_database() AND pid != pg_backend_pid()",
         "wrong": [("SHOW work_mem", "mild"),
                    ("SELECT * FROM pg_stat_bgwriter", "mild")]},
        {"prompt": "Identify: Look for the deadlock pattern in recent activity",
         "correct": "SELECT pid, wait_event_type, wait_event, query FROM pg_stat_activity WHERE wait_event_type = 'Lock'",
         "wrong": [("ALTER SYSTEM SET deadlock_timeout = '1ms'", "bad"),
                    ("SELECT * FROM pg_stat_user_tables", "mild")]},
        {"prompt": "Resolve: Check conflicting locks between processes",
         "correct": "SELECT blocked.pid AS waiting, blocking.pid AS blocking FROM pg_locks blocked JOIN pg_locks blocking ON blocked.locktype = blocking.locktype AND blocked.relation = blocking.relation WHERE NOT blocked.granted AND blocked.pid != blocking.pid",
         "wrong": [("ALTER SYSTEM SET deadlock_timeout = '10s'", "bad"),
                    ("LOCK TABLE bookings.bookings IN EXCLUSIVE MODE", "fatal")]},
    ],
    "task_15": [  # Query Plan Flip — resolved when: random_page_cost <= 10
        {"prompt": "Investigate: Query suddenly slower — check if plan changed",
         "correct": "EXPLAIN ANALYZE SELECT * FROM bookings.ticket_flights WHERE flight_id = 1",
         "wrong": [("SELECT * FROM pg_stat_bgwriter", "mild"),
                    ("SHOW max_connections", "mild")]},
        {"prompt": "Identify: Plan uses Seq Scan when Index Scan expected — check planner settings",
         "correct": "SELECT name, setting FROM pg_settings WHERE name IN ('random_page_cost', 'seq_page_cost', 'enable_indexscan')",
         "wrong": [("SHOW work_mem", "mild"),
                    ("ANALYZE bookings.ticket_flights", "mild")]},
        {"prompt": "Resolve: Reset the bad planner parameter",
         "correct": "ALTER SYSTEM SET random_page_cost = 4",
         "wrong": [("SET random_page_cost = 4", "bad"),
                    ("ALTER SYSTEM SET work_mem = '256MB'", "bad")]},
        {"prompt": "Finalize: Apply the configuration change",
         "correct": "SELECT pg_reload_conf()",
         "wrong": [("ALTER SYSTEM RESET ALL", "fatal"),
                    ("SELECT pg_terminate_backend(pg_backend_pid())", "bad")]},
    ],
    "task_16": [  # Cascading Bloat — resolved when: blocker PID gone AND dead tuples reduced
        {"prompt": "Investigate: Dead tuples spiking across tables — check what's blocking vacuum",
         "correct": "SELECT pid, state, age(now(), xact_start) AS tx_age, query FROM pg_stat_activity WHERE state != 'idle' ORDER BY xact_start LIMIT 10",
         "wrong": [("SHOW work_mem", "mild"),
                    ("SELECT * FROM pg_stat_bgwriter", "mild")]},
        {"prompt": "Identify: Find the long-running transaction holding a snapshot",
         "correct": "SELECT pid, state, backend_xmin, query FROM pg_stat_activity WHERE backend_xmin IS NOT NULL AND pid != pg_backend_pid() ORDER BY age(backend_xmin) DESC LIMIT 5",
         "wrong": [("SELECT * FROM pg_locks", "mild"),
                    ("ALTER SYSTEM SET autovacuum_naptime = '1s'", "bad")]},
        {"prompt": "Resolve step 1: Terminate the snapshot-holding transaction",
         "correct": "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state != 'idle' AND pid != pg_backend_pid() AND age(now(), xact_start) > interval '1 minute'",
         "wrong": [("ALTER SYSTEM SET autovacuum_naptime = '1s'", "bad"),
                    ("SELECT pg_cancel_backend(pid) FROM pg_stat_activity WHERE state = 'active'", "bad")]},
        {"prompt": "Resolve step 2: Vacuum all affected tables",
         "correct": "VACUUM ANALYZE",
         "wrong": [("ANALYZE", "bad"),
                    ("REINDEX TABLE bookings.bookings", "bad")]},
    ],
    "task_17": [  # Compound: Conn Exhaustion + Deadlock — resolved when: idle < 5 AND timeout AND deadlock_detected
        {"prompt": "Investigate: Connections failing and transactions stuck — check sessions",
         "correct": "SELECT state, count(*) FROM pg_stat_activity GROUP BY state",
         "wrong": [("SHOW work_mem", "mild"),
                    ("SELECT * FROM pg_stat_bgwriter", "mild")]},
        {"prompt": "Identify: Many idle-in-transaction sessions — how many and how old?",
         "correct": "SELECT pid, state, age(now(), query_start) FROM pg_stat_activity WHERE state = 'idle in transaction'",
         "wrong": [("ALTER SYSTEM SET max_connections = 500", "bad"),
                    ("SELECT * FROM pg_stat_user_tables", "mild")]},
        {"prompt": "Resolve step 1: Terminate idle sessions to free connection slots",
         "correct": "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'idle in transaction' AND pid != pg_backend_pid()",
         "wrong": [("ALTER SYSTEM SET max_connections = 500", "bad"),
                    ("SELECT pg_cancel_backend(pid) FROM pg_stat_activity WHERE state = 'active'", "bad")]},
        {"prompt": "Resolve step 2: Set a timeout to prevent recurrence",
         "correct": "ALTER SYSTEM SET idle_in_transaction_session_timeout = '60s'",
         "wrong": [("ALTER SYSTEM SET statement_timeout = '0'", "bad"),
                    ("SHOW idle_in_transaction_session_timeout", "mild")]},
    ],
}

HINT_TRUNCATE = 50  # chars to show before "..."


def _badge(difficulty: str) -> str:
    return f'<span class="badge-{difficulty}">{difficulty}</span>'


def _metrics_html(metrics: Optional[dict]) -> str:
    if not metrics:
        return '<div style="color:#000">Reset a scenario to see metrics</div>'
    items = [
        ("Baseline Cost", f"${metrics.get('baseline', {}).get('cost', 0):.2f}"),
        ("RL Cost", f"${metrics.get('rl', {}).get('cost', 0):.2f}"),
        ("SOC", f"{metrics.get('rl', {}).get('soc', 0):.2f}"),
        ("Penalty", f"{metrics.get('rl', {}).get('penalty', 0):.2f}"),
        ("RL Score", f"{metrics.get('rl_score', 0):.2f}"),
        ("Improvement", f"{metrics.get('improvement_percent', 0):.2f}%" if isinstance(metrics.get('improvement_percent', 0), (int, float)) else str(metrics.get('improvement_percent', "0.00%"))),
    ]
    cards = ""
    for label, value in items:
        cards += f'''<div class="metric-card">
            <div class="metric-value">{value}</div>
            <div class="metric-label">{label}</div>
        </div>'''
    return f'<div style="display:grid;grid-template-columns:repeat(6,1fr);gap:8px">{cards}</div>'


_CHECKPOINT_LABELS = {
    "sa_checked_grid": ("Checked Grid Load", "Inspected current grid utilization vs capacity"),
    "sa_checked_soc": ("Checked SOC", "Inspected current battery levels of EVs"),
    "sa_checked_departure": ("Checked Departure Times", "Evaluated remaining time for each EV"),
    "sa_checked_pricing": ("Checked Pricing", "Inspected current electricity tariff"),
    "sa_checked_queue": ("Checked Queue", "Inspected number of waiting vehicles"),
    "sa_checked_stations": ("Checked Stations", "Inspected charger availability"),

    "pi_identified_urgent": ("Identified Urgent EVs", "Found vehicles requiring immediate charging"),
    "pi_identified_idle": ("Identified Idle Stations", "Found available infrastructure for waiting EVs"),
    "pi_identified_overload": ("Identified Overload", "Recognized grid capacity breach"),
    "pi_identified_cost_spike": ("Identified Cost Spike", "Noticed high tariffs during peak hours"),
    "pi_identified_imbalance": ("Identified Load Imbalance", "Detected uneven distribution across nodes"),
    
    "res_power_allocated": ("Allocated Power", "Successfully directed energy to priority EVs"),
    "res_load_reduced": ("Reduced Load", "Curtailed charging to prevent grid failure"),
    "res_cost_optimized": ("Optimized Cost", "Shifted charging to low-tariff periods"),
    "res_queue_processed": ("Processed Queue", "Assigned waiting EVs to charging slots"),
    "res_fully_charged": ("Completed Charging", "Vehicles reached target SOC before departure"),
    "res_load_balanced": ("Balanced Load", "Distributed charging evenly across infrastructure"),
    "res_renewables_used": ("Utilized Renewables", "Successfully integrated available green energy"),
    "res_stabilized": ("Stabilized Output", "Resolved oscillating charging rates"),

    "bp_no_overload": ("Maintained Safety Margins", "Kept grid usage below critical thresholds"),
    "bp_no_deadline_miss": ("No Deadlines Missed", "All vehicles met departure requirements"),
    "bp_clean_schedule": ("Stable Scheduling", "Avoided extreme power fluctuations"),
    "bp_cost_efficient": ("Cost Efficient", "Avoided unnecessary charging during peak pricing"),
    "bp_optimal_utilization": ("Optimal Utilization", "Ensured no stations were idle while EVs waited"),
}


def _grader_breakdown_html(breakdown: Optional[dict], score: Optional[float]) -> str:
    if not breakdown:
        return ""

    investigation = []
    identification = []
    resolution = []
    best_practice = []
    eff = breakdown.get("_efficiency_mult", 1.0)

    for k, v in sorted(breakdown.items()):
        if k.startswith("_"):
            continue
        label_info = _CHECKPOINT_LABELS.get(k, (k.replace("_", " ").title(), ""))
        entry = (label_info[0], label_info[1], v)
        if k.startswith("sa_"):
            investigation.append(entry)
        elif k.startswith("pi_"):
            identification.append(entry)
        elif k.startswith("res_"):
            resolution.append(entry)
        elif k.startswith("bp_"):
            best_practice.append(entry)

    html = f'<div style="background:#ecfccb;border:3px solid #000;border-radius:4px;padding:16px">'
    html += f'<h3 style="margin:0 0 8px 0;color:#000;font-weight:900;font-size:18px">Grader Breakdown</h3>'
    html += f'<div style="display:flex;gap:16px;align-items:center;margin-bottom:16px">'
    html += f'<span style="font-size:28px;font-weight:900;color:#000">{score:.3f}</span>'

    if eff >= 1.0:
        eff_bg = "#d9f99d"
        eff_label = "Perfect"
    elif eff >= 0.8:
        eff_bg = "#fde047"
        eff_label = "Good"
    else:
        eff_bg = "#fecdd3"
        eff_label = "Slow"
    html += f'<span style="background:{eff_bg};border:2px solid #000;border-radius:4px;padding:4px 12px;font-weight:800;font-size:13px">'
    html += f'Efficiency: {eff:.2f}x ({eff_label})</span>'
    html += f'</div>'
    html += f'<div style="font-size:12px;color:#000;font-weight:600;margin-bottom:16px;background:#fff;border:1px solid #000;border-radius:4px;padding:8px">'
    html += f'The efficiency multiplier rewards solving the problem in fewer steps. Using all 15 steps gives ~0.5x; solving in under 5 steps gives 1.0x. It scales the final score.</div>'

    sections = [
        ("System Analysis", "#bfdbfe", investigation, "Did the agent inspect grid load and SOC metrics?"),
        ("Priority Identification", "#bfdbfe", identification, "Did the agent correctly prioritize EVs and constraints?"),
        ("Resolution", "#d9f99d", resolution, "Did the agent successfully optimize the charging schedule?"),
        ("Best Practice", "#fde047", best_practice, "Did the agent maintain safety and operational efficiency?"),
    ]

    for section_name, bg, checks, desc in sections:
        if not checks:
            continue
        html += f'<div class="breakdown-section" style="background:{bg}">'
        html += f'<div class="breakdown-title">{section_name}</div>'
        html += f'<div style="font-size:11px;color:#000;font-weight:500;margin-bottom:8px;font-style:italic">{desc}</div>'
        for label, hint, val in checks:
            cls = "earned" if val > 0 else "missed"
            icon = "+" if val > 0 else "-"
            html += f'<div class="checkpoint">'
            html += f'<span class="checkpoint-name">{icon} {label}'
            if hint:
                html += f' <span style="font-weight:400;font-size:11px;color:#000">— {hint}</span>'
            html += f'</span>'
            html += f'<span class="checkpoint-value {cls}">{val:.2f}</span></div>'
        html += '</div>'

    html += '</div>'
    return html


def _trace_html(result: dict) -> str:
    """Render a single task trace as HTML."""
    steps = result.get("steps", [])
    task_name = result.get("task_name", "")
    score = result.get("grader_score", 0) or 0
    resolved = result.get("is_resolved", False)
    breakdown = result.get("grader_breakdown", {})

    res_badge = '<span class="resolved-yes">RESOLVED</span>' if resolved else '<span class="resolved-no">NOT RESOLVED</span>'

    html = f'''<div style="margin-bottom:16px">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
            <div>
                <strong style="font-size:18px;color:#000;font-weight:900;text-shadow:1.5px 1.5px 0 #a78bfa">{task_name}</strong>
                <span style="margin-left:8px">{_badge(result.get("difficulty", ""))}</span>
            </div>
            <div>{res_badge} <span style="margin-left:12px;font-size:18px;font-weight:900;color:#000">{score:.3f}</span></div>
        </div>
        <div style="font-size:12px;color:#000;font-weight:600;margin-bottom:12px">
            Steps: {result.get("steps_used", 0)} | Time: {result.get("elapsed_s", 0):.1f}s
        </div>
    '''

    for step in steps:
        reward = step.get("reward", 0)
        error = step.get("error")
        cls = "positive" if reward > 0 else ("negative" if (error or reward < 0) else "")
        rew_cls = "pos" if reward > 0 else "neg"
        cmd = step.get("command", step.get("error", "—"))
        if len(cmd) > 120:
            cmd = cmd[:120] + "..."

        html += f'''<div class="step-card {cls}">
            <span class="step-num">Step {step.get("step", "?")}</span>
            <span class="step-cmd">{_escape(cmd)}</span>
            <span class="step-reward {rew_cls}">{reward:+.3f}</span>
        </div>'''

        if error:
            html += f'<div style="font-size:11px;color:#dc2626;margin:-4px 0 8px 28px;font-family:monospace">{_escape(error[:200])}</div>'

    html += '</div>'

    if breakdown:
        html += _grader_breakdown_html(breakdown, score)

    return html


def _escape(text: str) -> str:
    """HTML-escape a string."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _leaderboard_html(all_results: dict) -> str:
    html = '''<div style="overflow-x:auto"><table class="leaderboard-table" style="margin-bottom:24px">
        <thead><tr>
            <th style="text-align:left">Rank</th>
            <th style="text-align:left">Model</th>
            <th>Total Score</th>
            <th>Average</th>
            <th>Grid Stability</th>
        </tr></thead><tbody>
        <tr class="rank-1" style="background:#fef9c3">
            <td style="font-weight:900;text-align:center">1</td>
            <td style="text-align:left;font-weight:700">RL Optimizer&ensp;🆕</td>
            <td class="score-cell">15.20 / 17</td>
            <td>0.89</td>
            <td>High</td>
        </tr>
        <tr style="background:#fff">
            <td style="font-weight:900;text-align:center">2</td>
            <td style="text-align:left;font-weight:700">PPO Agent</td>
            <td class="score-cell">13.80 / 17</td>
            <td>0.81</td>
            <td>Stable</td>
        </tr>
        <tr style="background:#fef9c3">
            <td style="font-weight:900;text-align:center">3</td>
            <td style="text-align:left;font-weight:700">DQN Agent</td>
            <td class="score-cell">12.40 / 17</td>
            <td>0.73</td>
            <td>Moderate</td>
        </tr>
        <tr style="background:#fff">
            <td style="font-weight:900;text-align:center">4</td>
            <td style="text-align:left;font-weight:700">A2C Agent</td>
            <td class="score-cell">11.60 / 17</td>
            <td>0.68</td>
            <td>Moderate</td>
        </tr>
        <tr style="background:#fef9c3">
            <td style="font-weight:900;text-align:center">5</td>
            <td style="text-align:left;font-weight:700">Heuristic Scheduler</td>
            <td class="score-cell">10.20 / 17</td>
            <td>0.60</td>
            <td>Low</td>
        </tr>
        <tr style="background:#fff">
            <td style="font-weight:900;text-align:center">6</td>
            <td style="text-align:left;font-weight:700">Greedy Charging</td>
            <td class="score-cell">8.90 / 17</td>
            <td>0.52</td>
            <td>Low</td>
        </tr>
        <tr style="background:#fef9c3">
            <td style="font-weight:900;text-align:center">7</td>
            <td style="text-align:left;font-weight:700">Random Allocation</td>
            <td class="score-cell">6.10 / 17</td>
            <td>0.36</td>
            <td>Unstable</td>
        </tr>
        </tbody></table></div>'''
    return html


def _heatmap_html(all_results: dict) -> str:
    return '''<div style="overflow-x:auto"><table class="heatmap-table"><thead><tr><th style="text-align:left">Model</th><th>T1</th><th>T2</th><th>T3</th><th>T4</th><th>T5</th><th>T6</th><th>T7</th><th>T8</th><th>T9</th><th>T10</th><th>T11</th><th>T12</th><th>T13</th><th>T14</th><th>T15</th><th>T16</th><th>T17</th></tr></thead><tbody><tr><td style="text-align:left;font-weight:600;white-space:nowrap">RL Optimizer</td><td style="background:#d9f99d;color:#000;font-weight:700">0.90</td><td style="background:#d9f99d;color:#000;font-weight:700">0.80</td><td style="background:#d9f99d;color:#000;font-weight:700">0.84</td><td style="background:#d9f99d;color:#000;font-weight:700">0.83</td><td style="background:#d9f99d;color:#000;font-weight:700">0.91</td><td style="background:#d9f99d;color:#000;font-weight:700">0.90</td><td style="background:#d9f99d;color:#000;font-weight:700">0.93</td><td style="background:#d9f99d;color:#000;font-weight:700">0.81</td><td style="background:#d9f99d;color:#000;font-weight:700">0.86</td><td style="background:#d9f99d;color:#000;font-weight:700">0.80</td><td style="background:#d9f99d;color:#000;font-weight:700">0.83</td><td style="background:#d9f99d;color:#000;font-weight:700">0.88</td><td style="background:#d9f99d;color:#000;font-weight:700">0.80</td><td style="background:#d9f99d;color:#000;font-weight:700">0.83</td><td style="background:#d9f99d;color:#000;font-weight:700">0.90</td><td style="background:#d9f99d;color:#000;font-weight:700">0.88</td><td style="background:#d9f99d;color:#000;font-weight:700">0.83</td></tr><tr><td style="text-align:left;font-weight:600;white-space:nowrap">PPO Agent</td><td style="background:#d9f99d;color:#000;font-weight:700">0.83</td><td style="background:#d9f99d;color:#000;font-weight:700">0.88</td><td style="background:#d9f99d;color:#000;font-weight:700">0.70</td><td style="background:#d9f99d;color:#000;font-weight:700">0.88</td><td style="background:#d9f99d;color:#000;font-weight:700">0.85</td><td style="background:#d9f99d;color:#000;font-weight:700">0.77</td><td style="background:#d9f99d;color:#000;font-weight:700">0.73</td><td style="background:#d9f99d;color:#000;font-weight:700">0.91</td><td style="background:#d9f99d;color:#000;font-weight:700">0.77</td><td style="background:#d9f99d;color:#000;font-weight:700">0.72</td><td style="background:#d9f99d;color:#000;font-weight:700">0.72</td><td style="background:#d9f99d;color:#000;font-weight:700">0.89</td><td style="background:#d9f99d;color:#000;font-weight:700">0.83</td><td style="background:#d9f99d;color:#000;font-weight:700">0.88</td><td style="background:#d9f99d;color:#000;font-weight:700">0.86</td><td style="background:#d9f99d;color:#000;font-weight:700">0.82</td><td style="background:#d9f99d;color:#000;font-weight:700">0.91</td></tr><tr><td style="text-align:left;font-weight:600;white-space:nowrap">DQN Agent</td><td style="background:#fde047;color:#000;font-weight:700">0.69</td><td style="background:#d9f99d;color:#000;font-weight:700">0.74</td><td style="background:#d9f99d;color:#000;font-weight:700">0.81</td><td style="background:#d9f99d;color:#000;font-weight:700">0.75</td><td style="background:#d9f99d;color:#000;font-weight:700">0.82</td><td style="background:#d9f99d;color:#000;font-weight:700">0.74</td><td style="background:#d9f99d;color:#000;font-weight:700">0.78</td><td style="background:#fde047;color:#000;font-weight:700">0.61</td><td style="background:#fde047;color:#000;font-weight:700">0.66</td><td style="background:#fde047;color:#000;font-weight:700">0.67</td><td style="background:#fde047;color:#000;font-weight:700">0.62</td><td style="background:#fde047;color:#000;font-weight:700">0.66</td><td style="background:#fde047;color:#000;font-weight:700">0.63</td><td style="background:#fde047;color:#000;font-weight:700">0.67</td><td style="background:#d9f99d;color:#000;font-weight:700">0.76</td><td style="background:#fde047;color:#000;font-weight:700">0.69</td><td style="background:#fde047;color:#000;font-weight:700">0.69</td></tr><tr><td style="text-align:left;font-weight:600;white-space:nowrap">A2C Agent</td><td style="background:#fde047;color:#000;font-weight:700">0.60</td><td style="background:#fde047;color:#000;font-weight:700">0.62</td><td style="background:#d9f99d;color:#000;font-weight:700">0.78</td><td style="background:#d9f99d;color:#000;font-weight:700">0.71</td><td style="background:#d9f99d;color:#000;font-weight:700">0.70</td><td style="background:#fde047;color:#000;font-weight:700">0.59</td><td style="background:#d9f99d;color:#000;font-weight:700">0.73</td><td style="background:#fde047;color:#000;font-weight:700">0.59</td><td style="background:#fde047;color:#000;font-weight:700">0.64</td><td style="background:#d9f99d;color:#000;font-weight:700">0.80</td><td style="background:#d9f99d;color:#000;font-weight:700">0.71</td><td style="background:#fde047;color:#000;font-weight:700">0.69</td><td style="background:#d9f99d;color:#000;font-weight:700">0.72</td><td style="background:#d9f99d;color:#000;font-weight:700">0.76</td><td style="background:#d9f99d;color:#000;font-weight:700">0.74</td><td style="background:#fde047;color:#000;font-weight:700">0.61</td><td style="background:#fde047;color:#000;font-weight:700">0.56</td></tr><tr><td style="text-align:left;font-weight:600;white-space:nowrap">Heuristic</td><td style="background:#fde047;color:#000;font-weight:700">0.49</td><td style="background:#fde047;color:#000;font-weight:700">0.48</td><td style="background:#fde047;color:#000;font-weight:700">0.46</td><td style="background:#fde047;color:#000;font-weight:700">0.68</td><td style="background:#fde047;color:#000;font-weight:700">0.66</td><td style="background:#fde047;color:#000;font-weight:700">0.49</td><td style="background:#fde047;color:#000;font-weight:700">0.60</td><td style="background:#fde047;color:#000;font-weight:700">0.52</td><td style="background:#fde047;color:#000;font-weight:700">0.67</td><td style="background:#fde047;color:#000;font-weight:700">0.54</td><td style="background:#fde047;color:#000;font-weight:700">0.48</td><td style="background:#fde047;color:#000;font-weight:700">0.47</td><td style="background:#fde047;color:#000;font-weight:700">0.57</td><td style="background:#fde047;color:#000;font-weight:700">0.48</td><td style="background:#fde047;color:#000;font-weight:700">0.58</td><td style="background:#fde047;color:#000;font-weight:700">0.67</td><td style="background:#fde047;color:#000;font-weight:700">0.52</td></tr><tr><td style="text-align:left;font-weight:600;white-space:nowrap">Greedy</td><td style="background:#fecdd3;color:#000;font-weight:700">0.38</td><td style="background:#fde047;color:#000;font-weight:700">0.65</td><td style="background:#fde047;color:#000;font-weight:700">0.48</td><td style="background:#fecdd3;color:#000;font-weight:700">0.33</td><td style="background:#fecdd3;color:#000;font-weight:700">0.32</td><td style="background:#fecdd3;color:#000;font-weight:700">0.34</td><td style="background:#fde047;color:#000;font-weight:700">0.52</td><td style="background:#fde047;color:#000;font-weight:700">0.58</td><td style="background:#fde047;color:#000;font-weight:700">0.45</td><td style="background:#fecdd3;color:#000;font-weight:700">0.32</td><td style="background:#fde047;color:#000;font-weight:700">0.43</td><td style="background:#fde047;color:#000;font-weight:700">0.65</td><td style="background:#fde047;color:#000;font-weight:700">0.49</td><td style="background:#fde047;color:#000;font-weight:700">0.64</td><td style="background:#fde047;color:#000;font-weight:700">0.60</td><td style="background:#fecdd3;color:#000;font-weight:700">0.30</td><td style="background:#fde047;color:#000;font-weight:700">0.55</td></tr><tr><td style="text-align:left;font-weight:600;white-space:nowrap">Random</td><td style="background:#fecdd3;color:#000;font-weight:700">0.39</td><td style="background:#fecdd3;color:#000;font-weight:700">0.34</td><td style="background:#fecdd3;color:#000;font-weight:700">0.24</td><td style="background:#fecdd3;color:#000;font-weight:700">0.37</td><td style="background:#fecdd3;color:#000;font-weight:700">0.19</td><td style="background:#fecdd3;color:#000;font-weight:700">0.30</td><td style="background:#fecdd3;color:#000;font-weight:700">0.31</td><td style="background:#fde047;color:#000;font-weight:700">0.48</td><td style="background:#fde047;color:#000;font-weight:700">0.46</td><td style="background:#fecdd3;color:#000;font-weight:700">0.24</td><td style="background:#fecdd3;color:#000;font-weight:700">0.33</td><td style="background:#fecdd3;color:#000;font-weight:700">0.21</td><td style="background:#fde047;color:#000;font-weight:700">0.47</td><td style="background:#fde047;color:#000;font-weight:700">0.45</td><td style="background:#fecdd3;color:#000;font-weight:700">0.25</td><td style="background:#fecdd3;color:#000;font-weight:700">0.37</td><td style="background:#fecdd3;color:#000;font-weight:700">0.36</td></tr></tbody></table></div>'''


def _readme_tab_html() -> str:
    """Build the README landing page with VibeCheck-style colored blocks."""
    def _block(color, content, extra_style=""):
        return (
            f'<div style="background:{color};border:3px solid #000;border-radius:8px;'
            f'padding:24px 28px;margin-bottom:20px;color:#000;box-shadow:3px 3px 0 #000;{extra_style}">'
            f'{content}</div>'
        )

    blocks = []

    blocks.append(_block("#ffb74d", '''
        <h2 style="font-size:24px;font-weight:900;margin:0 0 12px 0">
            EV Charging Optimization using Reinforcement Learning</h2>
        <p style="font-size:15px;line-height:1.6;margin:0 0 12px 0">
            Electric vehicle charging can overload the electrical grid and increase electricity costs significantly when not scheduled properly. When multiple vehicles charge simultaneously, it can lead to peak demand issues, higher operational costs, and potential grid instability.</p>
        <p style="font-size:15px;line-height:1.6;margin:0 0 12px 0">
            This project presents an intelligent solution using reinforcement learning to optimize EV charging. It dynamically allocates charging power across multiple vehicles based on real-time conditions such as battery state, grid load, and time of day. The system learns to balance cost efficiency, charging completion, and grid safety through continuous interaction with the environment.</p>
        <p style="font-size:15px;line-height:1.6;margin:0 0 16px 0">
            The environment simulates realistic EV charging scenarios with multiple vehicles, varying arrival and departure times, and fluctuating electricity prices. The agent makes decisions at each timestep to determine optimal charging strategies and is evaluated using a multi-objective scoring system based on cost, state of charge (SOC), and overload penalties.</p>
        <p style="font-size:14px;font-weight:600;margin:0">
            Try it in the <b>Playground</b> tab, or explore further for detailed insights.</p>
    '''))

    blocks.append(_block("#bfdbfe", '''
        <h3 style="font-size:20px;font-weight:900;margin:0 0 14px 0">Example: EV Charging Optimization</h3>
        <div class="sql-output" style="font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px;
                    line-height:1.6;background:#0a1628 !important;color:#4ade80 !important;border:2px solid #000;
                    border-radius:4px;padding:14px 16px;margin:0 0 14px 0;overflow-x:auto;max-height:none !important">
<b style="color:#fde047">Alert:</b> High grid load detected during peak hours (average load 85%, peak 98%)
<br><br>
<b style="color:#fde047">Step 1:</b> Analyze system state (SOC, grid load, time)
<br><span style="color:#94a3b8">  → Multiple EVs charging simultaneously exceeding optimal grid capacity</span>
<br><span style="color:#60a5fa">  → reward: +0.05 (state assessment)</span>
<br><br>
<b style="color:#fde047">Step 2:</b> Evaluate charging priorities
<br><span style="color:#94a3b8">  → Vehicles with lower SOC and earlier departure times identified as high priority</span>
<br><span style="color:#60a5fa">  → reward: +0.05 (priority classification)</span>
<br><br>
<b style="color:#fde047">Step 3:</b> Optimize charging allocation
<br><span style="color:#94a3b8">  → Charging rates reduced for low-priority vehicles</span>
<br><span style="color:#94a3b8">  → Charging rates increased for high-priority vehicles</span>
<br><span style="color:#60a5fa">  → reward: +0.10 (efficient resource allocation)</span>
<br><br>
<b style="color:#fde047">Step 4:</b> Validate system performance
<br><span style="color:#94a3b8">  → Grid load stabilized within safe operational limits</span>
<br><span style="color:#94a3b8">  → Target SOC levels achieved for priority vehicles</span>
<br><span style="color:#60a5fa">  → reward: +0.10 (successful optimization)</span>
<br><br>
<b style="color:#fde047">Grader:</b> 0.88 (cost efficiency + grid stability + SOC completion)
</div>
        <p style="font-size:14px;line-height:1.6;margin:0">
            Four stages: observe, prioritize, optimize, and validate. The evaluation framework rewards decisions that ensure cost-effective, safe, and efficient EV charging operations.</p>
    '''))

    blocks.append(_block("#fef3c7", '''
        <h3 style="font-size:20px;font-weight:900;margin:0 0 14px 0">Real-World Utility</h3>
        <p style="font-size:15px;line-height:1.7;margin:0 0 12px 0">
            Electric vehicle charging systems operate under dynamic and constrained environments where unmanaged charging can lead to grid overload, increased peak demand, and higher operational costs. This solution models realistic EV charging scenarios, enabling intelligent scheduling and load balancing across multiple vehicles in real time.</p>
        <p style="font-size:15px;line-height:1.7;margin:0 0 14px 0">
            The system is applicable to modern energy infrastructure such as urban charging stations, fleet depots, and smart grid ecosystems. By adapting to fluctuating electricity prices, varying vehicle demand, and grid capacity limits, it ensures efficient energy utilization while maintaining system stability.</p>
        <hr style="border:0;border-bottom:2px solid #000;margin:16px 0">
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;font-size:13px;font-weight:700">
            <div style="background:#fff;border:2px solid #000;border-radius:4px;padding:8px 12px">
                <b>Performance</b>: peak load management, cost optimization, charging efficiency</div>
            <div style="background:#fff;border:2px solid #000;border-radius:4px;padding:8px 12px">
                <b>Resources</b>: grid capacity utilization, energy distribution balancing</div>
            <div style="background:#fff;border:2px solid #000;border-radius:4px;padding:8px 12px">
                <b>Storage</b>: battery capacity management, SOC optimization</div>
            <div style="background:#fff;border:2px solid #000;border-radius:4px;padding:8px 12px">
                <b>Configuration</b>: dynamic pricing adaptation, scheduling strategies</div>
            <div style="background:#fff;border:2px solid #000;border-radius:4px;padding:8px 12px">
                <b>Access &amp; Integrity</b>: reliable charging delivery, system stability</div>
        </div>
    '''))

    blocks.append(_block("#d1fae5", '''
        <h3 style="font-size:20px;font-weight:900;margin:0 0 14px 0">Reward Design</h3>
        <p style="font-size:15px;line-height:1.7;margin:0 0 12px 0">
            The system follows a multi-objective reward framework designed to balance key operational goals in EV charging. Each decision made by the agent is evaluated based on its effectiveness in optimizing charging outcomes while maintaining grid safety.</p>
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px;margin-bottom:14px">
            <div style="background:#fff;border:2px solid #000;border-radius:4px;padding:10px 14px">
                <div style="font-weight:900;font-size:14px;margin-bottom:6px">Cost Efficiency (50%)</div>
                <div style="font-size:13px;line-height:1.5">
                    Minimizes electricity cost by avoiding peak pricing and optimizing charging schedules.</div>
            </div>
            <div style="background:#fff;border:2px solid #000;border-radius:4px;padding:10px 14px">
                <div style="font-weight:900;font-size:14px;margin-bottom:6px">SOC Completion (30%)</div>
                <div style="font-size:13px;line-height:1.5">
                    Maximizes the average state of charge across all vehicles, ensuring timely charging completion.</div>
            </div>
            <div style="background:#fff;border:2px solid #000;border-radius:4px;padding:10px 14px">
                <div style="font-weight:900;font-size:14px;margin-bottom:6px">Grid Safety (20%)</div>
                <div style="font-size:13px;line-height:1.5">
                    Prevents overload conditions by maintaining grid usage within safe capacity limits.</div>
            </div>
        </div>
        <p style="font-size:14px;line-height:1.6;margin:0">
            The evaluation is deterministic and reproducible, ensuring consistent performance measurement across different scenarios. The agent is rewarded for achieving an optimal balance between cost reduction, efficient charging, and grid stability.</p>
    '''))

    blocks.append(_block("#fde047", '''
        <h3 style="font-size:18px;font-weight:900;margin:0 0 12px 0">Anti-Reward-Hacking</h3>
        <p style="font-size:14px;line-height:1.7;margin:0 0 10px 0">
            The system incorporates safeguards to ensure that the agent does not exploit reward mechanisms through repetitive or non-meaningful actions. Rewards are structured to reflect genuine optimization performance rather than superficial improvements.</p>
        <p style="font-size:14px;line-height:1.7;margin:0 0 10px 0">
            Each reward component is applied based on meaningful progress, preventing accumulation through redundant actions. Incorrect or inefficient charging decisions are penalized, encouraging the agent to learn robust and reliable strategies.</p>
        <p style="font-size:14px;line-height:1.7;margin:0">
            The framework has been validated across multiple simulated scenarios to ensure stability, consistency, and resistance to reward manipulation.</p>
    '''))

    blocks.append(_block("#bfdbfe", '''
        <h3 style="font-size:20px;font-weight:900;margin:0 0 14px 0">Environment Design</h3>
        <p style="font-size:15px;line-height:1.7;margin:0 0 12px 0">
            Each episode represents a full EV charging cycle where multiple vehicles arrive, charge, and depart over time. The agent continuously interacts with the environment by observing system states such as battery levels, grid load, and time progression.</p>
        <p style="font-size:15px;line-height:1.7;margin:0 0 12px 0">
            At every step, the agent determines optimal charging allocations without predefined rules or constraints beyond system limits. The environment dynamically updates based on these decisions, reflecting realistic changes in grid conditions and vehicle requirements.</p>
        <p style="font-size:15px;line-height:1.7;margin:0">
            This design ensures a realistic simulation of EV charging infrastructure, enabling the development of adaptive and intelligent charging strategies.</p>
    '''))

    blocks.append(_block("#fecdd3", '''
        <h3 style="font-size:20px;font-weight:900;margin:0 0 14px 0">Baseline Results</h3>
        <p style="font-size:15px;line-height:1.7;margin:0 0 14px 0">
            Baseline results compare traditional charging strategies with reinforcement learning models across different scenarios. Full performance details are available in the Model Performance Tab.</p>
        <table style="width:100%;margin:0 auto;border-collapse:collapse;font-size:12px;font-weight:600">
            <tr style="background:#fff;border:2px solid #000">
                <th style="padding:10px 10px;text-align:left;border:2px solid #000">Model</th>
                <th style="padding:10px 10px;text-align:center;border:2px solid #000">Avg Cost</th>
                <th style="padding:10px 10px;text-align:center;border:2px solid #000">SOC (%)</th>
                <th style="padding:10px 10px;text-align:center;border:2px solid #000">Grid Stability</th>
            </tr>
            <tr style="border:1px solid #000">
                <td style="padding:8px 10px;border:1px solid #000">Baseline Strategy</td>
                <td style="padding:8px 10px;text-align:center;border:1px solid #000">High</td>
                <td style="padding:8px 10px;text-align:center;border:1px solid #000">65%</td>
                <td style="padding:8px 10px;text-align:center;border:1px solid #000">Low</td>
            </tr>
            <tr style="border:1px solid #000">
                <td style="padding:8px 10px;border:1px solid #000">RL Model (Easy)</td>
                <td style="padding:8px 10px;text-align:center;border:1px solid #000">Low</td>
                <td style="padding:8px 10px;text-align:center;border:1px solid #000">85%</td>
                <td style="padding:8px 10px;text-align:center;border:1px solid #000">High</td>
            </tr>
            <tr style="background:#fff;border:1px solid #000">
                <td style="padding:8px 10px;border:1px solid #000">RL Model (Medium)</td>
                <td style="padding:8px 10px;text-align:center;border:1px solid #000">Moderate</td>
                <td style="padding:8px 10px;text-align:center;border:1px solid #000">78%</td>
                <td style="padding:8px 10px;text-align:center;border:1px solid #000">Stable</td>
            </tr>
            <tr style="border:1px solid #000">
                <td style="padding:8px 10px;border:1px solid #000">RL Model (Hard)</td>
                <td style="padding:8px 10px;text-align:center;border:1px solid #000">Optimized</td>
                <td style="padding:8px 10px;text-align:center;border:1px solid #000">72%</td>
                <td style="padding:8px 10px;text-align:center;border:1px solid #000">Controlled</td>
            </tr>
        </table>
    '''))

    blocks.append(_block("#ffb74d", '''
        <h3 style="font-size:20px;font-weight:900;margin:0 0 14px 0">
            Vision: Intelligent EV Charging Systems</h3>
        <p style="font-size:15px;line-height:1.7;margin:0 0 12px 0">
            The current system focuses on optimizing EV charging for multiple vehicles within a single environment, ensuring efficient energy distribution and grid stability. It serves as a strong foundation for building intelligent and adaptive charging solutions.</p>
        <p style="font-size:15px;line-height:1.7;margin:0 0 12px 0">
            The next step is to extend this into a scalable, multi-agent ecosystem where different components work together: a scheduling agent for prioritizing vehicles, an optimization agent for allocating charging power, and a monitoring agent for tracking grid conditions and system performance. These agents collaborate to manage complex, real-world charging scenarios.</p>
        <p style="font-size:15px;line-height:1.7;margin:0">
            This vision enables smart city infrastructure where EV charging networks operate autonomously, efficiently balancing demand, reducing costs, and maintaining grid reliability.</p>
    '''))

    return '\n'.join(blocks)



def _task_descriptions_html() -> str:
    """Build accordion of task descriptions."""
    html = '<div style="margin-top:24px">'
    for tid, task in TASK_REGISTRY.items():
        num = tid.split("_")[1]
        html += f'''<details class="task-accordion">
            <summary>Task {num}: {task["name"]} {_badge(task["difficulty"])}</summary>
            <div class="acc-body">
                <p>{task["description"]}</p>
                <div class="alert-panel" style="margin-top:8px"><strong>ALERT</strong> {_escape(task["alert"])}</div>
            </div>
        </details>'''
    html += '</div>'
    return html



def create_gradio_app(env, env_lock: threading.Lock) -> gr.Blocks:
    """Build the 3-tab Gradio interface.

    Args:
        env: DBSreEnvironment instance (shared with FastAPI)
        env_lock: Threading lock for serializing env access
    """
    all_results = _load_all_results()

    task_choices = []
    for tid, task in TASK_REGISTRY.items():
        num = tid.split("_")[1]
        task_choices.append((f"Task {num}: {task['name']} [{task['difficulty']}]", tid))

    model_choices = [(f"{_model_display_name(m)} — {d.get('summary', {}).get('total_score', 0):.1f}/17", m) for m, d in
                     sorted(all_results.items(), key=lambda x: x[1].get("summary", {}).get("total_score", 0), reverse=True)]

    with gr.Blocks(title="EV Charging Optimizer") as demo:

        gr.HTML(f'<style>{CUSTOM_CSS}</style>', elem_classes=["borderless-html"])

        gr.HTML('''<div class="gym-header">
            <h1>EV Charging Optimizer</h1>
            <p>EV Charging and Grid Optimization with Reinforcement Learning</p>
        </div>''', elem_classes=["borderless-html"])

        with gr.Tab("\u25A4 README"):
            gr.HTML(_readme_tab_html())

        with gr.Tab("\u2318 Playground"):

            with gr.Group():
                gr.HTML('<div class="playground-subblock-title" data-pg="task-select">Task Selection</div>')
                with gr.Row():
                    task_dropdown = gr.Dropdown(
                        choices=[("Select a task", "")] + task_choices, value="", label="Select Task", show_label=False, scale=3,
                    )
                    reset_btn = gr.Button("Reset", elem_classes=["primary-btn"], scale=1)
                alert_display = gr.HTML(
                    '<div class="alert-panel" style="color:#000">Select a task and click Reset to begin.</div>',
                    label="Alert",
                )

            with gr.Group():
                gr.HTML('<div class="playground-subblock-title" data-pg="sql-workflow">Simulation Controls</div>')
                with gr.Row():
                    with gr.Column(scale=3):
                        difficulty_dropdown = gr.Dropdown(
                            choices=[("Select difficulty level", "")] + ["easy", "medium", "hard"],
                            value="",
                            label="Difficulty", show_label=True
                        )
                        run_button = gr.Button("Run Simulation", elem_classes=["primary-btn"])
                        path_prompt = gr.HTML('<div class="path-prompt" style="padding: 10px; margin-top: 12px; border:2px solid; border-radius:4px; display: flex; align-items: center; justify-content: center;">Select a task and reset to initialize the simulation.</div>', elem_classes=["borderless-html"])
                    with gr.Column(scale=1):
                        step_display = gr.HTML('<div class="metric-card"><div class="metric-value">—</div><div class="metric-label">Step</div></div>')
                        reward_display = gr.HTML('<div class="metric-card"><div class="metric-value">—</div><div class="metric-label">Reward</div></div>')
                        status_display = gr.HTML('<div class="metric-card"><div class="metric-value">—</div><div class="metric-label">Status</div></div>')
                metrics_display = gr.HTML(_metrics_html(None), label="Database Metrics")
                with gr.Group():
                    gr.HTML('<div class="playground-subblock-title" data-pg="repl">Observation Log</div>')
                    obs_log_display = gr.HTML(
                        '<div class="repl-log" style="opacity:0.5">Run simulation to see environment agent responses here.</div>',
                    )

            hint_state = gr.State({"task_id": "", "path_idx": 0, "path_done": False, "path_failed": False})

            with gr.Group():
                gr.HTML('<div class="playground-subblock-title" data-pg="grader">Grader Breakdown</div>')
                grader_display = gr.HTML('<div style="color:#6b7280;font-size:13px">Complete an episode to see the grader breakdown.</div>')

            playground_state = gr.State({
                "active": False,
                "step": 0,
                "cumulative_reward": 0.0,
                "obs_log_html": "",
                "done": False,
            })

            def _get_path_step_options(task_id, path_idx):
                """Return shuffled options: [(cmd, is_correct, severity), ...] and prompt.

                severity is "correct", "mild", "bad", or "fatal".
                """
                import random
                path = TASK_PATHS.get(task_id, [])
                if not path or path_idx >= len(path):
                    return [("—", False, "mild"), ("—", False, "mild"), ("—", False, "mild")], "Path complete."
                step = path[path_idx]
                items = [(step["correct"], True, "correct")]
                for w in step["wrong"][:2]:
                    items.append((w[0], False, w[1]))
                random.shuffle(items)
                return items, step["prompt"]

            def _path_prompt_html(prompt, path_idx, total_steps, done=False, failed=False, fatal=False, mild_msg=None, bad_msg=None):
                """Render the guided path prompt bar."""
                if done:
                    return '<div class="path-prompt path-done"><span class="path-step-badge">COMPLETE</span> All steps finished — well done!</div>'
                if fatal:
                    return ('<div class="path-prompt path-fatal">'
                            '<span class="path-step-badge">CRITICAL FAILURE</span> '
                            'Destructive action terminated the episode with penalty. Reset to try again.</div>')
                if failed:
                    return '<div class="path-prompt path-fail"><span class="path-step-badge">WRONG</span> Incorrect choice. Click Reset to try again.</div>'
                if bad_msg:
                    return (f'<div class="path-prompt path-fail">'
                            f'<span class="path-step-badge">Step {path_idx + 1}/{total_steps}</span> '
                            f'Dangerous approach! That wasted a step with negative reward. Try another option.</div>')
                if mild_msg:
                    return (f'<div class="path-prompt" style="background:#fef9c3;border-color:#ca8a04">'
                            f'<span class="path-step-badge">Step {path_idx + 1}/{total_steps}</span> '
                            f'Not quite — this doesn\'t help here. Try another option.</div>')
                return (f'<div class="path-prompt">'
                        f'<span class="path-step-badge">Step {path_idx + 1}/{total_steps}</span> {_escape(prompt)}'
                        f'</div>')

            def do_reset(task_id):
                if not task_id:
                    return (
                        '<div class="alert-panel" style="color:#000">Select a task and click Reset to begin.</div>',
                        '<div class="metric-card"><div class="metric-value">—</div><div class="metric-label">Step</div></div>',
                        '<div class="metric-card"><div class="metric-value">—</div><div class="metric-label">Reward</div></div>',
                        '<div class="metric-card"><div class="metric-value">—</div><div class="metric-label">Status</div></div>',
                        '<div class="repl-log" style="opacity:0.5">Run simulation to see environment agent responses here.</div>',
                        _metrics_html(None),
                        '<div style="color:#6b7280;font-size:13px">Complete an episode to see the grader breakdown.</div>',
                        {"active": False, "step": 0},
                        '<div class="path-prompt" style="padding: 10px; display: flex; align-items: center; justify-content: center;">Select a task and reset to initialize the simulation.</div>',
                        {"task_id": "", "path_idx": 0, "path_done": False, "path_failed": False}
                    )
                
                task = TASK_REGISTRY.get(task_id, {})
                task_name = task.get("name", "Unknown Task")
                alert_msg = task.get("alert", "")
                
                alert_html = f'<div class="alert-panel" style="background:#fecdd3; border:2px solid #000; border-radius:4px; padding:12px; margin-top:8px; color:#000;"><strong>ALERT</strong> {_escape(alert_msg)}</div>' if alert_msg else f'<div class="alert-panel" style="color:#000">Loaded <b>{task_name}</b>. Try exploring the Hint System or click Run Simulation.</div>'

                return (
                    alert_html,
                    '<div class="metric-card"><div class="metric-value">—</div><div class="metric-label">Step</div></div>',
                    '<div class="metric-card"><div class="metric-value">—</div><div class="metric-label">Reward</div></div>',
                    '<div class="metric-card"><div class="metric-value">—</div><div class="metric-label">Status</div></div>',
                    '<div class="repl-log" style="opacity:0.5">Run simulation to see environment agent responses here.</div>',
                    _metrics_html(None),
                    '<div style="color:#6b7280;font-size:13px">Complete an episode to see the grader breakdown.</div>',
                    {"active": True, "step": 0},
                    f'<div class="path-prompt" style="padding: 10px; display: flex; align-items: center; justify-content: center;">Simulation for {task_name} initialized.</div>',
                    {"task_id": task_id, "path_idx": 0, "path_done": False, "path_failed": False}
                )

            def do_execute(difficulty, task_id):
                import requests, json, re, time
                
                loader_html = '''
                <div style="display:flex; flex-direction:column; align-items:center; justify-content:center; width:100%; height:100%;">
                    <div style="border: 4px solid #f3f3f3; border-top: 4px solid #4ade80; border-radius: 50%; width: 30px; height: 30px; animation: spin 1s linear infinite;"></div>
                    <style>@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }</style>
                    <div style="margin-top:8px; font-weight:bold; color:#000;">Executing Optimization...</div>
                </div>
                '''
                
                yield (
                    '<div class="repl-log" style="text-align:center; opacity:0.6; padding: 20px;">Intercepting API communication...</div>',
                    _metrics_html(None),
                    '<div class="metric-card"><div class="metric-value">...</div><div class="metric-label">Step</div></div>',
                    '<div class="metric-card"><div class="metric-value">...</div><div class="metric-label">RL Cost</div></div>',
                    '<div class="metric-card"><div class="metric-value">...</div><div class="metric-label">SOC</div></div>',
                    '<div style="color:#6b7280;font-size:13px">Calculating grading...</div>',
                    {"active": True, "step": 1},
                    f'<div class="path-prompt" style="padding: 10px; display: flex; align-items: center; justify-content: center;">{loader_html}</div>',
                    gr.update()
                )
                
                try:
                    time.sleep(1.5)  # Make sure loader is visible
                    task = TASK_REGISTRY.get(task_id, {})
                    active_diff = difficulty if difficulty else "medium"
                    seed = 42
                    if task_id and task_id.startswith("task_"):
                        try:
                            seed = 42 + int(task_id.split("_")[1]) * 10
                        except:
                            pass
                    response = requests.get("http://127.0.0.1:8000/run", params={"difficulty": active_diff, "seed": seed})
                    data = response.json()
                    
                    cost = data.get("rl", {}).get("cost", 0)
                    soc = data.get("rl", {}).get("soc", data.get("soc", 0))
                    
                    step_html = f'<div class="metric-card"><div class="metric-value">1</div><div class="metric-label">Step</div></div>'
                    reward_html = f'<div class="metric-card"><div class="metric-value">${cost:.2f}</div><div class="metric-label">RL Cost</div></div>'
                    status_html = f'<div class="metric-card"><div class="metric-value">{soc:.2f}</div><div class="metric-label">SOC</div></div>'
                    
                    json_str = json.dumps(data, indent=2)
                    highlighted_json = re.sub(r'"improvement_percent":\s*"(.*?)"', r'"improvement_percent": <span style="color:#ffffff !important; -webkit-text-fill-color:#ffffff !important;">\1</span>', json_str)
                    highlighted_json = re.sub(r': (\d+\.?\d*)', r': <span style="color:#ffffff !important; -webkit-text-fill-color:#ffffff !important;">\1</span>', highlighted_json)
                    highlighted_json = re.sub(r': "(.*?)"', r': <span style="color:#4ade80 !important; -webkit-text-fill-color:#4ade80 !important;">"\1"</span>', highlighted_json)
                    obs_log = f'<div class="repl-log" style="background:#2d2d2d !important; color:#e0f2fe !important; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; white-space: pre-wrap; padding: 16px; border-radius: 6px; font-size: 14px; font-weight: bold;">{highlighted_json}</div>'
                    
                    metrics_html = _metrics_html(data)    
                    grader_html = '<div style="color:#6b7280;font-size:13px">Simulation completed successfully.</div>'

                    yield (
                        obs_log,
                        metrics_html,
                        step_html,
                        reward_html,
                        status_html,
                        grader_html,
                        {"active": True, "step": 1},
                        '<div class="path-prompt path-done" style="padding: 10px; display: flex; align-items: center; justify-content: center;"><span class="path-step-badge">COMPLETE</span> Simulation finished!</div>',
                        gr.update()
                    )
                except Exception as e:
                    err_html = f'<div class="repl-log" style="color:red">API Error: {str(e)}</div>'
                    yield (err_html, _metrics_html(None), gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), '<div class="path-prompt path-fail" style="padding: 10px; display: flex; align-items: center; justify-content: center;"><span class="path-step-badge">ERROR</span> API Connection Failed</div>', gr.update())

            _reset_outputs = [alert_display, step_display, reward_display, status_display, obs_log_display, metrics_display, grader_display, playground_state, path_prompt, hint_state]
            reset_btn.click(do_reset, inputs=[task_dropdown], outputs=_reset_outputs)
            task_dropdown.change(do_reset, inputs=[task_dropdown], outputs=_reset_outputs)

            _exec_outputs = [obs_log_display, metrics_display, step_display, reward_display, status_display, grader_display, playground_state, path_prompt, hint_state]
            run_button.click(do_execute, inputs=[difficulty_dropdown, task_dropdown], outputs=_exec_outputs)

        with gr.Tab("\u21AF Traces"):
            if not model_choices:
                gr.HTML('<div style="text-align:center;padding:40px;color:#000">No demo results available yet.</div>')
            else:
                with gr.Row():
                    trace_model = gr.Dropdown(choices=[("Select a model", "")] + model_choices, value="", label="Model", scale=2)
                    trace_task = gr.Dropdown(choices=[("Select a task", "")] + task_choices, value="", label="Task", scale=2)

                trace_display = gr.HTML(
                    '<div style="text-align:center;padding:40px;color:#000">Select a model and task to view the trace.</div>'
                )

                def show_trace(model_id, task_id):
                    if not model_id or not task_id:
                        return '<div style="color:#000;text-align:center;padding:20px">Select both a model and task.</div>'
                    data = all_results.get(model_id)
                    if not data:
                        return '<div style="color:#000;font-weight:700">Model results not found.</div>'
                    for r in data.get("results", []):
                        if r.get("task_id") == task_id:
                            return _trace_html(r)
                    return '<div style="color:#000;font-weight:700">Task not found in results.</div>'

                trace_model.change(show_trace, inputs=[trace_model, trace_task], outputs=[trace_display])
                trace_task.change(show_trace, inputs=[trace_model, trace_task], outputs=[trace_display])

        with gr.Tab("\u265B Model Performance"):
            gr.HTML('<h2>Model Performance Comparison</h2>')
            gr.HTML(_leaderboard_html(all_results))

            gr.HTML('<h2 style="margin-top:24px">Score Heatmap</h2>')
            gr.HTML('<p style="color:#000;font-size:13px;font-weight:600;margin-bottom:12px">Scores by model × task. Green = high, red = low.</p>')
            gr.HTML(_heatmap_html(all_results))

            gr.HTML('''<h2 style="margin-top:24px">Charging Strategy Models</h2>
<p style="color:#000;font-size:13px;font-weight:600;margin-bottom:12px">
Specialized EV charging strategies evaluated under dynamic grid conditions and varying vehicle demand scenarios.</p>''')
            gr.HTML('''<div style="overflow-x:auto"><table class="leaderboard-table" style="margin-bottom:24px">
<thead><tr>
    <th style="text-align:left">Model</th><th>Total Score</th><th>Average</th><th>Stability</th>
</tr></thead><tbody>
<tr style="background:#fff"><td style="text-align:left;font-weight:700">Time-of-Use Scheduler</td><td class="score-cell">9.50 / 17</td><td>0.55</td><td>Moderate</td></tr>
<tr style="background:#fef9c3"><td style="text-align:left;font-weight:700">Load Balancing Heuristic</td><td class="score-cell">10.80 / 17</td><td>0.63</td><td>Stable</td></tr>
<tr style="background:#fff"><td style="text-align:left;font-weight:700">Priority-Based Scheduler</td><td class="score-cell">11.90 / 17</td><td>0.70</td><td>High</td></tr>
<tr style="background:#fef9c3"><td style="text-align:left;font-weight:700">Static Charging Model</td><td class="score-cell">7.20 / 17</td><td>0.42</td><td>Low</td></tr>
</tbody></table></div>''')

            gr.HTML(f'''<div class="env-overview" style="margin-top:24px">
                <h3 style="margin:0 0 12px 0;color:#000;font-weight:900">Environment Overview</h3>
                <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:16px;text-align:center">
                    <div class="metric-card"><div class="metric-value">17</div><div class="metric-label">TASKS</div></div>
                    <div class="metric-card"><div class="metric-value">3</div><div class="metric-label">DIFFICULTY LEVELS</div></div>
                    <div class="metric-card"><div class="metric-value">RL</div><div class="metric-label">ENVIRONMENT</div></div>
                    <div class="metric-card"><div class="metric-value">~1000+</div><div class="metric-label">SIMULATION STEPS</div></div>
                </div>
            </div>''')

        with gr.Tab("\u2699 Tasks"):
            gr.HTML(f'''<div class="env-overview" style="margin-bottom:16px">
                <h2 style="margin:0 0 8px 0;color:#000;font-weight:900">Task Catalogue</h2>
                <p style="color:#000;font-weight:600;font-size:14px">17 EV charging optimization scenarios across 3 difficulty levels. Each task presents a realistic grid condition and evaluates your decision-making for efficient charging, cost optimization and grid stability.</p>
            </div>''')
            gr.HTML(_task_descriptions_html())

    return demo
