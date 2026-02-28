#!/usr/bin/env python3
"""
=============================================================================
CLAW AGENTS PROVISIONER — Skills Marketplace
=============================================================================
Manages the installation, removal, and discovery of agent skills from the
shared skills catalog.  Each skill adds a specific capability (web search,
sentiment analysis, CRM sync, etc.) to an individual Claw agent.

Supported platforms:
  - zeroclaw, nanoclaw, picoclaw, openclaw, parlant

Features:
  - Search skills by keyword, category, or platform compatibility
  - Install / uninstall skills per agent
  - Platform compatibility verification before install
  - Bundle install — pre-built skill sets for common use cases
  - List all available skills or installed skills per agent
  - Dependency resolution — auto-installs required dependencies

Usage:
  python3 shared/claw_skills.py --list                                  # All skills
  python3 shared/claw_skills.py --search "sentiment"                    # Search
  python3 shared/claw_skills.py --install web-search --agent zeroclaw   # Install
  python3 shared/claw_skills.py --bundle customer-support-bundle --agent nanoclaw
  python3 shared/claw_skills.py --uninstall web-search --agent zeroclaw # Uninstall
  python3 shared/claw_skills.py --installed --agent zeroclaw            # Show installed
  python3 shared/claw_skills.py --info web-search                       # Skill details

Data: data/skills/installed.json — tracks installed skills per agent

Python 3.8+ stdlib only (no external dependencies).
=============================================================================
Created by Mauro Tommasi — linkedin.com/in/maurotommasi
Apache 2.0 © 2026 Amenthyx
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Any

# -------------------------------------------------------------------------
# Constants
# -------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
CATALOG_FILE = SCRIPT_DIR / "skills-catalog.json"
INSTALLED_FILE = PROJECT_ROOT / "data" / "skills" / "installed.json"

VALID_PLATFORMS = ["zeroclaw", "nanoclaw", "picoclaw", "openclaw", "parlant"]

# -------------------------------------------------------------------------
# Colors (for terminal output)
# -------------------------------------------------------------------------
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
BLUE = "\033[0;34m"
CYAN = "\033[0;36m"
BOLD = "\033[1m"
DIM = "\033[2m"
NC = "\033[0m"


def log(msg: str) -> None:
    print(f"{GREEN}[skills]{NC} {msg}")


def warn(msg: str) -> None:
    print(f"{YELLOW}[skills]{NC} {msg}")


def err(msg: str) -> None:
    print(f"{RED}[skills]{NC} {msg}", file=sys.stderr)


def info(msg: str) -> None:
    print(f"{BLUE}[skills]{NC} {msg}")


# -------------------------------------------------------------------------
# SkillCatalog — load and search the skills catalog
# -------------------------------------------------------------------------
class SkillCatalog:
    """Loads the skills catalog from JSON and provides search capabilities."""

    def __init__(self, catalog_path: Optional[Path] = None) -> None:
        self.catalog_path = catalog_path or CATALOG_FILE
        self._catalog: Dict[str, Any] = {}
        self._skills: List[Dict[str, Any]] = []
        self._bundles: List[Dict[str, Any]] = []
        self._categories: List[str] = []
        self._load()

    def _load(self) -> None:
        """Load the skills catalog from disk."""
        if not self.catalog_path.exists():
            err(f"Catalog file not found: {self.catalog_path}")
            return

        try:
            with open(self.catalog_path, "r", encoding="utf-8") as f:
                self._catalog = json.load(f)
            self._skills = self._catalog.get("skills", [])
            self._bundles = self._catalog.get("bundles", [])
            self._categories = self._catalog.get("categories", [])
        except (json.JSONDecodeError, IOError) as exc:
            err(f"Failed to load catalog: {exc}")

    @property
    def version(self) -> str:
        return self._catalog.get("version", "unknown")

    @property
    def categories(self) -> List[str]:
        return list(self._categories)

    @property
    def skills(self) -> List[Dict[str, Any]]:
        return list(self._skills)

    @property
    def bundles(self) -> List[Dict[str, Any]]:
        return list(self._bundles)

    def get_skill(self, skill_id: str) -> Optional[Dict[str, Any]]:
        """Look up a single skill by ID."""
        for skill in self._skills:
            if skill["id"] == skill_id:
                return dict(skill)
        return None

    def get_bundle(self, bundle_id: str) -> Optional[Dict[str, Any]]:
        """Look up a single bundle by ID."""
        for bundle in self._bundles:
            if bundle["id"] == bundle_id:
                return dict(bundle)
        return None

    def search(
        self,
        keyword: Optional[str] = None,
        category: Optional[str] = None,
        platform: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Search skills by keyword, category, and/or platform.

        All filters are AND-combined when provided together.
        Keyword matches against id, name, description, and tags.
        """
        results = list(self._skills)

        if category:
            cat_lower = category.lower()
            results = [s for s in results if s.get("category", "").lower() == cat_lower]

        if platform:
            plat_lower = platform.lower()
            results = [
                s for s in results
                if plat_lower in [p.lower() for p in s.get("platforms", [])]
            ]

        if keyword:
            kw_lower = keyword.lower()
            filtered = []
            for skill in results:
                searchable = " ".join([
                    skill.get("id", ""),
                    skill.get("name", ""),
                    skill.get("description", ""),
                    " ".join(skill.get("tags", [])),
                ]).lower()
                if kw_lower in searchable:
                    filtered.append(skill)
            results = filtered

        return results

    def list_by_category(self) -> Dict[str, List[Dict[str, Any]]]:
        """Group all skills by category."""
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for cat in self._categories:
            grouped[cat] = []
        for skill in self._skills:
            cat = skill.get("category", "other")
            if cat not in grouped:
                grouped[cat] = []
            grouped[cat].append(skill)
        return grouped

    def check_compatibility(self, skill_id: str, platform: str) -> bool:
        """Check whether a skill is compatible with a given platform."""
        skill = self.get_skill(skill_id)
        if not skill:
            return False
        return platform.lower() in [p.lower() for p in skill.get("platforms", [])]

    def resolve_dependencies(self, skill_id: str) -> List[str]:
        """Return the ordered list of dependency skill IDs for a skill.

        Performs depth-first resolution to handle transitive dependencies.
        """
        visited: List[str] = []
        self._resolve_deps_recursive(skill_id, visited, set())
        # Remove the skill itself from the dependency list
        return [sid for sid in visited if sid != skill_id]

    def _resolve_deps_recursive(
        self, skill_id: str, ordered: List[str], seen: set
    ) -> None:
        """Recursive depth-first dependency resolution."""
        if skill_id in seen:
            return
        seen.add(skill_id)

        skill = self.get_skill(skill_id)
        if not skill:
            return

        for dep_id in skill.get("dependencies", []):
            self._resolve_deps_recursive(dep_id, ordered, seen)

        ordered.append(skill_id)


