#!/usr/bin/env python3
"""
=============================================================================
CLAW AGENTS PROVISIONER — Assessment Web Wizard
=============================================================================
Multi-step web form that guides users through assessment creation.
Generates client-assessment.json and optionally auto-triggers deployment.

Steps:
  1. Company Info     — name, industry, team size, service package
  2. Use Case         — primary use cases, complexity, description
  3. Requirements     — channel, languages, data sensitivity, storage
  4. Budget           — monthly API budget, deployment method
  5. Review           — summary of all selections, submit

HTTP Endpoints:
  GET  /                      — Serve embedded HTML wizard
  GET  /api/wizard/platforms  — List 5 platforms with metadata
  POST /api/wizard/assess     — Validate form data, write client-assessment.json
  GET  /api/wizard/preview    — Run resolve.py on current assessment
  POST /api/wizard/deploy     — Trigger claw.sh deploy
  GET  /api/wizard/status     — Deployment status

Usage:
  python3 shared/claw_wizard.py --start --port 9098
  python3 shared/claw_wizard.py --stop

Python 3.8+ stdlib only (no external dependencies).
=============================================================================
Created by Mauro Tommasi — linkedin.com/in/maurotommasi
Apache 2.0 © 2026 Amenthyx
"""

import argparse
import json
import logging
import os
import signal
import subprocess
import sys
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from socketserver import ThreadingMixIn
from typing import Optional
from urllib.parse import parse_qs

from claw_auth import check_auth
from claw_metrics import MetricsCollector
from claw_ratelimit import RateLimiter


# ═══════════════════════════════════════════════════════════════════════════
#  Constants
# ═══════════════════════════════════════════════════════════════════════════

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PID_DIR = PROJECT_ROOT / "data" / "wizard"
PID_FILE = PID_DIR / "wizard.pid"
ASSESSMENT_OUTPUT = PROJECT_ROOT / "client-assessment.json"
DEFAULT_PORT = 9098

GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
BLUE = "\033[0;34m"
CYAN = "\033[0;36m"
BOLD = "\033[1m"
DIM = "\033[2m"
NC = "\033[0m"

PLATFORMS = [
    {"id": "zeroclaw", "name": "ZeroClaw", "language": "Rust",
     "memory": "512 MB", "port": 3100,
     "description": "High-performance minimal agent"},
    {"id": "nanoclaw", "name": "NanoClaw", "language": "TypeScript",
     "memory": "1 GB", "port": 3200,
     "description": "Claude-native with Docker-out-of-Docker"},
    {"id": "picoclaw", "name": "PicoClaw", "language": "Go",
     "memory": "128 MB", "port": 3300,
     "description": "Ultra-lightweight data agent"},
    {"id": "openclaw", "name": "OpenClaw", "language": "Node.js",
     "memory": "4 GB", "port": 3400,
     "description": "50+ integrations, maximum extensibility"},
    {"id": "parlant", "name": "Parlant", "language": "Python",
     "memory": "2 GB", "port": 8800,
     "description": "Guidelines-driven with MCP support"},
]

REQUIRED_FIELDS = {
    "company_name", "industry", "team_size", "service_package",
    "complexity_level", "primary_channel", "monthly_api_budget",
    "deployment_method",
}


# ═══════════════════════════════════════════════════════════════════════════
#  Logging
# ═══════════════════════════════════════════════════════════════════════════

logger = logging.getLogger("claw-wizard")


