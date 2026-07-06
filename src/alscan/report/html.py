from __future__ import annotations

from jinja2 import Environment, PackageLoader, select_autoescape

from alscan.models import ScanResult


def generate_html_report(result: ScanResult) -> str:
    env = Environment(
        loader=PackageLoader("alscan", "report/templates"),
        autoescape=select_autoescape(["html", "xml"]),
    )

    try:
        template = env.get_template("report.html")
    except Exception:
        template = env.from_string(FALLBACK_TEMPLATE)

    proj = result.project
    track_counts = {}
    for tt in ("audio", "midi", "group", "return", "master"):
        track_counts[tt] = len([t for t in proj.tracks if t.track_type == tt])

    return template.render(
        project=proj,
        result=result,
        findings=result.findings,
        errors=result.errors,
        warnings=result.warnings,
        infos=result.info,
        track_counts=track_counts,
        version="0.1.0",
    )


FALLBACK_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>alscan - {{ project.file_path.name if project.file_path else 'Project Scan' }}</title>
<style>
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#1a1a2e;color:#e0e0e0;margin:0;padding:20px}
h1{color:#e94560}
.summary{display:flex;gap:16px;margin:16px 0}
.stat{padding:12px 20px;border-radius:8px;font-size:18px}
.stat-error{background:#4a1a2e;color:#ff6b6b}
.stat-warning{background:#4a3a1a;color:#ffd93d}
.stat-info{background:#1a2a4a;color:#6bcbff}
table{width:100%;border-collapse:collapse;margin:16px 0}
th,td{text-align:left;padding:8px 12px;border-bottom:1px solid #333}
th{color:#e94560}
.severity-error{color:#ff6b6b;font-weight:bold}
.severity-warning{color:#ffd93d;font-weight:bold}
.severity-info{color:#6bcbff}
.finding{margin:8px 0;padding:12px;border-radius:6px;background:#16213e}
.finding .title{font-weight:bold}
.finding .message{margin:4px 0}
.finding .meta{font-size:0.85em;color:#888}
hr{border:none;border-top:1px solid #333}
</style>
</head>
<body>
<h1>alscan</h1>
<p><strong>{{ project.file_path.name if project.file_path else 'Unknown' }}</strong> - {{ project.creator }} - {{ project.tempo }} BPM - {{ project.time_signature[0] }}/{{ project.time_signature[1] }}</p>
<div class="summary">
  <div class="stat stat-error">{{ errors|length }} Errors</div>
  <div class="stat stat-warning">{{ warnings|length }} Warnings</div>
  <div class="stat stat-info">{{ infos|length }} Info</div>
</div>
<hr>
<h2>Findings</h2>
{% if findings %}
{% for f in findings %}
<div class="finding">
  <div class="title severity-{{ f.severity }}">[{{ f.severity|upper }}] {{ f.title }}</div>
  <div class="message">{{ f.message }}</div>
  {% if f.location %}<div class="meta">Location: {{ f.location }}</div>{% endif %}
  {% if f.suggestion %}<div class="meta">Suggestion: {{ f.suggestion }}</div>{% endif %}
  {% if f.file_path %}<div class="meta">File: {{ f.file_path }}</div>{% endif %}
</div>
{% endfor %}
{% else %}
<p>No issues found!</p>
{% endif %}
<hr>
<h2>Project Summary</h2>
<table>
  <tr><td>Tempo</td><td>{{ project.tempo }} BPM</td></tr>
  <tr><td>Time Signature</td><td>{{ project.time_signature[0] }}/{{ project.time_signature[1] }}</td></tr>
  <tr><td>Total Tracks</td><td>{{ project.tracks|length }}</td></tr>
  {% for tt, count in track_counts.items() %}
  <tr><td>{{ tt|capitalize }} Tracks</td><td>{{ count }}</td></tr>
  {% endfor %}
  <tr><td>Locators</td><td>{{ project.locators|length }}</td></tr>
</table>
<p style="color:#666;font-size:0.85em">Scan completed in {{ result.scan_time_ms }}ms - alscan v{{ version }}</p>
<p style="color:#555;font-size:0.75em">Report contains project metadata (track names, plugin paths). Review before sharing.</p>
</body>
</html>"""