# -------------------------------------------------------------------------
# SkillManager — install / uninstall skills per agent
# -------------------------------------------------------------------------
class SkillManager:
    """Manages per-agent skill installations tracked in installed.json."""

    def __init__(
        self,
        catalog: SkillCatalog,
        installed_path: Optional[Path] = None,
    ) -> None:
        self.catalog = catalog
        self.installed_path = installed_path or INSTALLED_FILE
        self._data: Dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        """Load the installed skills registry from disk."""
        if self.installed_path.exists():
            try:
                with open(self.installed_path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except (json.JSONDecodeError, IOError) as exc:
                warn(f"Could not read installed skills file: {exc}")
                self._data = {}
        else:
            self._data = {}

    def _save(self) -> None:
        """Persist the installed skills registry to disk."""
        self.installed_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.installed_path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2)
        except IOError as exc:
            err(f"Failed to save installed skills: {exc}")

    def _agent_key(self, agent: str) -> str:
        """Normalize agent name for use as a dict key."""
        return agent.lower().strip()

    def get_installed(self, agent: str) -> List[Dict[str, Any]]:
        """Return list of installed skill records for an agent."""
        key = self._agent_key(agent)
        return list(self._data.get(key, {}).get("skills", []))

    def get_installed_ids(self, agent: str) -> List[str]:
        """Return just the IDs of installed skills for an agent."""
        return [s["id"] for s in self.get_installed(agent)]

    def is_installed(self, skill_id: str, agent: str) -> bool:
        """Check whether a skill is already installed on an agent."""
        return skill_id in self.get_installed_ids(agent)

    def install(self, skill_id: str, agent: str) -> Dict[str, Any]:
        """Install a skill on an agent.

        Returns a result dict with status, message, and any dependencies
        that were also installed.
        """
        key = self._agent_key(agent)

        # Validate agent platform
        if key not in VALID_PLATFORMS:
            return {
                "status": "error",
                "message": f"Unknown platform '{agent}'. Valid: {', '.join(VALID_PLATFORMS)}",
            }

        # Look up skill in catalog
        skill = self.catalog.get_skill(skill_id)
        if not skill:
            return {
                "status": "error",
                "message": f"Skill '{skill_id}' not found in catalog.",
            }

        # Platform compatibility check
        if not self.catalog.check_compatibility(skill_id, key):
            return {
                "status": "error",
                "message": (
                    f"Skill '{skill_id}' is not compatible with platform '{key}'. "
                    f"Supported: {', '.join(skill.get('platforms', []))}"
                ),
            }

        # Already installed?
        if self.is_installed(skill_id, agent):
            return {
                "status": "skipped",
                "message": f"Skill '{skill_id}' is already installed on '{key}'.",
            }

        # Resolve dependencies
        dep_ids = self.catalog.resolve_dependencies(skill_id)
        installed_deps: List[str] = []

        for dep_id in dep_ids:
            if self.is_installed(dep_id, agent):
                continue
            # Verify dependency is compatible
            if not self.catalog.check_compatibility(dep_id, key):
                return {
                    "status": "error",
                    "message": (
                        f"Dependency '{dep_id}' of '{skill_id}' is not compatible "
                        f"with platform '{key}'."
                    ),
                }
            self._do_install(dep_id, key)
            installed_deps.append(dep_id)

        # Install the skill itself
        self._do_install(skill_id, key)
        self._save()

        parts = [f"Skill '{skill_id}' installed on '{key}'."]
        if installed_deps:
            parts.append(f"Dependencies also installed: {', '.join(installed_deps)}")

        return {
            "status": "installed",
            "message": " ".join(parts),
            "skill_id": skill_id,
            "agent": key,
            "dependencies_installed": installed_deps,
        }

    def _do_install(self, skill_id: str, agent_key: str) -> None:
        """Low-level: append a skill record to the agent's installed list."""
        skill = self.catalog.get_skill(skill_id)
        if not skill:
            return

        if agent_key not in self._data:
            self._data[agent_key] = {"skills": []}

        record = {
            "id": skill["id"],
            "name": skill["name"],
            "version": skill["version"],
            "category": skill["category"],
            "installed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "install_cmd": skill.get("install_cmd", ""),
        }
        self._data[agent_key]["skills"].append(record)

    def uninstall(self, skill_id: str, agent: str) -> Dict[str, Any]:
        """Uninstall a skill from an agent.

        Will not remove a skill that is a dependency of another installed
        skill unless that dependent skill is uninstalled first.
        """
        key = self._agent_key(agent)

        if key not in VALID_PLATFORMS:
            return {
                "status": "error",
                "message": f"Unknown platform '{agent}'. Valid: {', '.join(VALID_PLATFORMS)}",
            }

        if not self.is_installed(skill_id, agent):
            return {
                "status": "error",
                "message": f"Skill '{skill_id}' is not installed on '{key}'.",
            }

        # Check whether any other installed skill depends on this one
        dependents = self._find_dependents(skill_id, key)
        if dependents:
            return {
                "status": "error",
                "message": (
                    f"Cannot uninstall '{skill_id}' — required by: "
                    f"{', '.join(dependents)}. Uninstall those first."
                ),
            }

        # Remove from installed list
        agent_data = self._data.get(key, {})
        agent_data["skills"] = [
            s for s in agent_data.get("skills", []) if s["id"] != skill_id
        ]
        self._data[key] = agent_data
        self._save()

        return {
            "status": "uninstalled",
            "message": f"Skill '{skill_id}' uninstalled from '{key}'.",
            "skill_id": skill_id,
            "agent": key,
        }

    def _find_dependents(self, skill_id: str, agent_key: str) -> List[str]:
        """Return IDs of installed skills that depend on skill_id."""
        dependents: List[str] = []
        for installed_id in self.get_installed_ids(agent_key):
            skill = self.catalog.get_skill(installed_id)
            if skill and skill_id in skill.get("dependencies", []):
                dependents.append(installed_id)
        return dependents