def setup_logging():
    fmt = logging.Formatter(
        "%(asctime)s  %(levelname)-5s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger.setLevel(logging.INFO)
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    logger.addHandler(console)


# ═══════════════════════════════════════════════════════════════════════════
#  Deployment State
# ═══════════════════════════════════════════════════════════════════════════

_deploy_state = {
    "status": "idle",
    "message": "",
    "started_at": "",
    "finished_at": "",
}
_deploy_lock = threading.Lock()


# ═══════════════════════════════════════════════════════════════════════════
#  Validation
# ═══════════════════════════════════════════════════════════════════════════

def validate_assessment(data: dict) -> list:
    """Validate form data and return list of error strings (empty = valid)."""
    errors = []

    for field in REQUIRED_FIELDS:
        val = data.get(field)
        if val is None or (isinstance(val, str) and not val.strip()):
            errors.append(f"Missing required field: {field}")

    valid_industries = [
        "technology", "healthcare", "finance", "real-estate", "education",
        "retail", "hospitality", "legal", "manufacturing", "other",
    ]
    if data.get("industry") and data["industry"] not in valid_industries:
        errors.append(f"Invalid industry: {data['industry']}")

    valid_packages = ["starter", "professional", "enterprise"]
    if data.get("service_package") and data["service_package"] not in valid_packages:
        errors.append(f"Invalid service_package: {data['service_package']}")

    valid_complexity = ["simple", "moderate", "expert"]
    if data.get("complexity_level") and data["complexity_level"] not in valid_complexity:
        errors.append(f"Invalid complexity_level: {data['complexity_level']}")

    valid_channels = ["web", "whatsapp", "telegram", "discord", "slack", "email"]
    if data.get("primary_channel") and data["primary_channel"] not in valid_channels:
        errors.append(f"Invalid primary_channel: {data['primary_channel']}")

    valid_sensitivity = ["low", "medium", "high", "critical"]
    if data.get("data_sensitivity") and data["data_sensitivity"] not in valid_sensitivity:
        errors.append(f"Invalid data_sensitivity: {data['data_sensitivity']}")

    valid_methods = ["docker", "vagrant"]
    if data.get("deployment_method") and data["deployment_method"] not in valid_methods:
        errors.append(f"Invalid deployment_method: {data['deployment_method']}")

    budget = data.get("monthly_api_budget")
    if budget is not None:
        try:
            b = float(budget)
            if b < 0:
                errors.append("monthly_api_budget cannot be negative")
        except (ValueError, TypeError):
            errors.append("monthly_api_budget must be a number")

    return errors


def build_assessment_json(data: dict) -> dict:
    """Transform flat form data into the assessment JSON schema."""
    use_cases = data.get("primary_use_cases", [])
    if isinstance(use_cases, str):
        use_cases = [u.strip() for u in use_cases.split(",") if u.strip()]

    languages = data.get("languages", [])
    if isinstance(languages, str):
        languages = [l.strip() for l in languages.split(",") if l.strip()]
    if not languages:
        languages = ["en"]

    budget_val = 0
    try:
        budget_val = int(float(data.get("monthly_api_budget", 0)))
    except (ValueError, TypeError):
        pass

    return {
        "client_profile": {
            "company_name": data.get("company_name", "").strip(),
            "industry": data.get("industry", "other"),
            "team_size": data.get("team_size", "1"),
            "service_package": data.get("service_package", "starter"),
        },
        "use_cases": {
            "primary_use_cases": use_cases,
            "complexity_level": data.get("complexity_level", "moderate"),
            "description": data.get("description", ""),
        },
        "channels": {
            "primary_channel": data.get("primary_channel", "web"),
        },
        "communication_preferences": {
            "languages": languages,
            "primary_language": languages[0] if languages else "en",
        },
        "data_privacy": {
            "sensitivity": data.get("data_sensitivity", "low"),
            "storage_preference": data.get("storage_preference", "any-cloud"),
        },
        "budget": {
            "monthly_api_budget": budget_val,
        },
        "infrastructure": {
            "deployment_method": data.get("deployment_method", "docker"),
        },
    }


# ═══════════════════════════════════════════════════════════════════════════
#  Resolve Integration
# ═══════════════════════════════════════════════════════════════════════════

def run_resolve_preview() -> dict:
    """Run resolve.py on the current client-assessment.json."""
    if not ASSESSMENT_OUTPUT.exists():
        return {"error": "No client-assessment.json found. Submit the wizard first."}

    resolve_path = PROJECT_ROOT / "assessment" / "resolve.py"
    if not resolve_path.exists():
        return {"error": "resolve.py not found in assessment/ directory."}

    # Import resolve.py dynamically
    resolve_dir = str(resolve_path.parent)
    if resolve_dir not in sys.path:
        sys.path.insert(0, resolve_dir)

    try:
        import importlib
        spec = importlib.util.spec_from_file_location("resolve", str(resolve_path))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        with open(ASSESSMENT_OUTPUT, "r", encoding="utf-8") as f:
            assessment = json.load(f)

        result = mod.resolve_assessment(assessment, verbose=True)
        return result.to_dict()
    except (ImportError, AttributeError, json.JSONDecodeError,
            OSError, ValueError, TypeError, RuntimeError) as e:
        return {"error": f"Resolution failed: {e}"}


# ═══════════════════════════════════════════════════════════════════════════
#  Deploy Integration
# ═══════════════════════════════════════════════════════════════════════════

def trigger_deploy():
    """Trigger claw.sh deploy in a background thread."""
    global _deploy_state
    import datetime

    with _deploy_lock:
        if _deploy_state["status"] == "running":
            return
        _deploy_state["status"] = "running"
        _deploy_state["message"] = "Deployment started"
        _deploy_state["started_at"] = datetime.datetime.now(
            datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        _deploy_state["finished_at"] = ""

    def _run():
        global _deploy_state
        import datetime as dt
        claw_sh = PROJECT_ROOT / "claw.sh"
        try:
            result = subprocess.run(
                ["bash", str(claw_sh), "deploy",
                 "--assessment", str(ASSESSMENT_OUTPUT)],
                capture_output=True, text=True, timeout=300,
                cwd=str(PROJECT_ROOT),
            )
            with _deploy_lock:
                _deploy_state["finished_at"] = dt.datetime.now(
                    dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                if result.returncode == 0:
                    _deploy_state["status"] = "success"
                    _deploy_state["message"] = result.stdout[-500:] if result.stdout else "Deployed"
                else:
                    _deploy_state["status"] = "failed"
                    _deploy_state["message"] = result.stderr[-500:] if result.stderr else "Deploy failed"
        except subprocess.TimeoutExpired:
            with _deploy_lock:
                _deploy_state["status"] = "failed"
                _deploy_state["message"] = "Deployment timed out (300s)"
        except (subprocess.SubprocessError, OSError) as e:
            with _deploy_lock:
                _deploy_state["status"] = "failed"
                _deploy_state["message"] = str(e)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()


# ═══════════════════════════════════════════════════════════════════════════
#  Embedded HTML
# ═══════════════════════════════════════════════════════════════════════════

WIZARD_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Claw Agents Provisioner — Assessment Wizard</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#0a0a0f;color:#e0e0e0;font-family:'Segoe UI',system-ui,sans-serif;min-height:100vh;display:flex;justify-content:center;padding:2rem 1rem}
.container{max-width:720px;width:100%}
h1{color:#00d4aa;font-size:1.6rem;text-align:center;margin-bottom:.3rem}
.subtitle{text-align:center;color:#888;font-size:.85rem;margin-bottom:2rem}
.steps{display:flex;justify-content:center;align-items:center;gap:0;margin-bottom:2rem}
.step-circle{width:36px;height:36px;border-radius:50%;border:2px solid #333;display:flex;align-items:center;justify-content:center;font-size:.85rem;font-weight:600;color:#555;transition:all .3s;flex-shrink:0}
.step-circle.active{border-color:#00d4aa;color:#00d4aa;box-shadow:0 0 12px rgba(0,212,170,.3)}
.step-circle.done{border-color:#00d4aa;background:#00d4aa;color:#0a0a0f}
.step-line{width:40px;height:2px;background:#333;transition:background .3s}
.step-line.done{background:#00d4aa}
fieldset{display:none;border:1px solid #1a1a2e;border-radius:12px;padding:2rem;background:#12121f;margin-bottom:1.5rem}
fieldset.active{display:block}
legend{color:#00d4aa;font-size:1.1rem;font-weight:600;padding:0 .5rem}
.field{margin-bottom:1.2rem}
.field label{display:block;color:#aaa;font-size:.85rem;margin-bottom:.4rem;font-weight:500}
.field input,.field select,.field textarea{width:100%;padding:.65rem .8rem;background:#1a1a2e;border:1px solid #2a2a40;border-radius:8px;color:#e0e0e0;font-size:.9rem;outline:none;transition:border-color .2s}
.field input:focus,.field select:focus,.field textarea:focus{border-color:#00d4aa}
.field textarea{resize:vertical;min-height:80px}
.field select{cursor:pointer}
.checkbox-group{display:flex;flex-wrap:wrap;gap:.6rem}
.checkbox-group label{display:flex;align-items:center;gap:.4rem;background:#1a1a2e;padding:.5rem .8rem;border-radius:8px;border:1px solid #2a2a40;cursor:pointer;font-size:.85rem;color:#ccc;transition:all .2s}
.checkbox-group label:hover{border-color:#00d4aa}
.checkbox-group input[type=checkbox]{accent-color:#00d4aa}
.checkbox-group input[type=checkbox]:checked+span{color:#00d4aa}
.btn-row{display:flex;justify-content:space-between;margin-top:1.5rem}
.btn{padding:.7rem 1.8rem;border-radius:8px;border:none;cursor:pointer;font-size:.9rem;font-weight:600;transition:all .2s}
.btn-next{background:#00d4aa;color:#0a0a0f}.btn-next:hover{background:#00e8bb}
.btn-back{background:#1a1a2e;color:#aaa;border:1px solid #333}.btn-back:hover{border-color:#00d4aa;color:#00d4aa}
.btn-submit{background:#00d4aa;color:#0a0a0f;padding:.8rem 2.5rem;font-size:1rem}.btn-submit:hover{background:#00e8bb}
.review-section{background:#1a1a2e;border-radius:8px;padding:1rem 1.2rem;margin-bottom:1rem;position:relative}
.review-section h3{color:#00d4aa;font-size:.9rem;margin-bottom:.6rem}
.review-section p{font-size:.85rem;color:#ccc;margin-bottom:.3rem}
.review-section .edit-btn{position:absolute;top:.8rem;right:1rem;background:none;border:1px solid #333;color:#aaa;padding:.25rem .6rem;border-radius:6px;cursor:pointer;font-size:.75rem}
.review-section .edit-btn:hover{border-color:#00d4aa;color:#00d4aa}
.msg{padding:1rem;border-radius:8px;margin-top:1rem;font-size:.9rem;display:none}
.msg.ok{display:block;background:#0a2922;border:1px solid #00d4aa;color:#00d4aa}
.msg.err{display:block;background:#2a0f0f;border:1px solid #ff4455;color:#ff6677}
.footer{text-align:center;color:#444;font-size:.75rem;margin-top:2rem}
</style>
</head>
<body>
<div class="container">
<h1>Claw Assessment Wizard</h1>
<p class="subtitle">Created by Mauro Tommasi &mdash; Apache 2.0 &copy; 2026 Amenthyx</p>

<div class="steps" id="stepIndicator">
  <div class="step-circle active" data-s="0">1</div><div class="step-line"></div>
  <div class="step-circle" data-s="1">2</div><div class="step-line"></div>
  <div class="step-circle" data-s="2">3</div><div class="step-line"></div>
  <div class="step-circle" data-s="3">4</div><div class="step-line"></div>
  <div class="step-circle" data-s="4">5</div>
</div>

<form id="wizardForm" autocomplete="off">

<!-- Step 1: Company Info -->
<fieldset class="active" data-step="0">
<legend>Company Info</legend>
<div class="field"><label>Company Name *</label><input type="text" name="company_name" required></div>
<div class="field"><label>Industry *</label>
<select name="industry" required>
<option value="">Select...</option>
<option value="technology">Technology</option><option value="healthcare">Healthcare</option>
<option value="finance">Finance</option><option value="real-estate">Real Estate</option>
<option value="education">Education</option><option value="retail">Retail</option>
<option value="hospitality">Hospitality</option><option value="legal">Legal</option>
<option value="manufacturing">Manufacturing</option><option value="other">Other</option>
</select></div>
<div class="field"><label>Team Size</label><input type="text" name="team_size" placeholder="e.g. 2-10" value="1-5"></div>
<div class="field"><label>Service Package *</label>
<select name="service_package" required>
<option value="starter">Starter</option><option value="professional">Professional</option>
<option value="enterprise">Enterprise</option>
</select></div>
</fieldset>

<!-- Step 2: Use Case -->
<fieldset data-step="1">
<legend>Use Case</legend>
<div class="field"><label>Primary Use Cases</label>
<div class="checkbox-group">
<label><input type="checkbox" name="primary_use_cases" value="customer-support"><span>Customer Support</span></label>
<label><input type="checkbox" name="primary_use_cases" value="sales-crm"><span>Sales / CRM</span></label>
<label><input type="checkbox" name="primary_use_cases" value="real-estate"><span>Real Estate</span></label>
<label><input type="checkbox" name="primary_use_cases" value="knowledge-base"><span>Knowledge Base</span></label>
<label><input type="checkbox" name="primary_use_cases" value="data-analysis"><span>Data Analysis</span></label>
<label><input type="checkbox" name="primary_use_cases" value="content-generation"><span>Content Generation</span></label>
<label><input type="checkbox" name="primary_use_cases" value="code-assistant"><span>Code Assistant</span></label>
<label><input type="checkbox" name="primary_use_cases" value="scheduling"><span>Scheduling</span></label>
</div></div>
<div class="field"><label>Complexity Level *</label>
<select name="complexity_level" required>
<option value="simple">Simple</option><option value="moderate" selected>Moderate</option>
<option value="expert">Expert</option>
</select></div>
<div class="field"><label>Description</label><textarea name="description" placeholder="Describe what you need the agent to do..."></textarea></div>
</fieldset>

<!-- Step 3: Requirements -->
<fieldset data-step="2">
<legend>Requirements</legend>
<div class="field"><label>Primary Channel *</label>
<select name="primary_channel" required>
<option value="web">Web Chat</option><option value="whatsapp">WhatsApp</option>
<option value="telegram">Telegram</option><option value="discord">Discord</option>
<option value="slack">Slack</option><option value="email">Email</option>
</select></div>
<div class="field"><label>Languages</label>
<div class="checkbox-group">
<label><input type="checkbox" name="languages" value="en" checked><span>English</span></label>
<label><input type="checkbox" name="languages" value="it"><span>Italian</span></label>
<label><input type="checkbox" name="languages" value="es"><span>Spanish</span></label>
<label><input type="checkbox" name="languages" value="fr"><span>French</span></label>
<label><input type="checkbox" name="languages" value="de"><span>German</span></label>
<label><input type="checkbox" name="languages" value="pt"><span>Portuguese</span></label>
<label><input type="checkbox" name="languages" value="zh"><span>Chinese</span></label>
<label><input type="checkbox" name="languages" value="ja"><span>Japanese</span></label>
</div></div>
<div class="field"><label>Data Sensitivity</label>
<select name="data_sensitivity">
<option value="low">Low</option><option value="medium" selected>Medium</option>
<option value="high">High</option><option value="critical">Critical</option>
</select></div>
<div class="field"><label>Storage Preference</label>
<select name="storage_preference">
<option value="any-cloud">Any Cloud</option><option value="private-cloud">Private Cloud</option>
<option value="on-premise">On-Premise</option><option value="eu-only">EU Only</option>
</select></div>
</fieldset>

<!-- Step 4: Budget -->
<fieldset data-step="3">
<legend>Budget</legend>
<div class="field"><label>Monthly API Budget (USD) *</label><input type="number" name="monthly_api_budget" min="0" value="50" step="5"></div>
<div class="field"><label>Deployment Method *</label>
<select name="deployment_method" required>
<option value="docker" selected>Docker</option><option value="vagrant">Vagrant</option>
</select></div>
</fieldset>

<!-- Step 5: Review -->
<fieldset data-step="4">
<legend>Review &amp; Submit</legend>
<div id="reviewContent"></div>
<div id="msgBox"></div>
<div class="btn-row"><button type="button" class="btn btn-back" onclick="goStep(3)">Back</button>
<button type="button" class="btn btn-submit" onclick="submitForm()">Submit Assessment</button></div>
</fieldset>

<div class="btn-row" id="navBtns">
<button type="button" class="btn btn-back" id="backBtn" onclick="goStep(currentStep-1)" style="visibility:hidden">Back</button>
<button type="button" class="btn btn-next" id="nextBtn" onclick="goStep(currentStep+1)">Next</button>
</div>
</form>

<p class="footer">Claw Agents Provisioner &mdash; Assessment Wizard on port WIZARD_PORT</p>
</div>

<script>
let currentStep=0;const totalSteps=5;
function goStep(n){
  if(n<0||n>=totalSteps)return;
  if(n>currentStep){const fs=document.querySelector('[data-step="'+currentStep+'"]');
    const req=fs.querySelectorAll('[required]');
    for(const r of req){if(!r.value.trim()){r.style.borderColor='#ff4455';r.focus();return;}r.style.borderColor='#2a2a40';}}
  currentStep=n;
  document.querySelectorAll('fieldset').forEach(f=>f.classList.remove('active'));
  document.querySelector('[data-step="'+n+'"]').classList.add('active');
  const circles=document.querySelectorAll('.step-circle');
  const lines=document.querySelectorAll('.step-line');
  circles.forEach((c,i)=>{c.classList.remove('active','done');if(i<n)c.classList.add('done');if(i===n)c.classList.add('active');});
  lines.forEach((l,i)=>{l.classList.toggle('done',i<n);});
  const nav=document.getElementById('navBtns');
  if(n===totalSteps-1){nav.style.display='none';}else{nav.style.display='flex';
    document.getElementById('backBtn').style.visibility=n>0?'visible':'hidden';}
  if(n===totalSteps-1)buildReview();
}
function getFormData(){
  const fd={};const form=document.getElementById('wizardForm');
  form.querySelectorAll('input[type=text],input[type=number],select,textarea').forEach(el=>{if(el.name)fd[el.name]=el.value;});
  const cbGroups={};
  form.querySelectorAll('input[type=checkbox]:checked').forEach(el=>{if(!cbGroups[el.name])cbGroups[el.name]=[];cbGroups[el.name].push(el.value);});
  Object.assign(fd,cbGroups);
  return fd;
}
function buildReview(){
  const d=getFormData();const rc=document.getElementById('reviewContent');
  const sections=[
    {title:'Company Info',step:0,items:[['Company',d.company_name],['Industry',d.industry],['Team Size',d.team_size],['Package',d.service_package]]},
    {title:'Use Case',step:1,items:[['Use Cases',(d.primary_use_cases||[]).join(', ')||'none'],['Complexity',d.complexity_level],['Description',d.description||'--']]},
    {title:'Requirements',step:2,items:[['Channel',d.primary_channel],['Languages',(d.languages||[]).join(', ')],['Sensitivity',d.data_sensitivity],['Storage',d.storage_preference]]},
    {title:'Budget',step:3,items:[['Monthly Budget','$'+d.monthly_api_budget],['Deploy Method',d.deployment_method]]}
  ];
  rc.innerHTML=sections.map(s=>'<div class="review-section"><h3>'+s.title+'</h3>'+s.items.map(i=>'<p><strong>'+i[0]+':</strong> '+i[1]+'</p>').join('')+'<button class="edit-btn" type="button" onclick="goStep('+s.step+')">Edit</button></div>').join('');
  document.getElementById('msgBox').innerHTML='';
}
function submitForm(){
  const d=getFormData();const mb=document.getElementById('msgBox');
  mb.innerHTML='<div class="msg" style="display:block;background:#1a1a2e;border:1px solid #00d4aa;color:#aaa">Submitting...</div>';
  fetch('/api/wizard/assess',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(d)})
  .then(r=>r.json()).then(j=>{
    if(j.ok){mb.innerHTML='<div class="msg ok">'+j.message+'</div>';}
    else{mb.innerHTML='<div class="msg err">'+(j.errors||[]).join('<br>')+'</div>';}
  }).catch(e=>{mb.innerHTML='<div class="msg err">Network error: '+e+'</div>';});
}
</script>
</body>
</html>
"""


# ═══════════════════════════════════════════════════════════════════════════
#  HTTP Handler
# ═══════════════════════════════════════════════════════════════════════════

class WizardHandler(BaseHTTPRequestHandler):
    """Handles wizard HTTP endpoints."""

    server_version = "ClawWizard/1.0"
    metrics: Optional[MetricsCollector] = None
    rate_limiter: RateLimiter = RateLimiter()

    def _get_client_key(self) -> str:
        """Derive a rate-limit key from Bearer token or client IP."""
        auth = self.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            return auth[7:].strip()
        return self.client_address[0]

    def _check_middleware(self) -> bool:
        """
        Run auth + rate-limit checks before request handling.

        Returns True if the request should proceed, False if a response
        has already been sent (401 or 429).
        """
        ok, error_msg = check_auth(self.headers)
        if not ok:
            self._send_json({"error": error_msg}, 401)
            return False

        client_key = self._get_client_key()
        allowed, remaining, reset_at = self.rate_limiter.check(client_key)
        self._rl_remaining = remaining
        self._rl_reset_at = reset_at

        if not allowed:
            body = json.dumps({"error": "Rate limit exceeded. Try again later."}, indent=2).encode("utf-8")
            self.send_response(429)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-RateLimit-Limit", str(self.rate_limiter.max_requests))
            self.send_header("X-RateLimit-Remaining", str(remaining))
            self.send_header("X-RateLimit-Reset", str(int(reset_at)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)
            return False

        return True

    def _send_json(self, data: dict, status: int = 200):
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        # Rate-limit headers
        self.send_header("X-RateLimit-Limit", str(self.rate_limiter.max_requests))
        if hasattr(self, "_rl_remaining"):
            self.send_header("X-RateLimit-Remaining", str(self._rl_remaining))
        if hasattr(self, "_rl_reset_at"):
            self.send_header("X-RateLimit-Reset", str(int(self._rl_reset_at)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str, status: int = 200):
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(length) if length > 0 else b""

    def _send_metrics(self) -> None:
        """GET /metrics — Prometheus text exposition."""
        if not self.metrics:
            self._send_json({"error": "Metrics not initialized"}, 503)
            return
        body = self.metrics.metrics_handler().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # ── GET routes ────────────────────────────────────────────────────────

    def do_GET(self):
        if self.metrics:
            self.metrics.inc_active_connections()
        start = time.time()
        path = self.path.split("?")[0]
        status = 200

        try:
            # Health and metrics bypass auth + rate limiting
            if path == "/metrics":
                self._send_metrics()
                return

            # Auth + rate-limit middleware
            if not self._check_middleware():
                return

            if path == "/":
                port = self.server.server_address[1]
                html = WIZARD_HTML.replace("WIZARD_PORT", str(port))
                self._send_html(html)

            elif path == "/api/wizard/platforms":
                self._send_json({"platforms": PLATFORMS})

            elif path == "/api/wizard/preview":
                result = run_resolve_preview()
                self._send_json(result)

            elif path == "/api/wizard/status":
                with _deploy_lock:
                    self._send_json(dict(_deploy_state))

            else:
                status = 404
                self.send_error(404, "Not Found")
        except Exception:  # Broad catch: record status=500 for metrics before re-raising
            status = 500
            raise
        finally:
            if self.metrics:
                self.metrics.dec_active_connections()
                self.metrics.track_request("GET", path, status, time.time() - start)

    # ── POST routes ───────────────────────────────────────────────────────

    def do_POST(self):
        if self.metrics:
            self.metrics.inc_active_connections()
        start = time.time()
        path = self.path.split("?")[0]
        status = 200

        try:
            # Auth + rate-limit middleware
            if not self._check_middleware():
                return

            if path == "/api/wizard/assess":
                self._handle_assess()

            elif path == "/api/wizard/deploy":
                self._handle_deploy()

            else:
                status = 404
                self.send_error(404, "Not Found")
        except Exception:  # Broad catch: record status=500 for metrics before re-raising
            status = 500
            raise
        finally:
            if self.metrics:
                self.metrics.dec_active_connections()
                self.metrics.track_request("POST", path, status, time.time() - start)

    def _handle_assess(self):
        """Validate form data and write client-assessment.json."""
        raw = self._read_body()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            self._send_json({"ok": False, "errors": ["Invalid JSON body"]}, 400)
            return

        errors = validate_assessment(data)
        if errors:
            self._send_json({"ok": False, "errors": errors}, 422)
            return

        assessment = build_assessment_json(data)

        try:
            with open(ASSESSMENT_OUTPUT, "w", encoding="utf-8") as f:
                json.dump(assessment, f, indent=2, ensure_ascii=False)
            logger.info(f"Assessment written: {ASSESSMENT_OUTPUT}")
            self._send_json({
                "ok": True,
                "message": f"Assessment saved to {ASSESSMENT_OUTPUT.name}",
                "path": str(ASSESSMENT_OUTPUT),
            })
        except OSError as e:
            logger.error(f"Failed to write assessment: {e}")
            self._send_json(
                {"ok": False, "errors": [f"Write failed: {e}"]}, 500,
            )

    def _handle_deploy(self):
        """Trigger claw.sh deploy."""
        if not ASSESSMENT_OUTPUT.exists():
            self._send_json(
                {"ok": False, "error": "No assessment file. Submit wizard first."},
                400,
            )
            return

        with _deploy_lock:
            if _deploy_state["status"] == "running":
                self._send_json(
                    {"ok": False, "error": "Deployment already in progress."},
                    409,
                )
                return

        trigger_deploy()
        self._send_json({"ok": True, "message": "Deployment started."})

    # ── OPTIONS (CORS preflight) ──────────────────────────────────────────

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, format, *args):
        logger.info(f"{self.client_address[0]}  {format % args}")


# ═══════════════════════════════════════════════════════════════════════════
#  Threaded HTTP Server
# ═══════════════════════════════════════════════════════════════════════════

class ThreadedWizardServer(ThreadingMixIn, HTTPServer):
    """HTTP server that handles each request in a separate thread."""
    daemon_threads = True
    allow_reuse_address = True


# ═══════════════════════════════════════════════════════════════════════════
#  PID Management
# ═══════════════════════════════════════════════════════════════════════════

def write_pid():
    """Write current PID to the PID file."""
    PID_DIR.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(os.getpid()), encoding="utf-8")
    logger.info(f"PID file: {PID_FILE}")


def read_pid() -> int:
    """Read PID from file, return 0 if missing or invalid."""
    if not PID_FILE.exists():
        return 0
    try:
        return int(PID_FILE.read_text(encoding="utf-8").strip())
    except (ValueError, OSError):
        return 0


def remove_pid():
    """Remove the PID file."""
    try:
        PID_FILE.unlink(missing_ok=True)
    except OSError:
        pass


def is_process_alive(pid: int) -> bool:
    """Check if a process with the given PID is running."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError, OSError):
        return False


# ═══════════════════════════════════════════════════════════════════════════
#  Start / Stop
# ═══════════════════════════════════════════════════════════════════════════

def cmd_start(port: int):
    """Start the wizard HTTP server."""
    existing_pid = read_pid()
    if existing_pid and is_process_alive(existing_pid):
        print(f"{YELLOW}Wizard already running (PID {existing_pid}){NC}")
        print(f"Stop it first:  python shared/claw_wizard.py --stop")
        sys.exit(1)

    print(f"{BOLD}{'=' * 60}{NC}")
    print(f"  {CYAN}CLAW AGENTS PROVISIONER{NC} -- Assessment Web Wizard")
    print(f"{'=' * 60}")
    print(f"  {GREEN}Starting on port {port}...{NC}")
    print()

    WizardHandler.metrics = MetricsCollector(service="claw-wizard")
    server = ThreadedWizardServer(("0.0.0.0", port), WizardHandler)
    write_pid()

    def _shutdown(sig, frame):
        logger.info("Shutdown signal received")
        remove_pid()
        server.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    print(f"  {GREEN}Wizard running:{NC}  http://localhost:{port}/")
    print(f"  {DIM}PID: {os.getpid()}{NC}")
    print(f"  {DIM}Assessment output: {ASSESSMENT_OUTPUT}{NC}")
    print(f"  {DIM}Press Ctrl+C to stop{NC}")
    print()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        remove_pid()
        logger.info("Wizard stopped")


def cmd_stop():
    """Stop a running wizard server via its PID file."""
    pid = read_pid()
    if not pid:
        print(f"{YELLOW}No wizard PID file found.{NC}")
        return

    if not is_process_alive(pid):
        print(f"{YELLOW}Wizard process (PID {pid}) is not running. Cleaning up.{NC}")
        remove_pid()
        return

    print(f"{BLUE}Stopping wizard (PID {pid})...{NC}")
    try:
        os.kill(pid, signal.SIGTERM)
        print(f"{GREEN}Wizard stopped.{NC}")
    except OSError as e:
        print(f"{RED}Failed to stop wizard: {e}{NC}")

    remove_pid()


# ═══════════════════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════════════════

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="claw_wizard",
        description="Claw Assessment Web Wizard — guided assessment creation",
    )
    parser.add_argument(
        "--start", action="store_true",
        help="Start the wizard web server",
    )
    parser.add_argument(
        "--stop", action="store_true",
        help="Stop a running wizard server",
    )
    parser.add_argument(
        "--port", type=int, default=DEFAULT_PORT,
        help=f"Port to listen on (default: {DEFAULT_PORT})",
    )
    return parser


def main():
    setup_logging()
    parser = build_parser()
    args = parser.parse_args()

    if args.stop:
        cmd_stop()
    elif args.start:
        cmd_start(args.port)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