# -------------------------------------------------------------------------
# BundleManager — install pre-built skill bundles
# -------------------------------------------------------------------------
class BundleManager:
    """Installs entire skill bundles on agents via SkillManager."""

    def __init__(self, catalog: SkillCatalog, skill_manager: SkillManager) -> None:
        self.catalog = catalog
        self.skill_manager = skill_manager

    def install_bundle(self, bundle_id: str, agent: str) -> Dict[str, Any]:
        """Install all skills from a bundle on an agent.

        Skills already installed are skipped.  Incompatible skills are
        reported but do not block the rest of the bundle.
        """
        bundle = self.catalog.get_bundle(bundle_id)
        if not bundle:
            return {
                "status": "error",
                "message": f"Bundle '{bundle_id}' not found in catalog.",
            }

        key = agent.lower().strip()
        if key not in VALID_PLATFORMS:
            return {
                "status": "error",
                "message": f"Unknown platform '{agent}'. Valid: {', '.join(VALID_PLATFORMS)}",
            }

        results: List[Dict[str, Any]] = []
        installed_count = 0
        skipped_count = 0
        error_count = 0

        for skill_id in bundle.get("skills", []):
            result = self.skill_manager.install(skill_id, agent)
            results.append(result)

            status = result.get("status", "")
            if status == "installed":
                installed_count += 1
            elif status == "skipped":
                skipped_count += 1
            else:
                error_count += 1

        total = len(bundle.get("skills", []))
        return {
            "status": "completed",
            "message": (
                f"Bundle '{bundle_id}' on '{key}': "
                f"{installed_count} installed, {skipped_count} skipped, "
                f"{error_count} errors (out of {total} skills)"
            ),
            "bundle_id": bundle_id,
            "agent": key,
            "installed": installed_count,
            "skipped": skipped_count,
            "errors": error_count,
            "total": total,
            "details": results,
        }

    def list_bundles(self) -> List[Dict[str, Any]]:
        """Return all available bundles with their skill lists."""
        bundles = []
        for bundle in self.catalog.bundles:
            skill_details = []
            for sid in bundle.get("skills", []):
                skill = self.catalog.get_skill(sid)
                if skill:
                    skill_details.append({
                        "id": skill["id"],
                        "name": skill["name"],
                        "category": skill["category"],
                    })
            bundles.append({
                "id": bundle["id"],
                "name": bundle["name"],
                "description": bundle["description"],
                "skill_count": len(bundle.get("skills", [])),
                "skills": skill_details,
            })
        return bundles


# -------------------------------------------------------------------------
# CLI Output Formatting
# -------------------------------------------------------------------------
def print_skill_list(skills: List[Dict[str, Any]], title: str = "Skills") -> None:
    """Print a formatted table of skills."""
    print(f"\n{BOLD}{CYAN}=== {title} ({len(skills)}) ==={NC}\n")

    if not skills:
        print(f"  {DIM}No skills found.{NC}\n")
        return

    # Group by category for readability
    by_cat: Dict[str, List[Dict[str, Any]]] = {}
    for skill in skills:
        cat = skill.get("category", "other")
        if cat not in by_cat:
            by_cat[cat] = []
        by_cat[cat].append(skill)

    for cat in sorted(by_cat.keys()):
        cat_skills = by_cat[cat]
        print(f"  {BOLD}{cat.upper()}{NC}")
        for s in cat_skills:
            platforms = ", ".join(s.get("platforms", []))
            print(
                f"    {GREEN}{s['id']:.<28}{NC} "
                f"{s.get('name', ''):<22} "
                f"v{s.get('version', '?'):<8} "
                f"{DIM}[{platforms}]{NC}"
            )
            print(f"      {DIM}{s.get('description', '')}{NC}")
        print()


def print_skill_info(skill: Dict[str, Any]) -> None:
    """Print detailed information about a single skill."""
    print(f"\n{BOLD}{CYAN}=== Skill: {skill.get('name', '?')} ==={NC}\n")
    print(f"  {BOLD}ID:{NC}           {skill.get('id', '?')}")
    print(f"  {BOLD}Name:{NC}         {skill.get('name', '?')}")
    print(f"  {BOLD}Version:{NC}      {skill.get('version', '?')}")
    print(f"  {BOLD}Category:{NC}     {skill.get('category', '?')}")
    print(f"  {BOLD}Description:{NC}  {skill.get('description', '?')}")
    print(f"  {BOLD}Install cmd:{NC}  {skill.get('install_cmd', '?')}")

    platforms = skill.get("platforms", [])
    print(f"  {BOLD}Platforms:{NC}    {', '.join(platforms)}")

    deps = skill.get("dependencies", [])
    if deps:
        print(f"  {BOLD}Dependencies:{NC} {', '.join(deps)}")
    else:
        print(f"  {BOLD}Dependencies:{NC} {DIM}none{NC}")

    tags = skill.get("tags", [])
    if tags:
        print(f"  {BOLD}Tags:{NC}         {', '.join(tags)}")

    print()


def print_installed(agent: str, skills: List[Dict[str, Any]]) -> None:
    """Print skills installed on an agent."""
    print(f"\n{BOLD}{CYAN}=== Installed Skills: {agent} ({len(skills)}) ==={NC}\n")

    if not skills:
        print(f"  {DIM}No skills installed on '{agent}'.{NC}\n")
        return

    print(f"  {BOLD}{'ID':<28} {'Name':<22} {'Version':<10} {'Category':<16} {'Installed At'}{NC}")
    print(f"  {'-' * 28} {'-' * 22} {'-' * 10} {'-' * 16} {'-' * 20}")

    for s in skills:
        print(
            f"  {GREEN}{s['id']:<28}{NC} "
            f"{s.get('name', ''):<22} "
            f"v{s.get('version', '?'):<9} "
            f"{s.get('category', ''):<16} "
            f"{DIM}{s.get('installed_at', '?')}{NC}"
        )

    print()


def print_bundle_list(bundles: List[Dict[str, Any]]) -> None:
    """Print all available bundles."""
    print(f"\n{BOLD}{CYAN}=== Skill Bundles ({len(bundles)}) ==={NC}\n")

    for b in bundles:
        print(f"  {BOLD}{GREEN}{b['id']}{NC}")
        print(f"    {b.get('description', '')}")
        skill_names = [s["name"] for s in b.get("skills", [])]
        print(f"    {DIM}Skills ({b.get('skill_count', 0)}): {', '.join(skill_names)}{NC}")
        print()


def print_search_results(results: List[Dict[str, Any]], query: str) -> None:
    """Print search results with the query highlighted."""
    print(f"\n{BOLD}{CYAN}=== Search Results for '{query}' ({len(results)} matches) ==={NC}\n")

    if not results:
        print(f"  {DIM}No skills match '{query}'.{NC}\n")
        return

    for s in results:
        platforms = ", ".join(s.get("platforms", []))
        tags = ", ".join(s.get("tags", []))
        print(
            f"  {GREEN}{s['id']:.<28}{NC} "
            f"{s.get('name', ''):<22} "
            f"{BOLD}[{s.get('category', '?')}]{NC}"
        )
        print(f"    {s.get('description', '')}")
        print(f"    {DIM}Platforms: {platforms}  |  Tags: {tags}{NC}")
        print()


def print_result(result: Dict[str, Any]) -> None:
    """Print an install/uninstall result."""
    status = result.get("status", "unknown")
    message = result.get("message", "")

    if status == "installed":
        print(f"\n  {GREEN}INSTALLED{NC} {message}")
    elif status == "uninstalled":
        print(f"\n  {GREEN}UNINSTALLED{NC} {message}")
    elif status == "skipped":
        print(f"\n  {YELLOW}SKIPPED{NC} {message}")
    elif status == "completed":
        print(f"\n  {GREEN}COMPLETED{NC} {message}")
    elif status == "error":
        print(f"\n  {RED}ERROR{NC} {message}")
    else:
        print(f"\n  {DIM}{status}{NC} {message}")

    # Print dependency details if present
    deps = result.get("dependencies_installed", [])
    if deps:
        print(f"    {DIM}Dependencies installed: {', '.join(deps)}{NC}")

    # Print bundle details if present
    details = result.get("details", [])
    if details:
        print()
        for d in details:
            s = d.get("status", "?")
            m = d.get("message", "")
            if s == "installed":
                print(f"    {GREEN}+{NC} {m}")
            elif s == "skipped":
                print(f"    {YELLOW}-{NC} {m}")
            elif s == "error":
                print(f"    {RED}x{NC} {m}")

    print()


# -------------------------------------------------------------------------
# Main CLI
# -------------------------------------------------------------------------
def main() -> None:
    if len(sys.argv) < 2:
        _print_usage()
        sys.exit(1)

    # Parse arguments manually (no argparse dependency for simplicity)
    args = sys.argv[1:]
    action = args[0]

    # Extract --agent value if present
    agent = _extract_flag(args, "--agent")

    # Initialize components
    catalog = SkillCatalog()
    manager = SkillManager(catalog)
    bundle_mgr = BundleManager(catalog, manager)

    if action == "--list":
        print_skill_list(catalog.skills, "Skills Marketplace")
        print(f"{BOLD}Catalog version:{NC} {catalog.version}")
        print(f"{BOLD}Total skills:{NC}   {len(catalog.skills)}")
        print(f"{BOLD}Categories:{NC}     {', '.join(catalog.categories)}")
        print(f"{BOLD}Bundles:{NC}        {len(catalog.bundles)}")
        print()
        print(f"{DIM}Use --search <keyword> to find skills, --info <id> for details.{NC}\n")

    elif action == "--search":
        keyword = _extract_positional(args, 1)
        category = _extract_flag(args, "--category")
        platform = _extract_flag(args, "--platform") or agent
        if not keyword and not category and not platform:
            err("Provide a search keyword, --category, or --platform filter.")
            sys.exit(1)
        results = catalog.search(keyword=keyword, category=category, platform=platform)
        query_parts = []
        if keyword:
            query_parts.append(keyword)
        if category:
            query_parts.append(f"category={category}")
        if platform:
            query_parts.append(f"platform={platform}")
        print_search_results(results, " + ".join(query_parts))

    elif action == "--install":
        skill_id = _extract_positional(args, 1)
        if not skill_id:
            err("Provide a skill ID. Example: --install web-search --agent zeroclaw")
            sys.exit(1)
        if not agent:
            err("Provide --agent <platform>. Example: --install web-search --agent zeroclaw")
            sys.exit(1)
        result = manager.install(skill_id, agent)
        print_result(result)

    elif action == "--uninstall":
        skill_id = _extract_positional(args, 1)
        if not skill_id:
            err("Provide a skill ID. Example: --uninstall web-search --agent zeroclaw")
            sys.exit(1)
        if not agent:
            err("Provide --agent <platform>. Example: --uninstall web-search --agent zeroclaw")
            sys.exit(1)
        result = manager.uninstall(skill_id, agent)
        print_result(result)

    elif action == "--bundle":
        bundle_id = _extract_positional(args, 1)
        if not bundle_id:
            # List all bundles
            bundles = bundle_mgr.list_bundles()
            print_bundle_list(bundles)
            return
        if not agent:
            err("Provide --agent <platform>. Example: --bundle customer-support-bundle --agent nanoclaw")
            sys.exit(1)
        result = bundle_mgr.install_bundle(bundle_id, agent)
        print_result(result)

    elif action == "--installed":
        if not agent:
            # Show all agents that have skills installed
            _print_all_installed(manager, catalog)
            return
        skills = manager.get_installed(agent)
        print_installed(agent, skills)

    elif action == "--info":
        skill_id = _extract_positional(args, 1)
        if not skill_id:
            err("Provide a skill ID. Example: --info web-search")
            sys.exit(1)
        skill = catalog.get_skill(skill_id)
        if not skill:
            err(f"Skill '{skill_id}' not found in catalog.")
            sys.exit(1)
        print_skill_info(skill)

    elif action == "--bundles":
        bundles = bundle_mgr.list_bundles()
        print_bundle_list(bundles)

    elif action in ("--help", "-h"):
        _print_usage()

    else:
        err(f"Unknown action: {action}")
        _print_usage()
        sys.exit(1)


def _print_all_installed(manager: SkillManager, catalog: SkillCatalog) -> None:
    """Print installed skills for every agent that has any."""
    print(f"\n{BOLD}{CYAN}=== All Installed Skills ==={NC}\n")

    found_any = False
    for platform in VALID_PLATFORMS:
        skills = manager.get_installed(platform)
        if skills:
            found_any = True
            print(f"  {BOLD}{platform}{NC} ({len(skills)} skills):")
            for s in skills:
                print(f"    {GREEN}{s['id']}{NC} v{s.get('version', '?')} [{s.get('category', '?')}]")
            print()

    if not found_any:
        print(f"  {DIM}No skills installed on any agent.{NC}\n")


def _extract_flag(args: List[str], flag: str) -> Optional[str]:
    """Extract the value after a flag (e.g. --agent zeroclaw)."""
    try:
        idx = args.index(flag)
        if idx + 1 < len(args):
            return args[idx + 1]
    except ValueError:
        pass
    return None


def _extract_positional(args: List[str], position: int) -> Optional[str]:
    """Extract a positional argument, skipping known flags and their values.

    The first arg (position 0) is always the action (e.g. --install).
    Position 1 is the first non-flag argument after the action.
    Known flags with values: --agent, --category, --platform.
    """
    FLAGS_WITH_VALUES = {"--agent", "--category", "--platform"}
    pos_count = 0
    skip_next = False
    for i, arg in enumerate(args):
        if skip_next:
            skip_next = False
            continue
        if arg in FLAGS_WITH_VALUES:
            skip_next = True  # Skip this flag's value
            continue
        if pos_count == position:
            return arg
        pos_count += 1
    return None


def _print_usage() -> None:
    """Print CLI usage instructions."""
    print(f"\n{BOLD}{CYAN}Claw Skills Marketplace{NC}")
    print(f"{DIM}Manage agent skills: search, install, uninstall, bundle.{NC}\n")
    print("Usage:")
    print(f"  python3 shared/claw_skills.py {GREEN}--list{NC}                                  List all available skills")
    print(f"  python3 shared/claw_skills.py {GREEN}--search{NC} <keyword>                      Search skills by keyword")
    print(f"  python3 shared/claw_skills.py {GREEN}--search{NC} <keyword> --category <cat>     Search with category filter")
    print(f"  python3 shared/claw_skills.py {GREEN}--search{NC} <keyword> --platform <plat>    Search with platform filter")
    print(f"  python3 shared/claw_skills.py {GREEN}--install{NC} <skill-id> --agent <platform> Install a skill")
    print(f"  python3 shared/claw_skills.py {GREEN}--uninstall{NC} <skill-id> --agent <plat>   Uninstall a skill")
    print(f"  python3 shared/claw_skills.py {GREEN}--bundle{NC} <bundle-id> --agent <platform> Install a skill bundle")
    print(f"  python3 shared/claw_skills.py {GREEN}--bundles{NC}                                List all bundles")
    print(f"  python3 shared/claw_skills.py {GREEN}--installed{NC}                              Show all installed skills")
    print(f"  python3 shared/claw_skills.py {GREEN}--installed{NC} --agent <platform>           Show installed for an agent")
    print(f"  python3 shared/claw_skills.py {GREEN}--info{NC} <skill-id>                        Show skill details")
    print()
    print(f"Platforms: {BOLD}{', '.join(VALID_PLATFORMS)}{NC}")
    print()


if __name__ == "__main__":
    main()
