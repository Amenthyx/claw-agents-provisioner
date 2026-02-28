"""
Tests for shared/claw_skills.py — Skills Marketplace.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "shared"))

from claw_skills import SkillCatalog, SkillManager, BundleManager, VALID_PLATFORMS


def _create_test_catalog(tmp_path):
    """Create a minimal skills catalog for testing."""
    catalog = {
        "version": "1.0-test",
        "categories": ["communication", "development", "analytics"],
        "skills": [
            {
                "id": "web-search",
                "name": "Web Search",
                "version": "1.0",
                "category": "communication",
                "description": "Search the web for information",
                "platforms": ["zeroclaw", "nanoclaw", "picoclaw", "openclaw", "parlant"],
                "tags": ["search", "web", "internet"],
                "dependencies": [],
                "install_cmd": "pip install web-search-skill",
            },
            {
                "id": "sentiment-analysis",
                "name": "Sentiment Analysis",
                "version": "1.0",
                "category": "analytics",
                "description": "Analyze sentiment of text",
                "platforms": ["zeroclaw", "openclaw"],
                "tags": ["sentiment", "nlp", "analysis"],
                "dependencies": [],
                "install_cmd": "pip install sentiment-skill",
            },
            {
                "id": "code-review",
                "name": "Code Review",
                "version": "1.0",
                "category": "development",
                "description": "Review code for quality",
                "platforms": ["zeroclaw", "openclaw", "parlant"],
                "tags": ["code", "review", "development"],
                "dependencies": [],
                "install_cmd": "pip install code-review-skill",
            },
            {
                "id": "advanced-code",
                "name": "Advanced Code Analysis",
                "version": "1.0",
                "category": "development",
                "description": "Advanced static analysis",
                "platforms": ["zeroclaw", "openclaw"],
                "tags": ["code", "static-analysis"],
                "dependencies": ["code-review"],
                "install_cmd": "pip install advanced-code-skill",
            },
        ],
        "bundles": [
            {
                "id": "dev-bundle",
                "name": "Developer Bundle",
                "description": "Skills for developers",
                "skills": ["web-search", "code-review"],
            },
        ],
    }
    catalog_file = tmp_path / "skills-catalog.json"
    catalog_file.write_text(json.dumps(catalog))
    return catalog_file


class TestSkillCatalogLoading:
    """Tests for SkillCatalog initialization."""

    def test_load_catalog(self, tmp_path):
        """SkillCatalog should load skills from JSON file."""
        catalog_file = _create_test_catalog(tmp_path)
        catalog = SkillCatalog(catalog_path=catalog_file)
        assert catalog.version == "1.0-test"
        assert len(catalog.skills) == 4
        assert len(catalog.categories) == 3

    def test_get_skill(self, tmp_path):
        """get_skill should return a specific skill by ID."""
        catalog_file = _create_test_catalog(tmp_path)
        catalog = SkillCatalog(catalog_path=catalog_file)
        skill = catalog.get_skill("web-search")
        assert skill is not None
        assert skill["name"] == "Web Search"

    def test_get_missing_skill(self, tmp_path):
        """get_skill for nonexistent ID should return None."""
        catalog_file = _create_test_catalog(tmp_path)
        catalog = SkillCatalog(catalog_path=catalog_file)
        assert catalog.get_skill("nonexistent") is None


class TestSearchByKeyword:
    """Tests for keyword-based skill search."""

    def test_search_by_keyword(self, tmp_path):
        """Search should find skills matching keyword in name/description/tags."""
        catalog_file = _create_test_catalog(tmp_path)
        catalog = SkillCatalog(catalog_path=catalog_file)
        results = catalog.search(keyword="sentiment")
        assert len(results) == 1
        assert results[0]["id"] == "sentiment-analysis"

    def test_search_by_keyword_partial(self, tmp_path):
        """Search should match partial keywords."""
        catalog_file = _create_test_catalog(tmp_path)
        catalog = SkillCatalog(catalog_path=catalog_file)
        results = catalog.search(keyword="code")
        assert len(results) >= 2  # code-review and advanced-code


class TestSearchByCategory:
    """Tests for category-based skill search."""

    def test_search_by_category(self, tmp_path):
        """Search should filter by category."""
        catalog_file = _create_test_catalog(tmp_path)
        catalog = SkillCatalog(catalog_path=catalog_file)
        results = catalog.search(category="development")
        assert len(results) == 2
        for r in results:
            assert r["category"] == "development"


class TestPlatformCompatibility:
    """Tests for platform compatibility filtering."""

    def test_search_by_platform(self, tmp_path):
        """Search should filter by platform compatibility."""
        catalog_file = _create_test_catalog(tmp_path)
        catalog = SkillCatalog(catalog_path=catalog_file)
        results = catalog.search(platform="nanoclaw")
        # Only web-search supports nanoclaw
        assert len(results) == 1
        assert results[0]["id"] == "web-search"

    def test_check_compatibility(self, tmp_path):
        """check_compatibility should verify platform support."""
        catalog_file = _create_test_catalog(tmp_path)
        catalog = SkillCatalog(catalog_path=catalog_file)
        assert catalog.check_compatibility("web-search", "zeroclaw") is True
        assert catalog.check_compatibility("sentiment-analysis", "nanoclaw") is False


class TestInstallUninstall:
    """Tests for SkillManager install and uninstall tracking."""

    def test_install_skill(self, tmp_path):
        """install should track the skill as installed."""
        catalog_file = _create_test_catalog(tmp_path)
        catalog = SkillCatalog(catalog_path=catalog_file)
        installed_file = tmp_path / "installed.json"
        mgr = SkillManager(catalog, installed_path=installed_file)

        result = mgr.install("web-search", "zeroclaw")
        assert result["status"] == "installed"
        assert mgr.is_installed("web-search", "zeroclaw")

    def test_uninstall_skill(self, tmp_path):
        """uninstall should remove the skill from the installed list."""
        catalog_file = _create_test_catalog(tmp_path)
        catalog = SkillCatalog(catalog_path=catalog_file)
        installed_file = tmp_path / "installed.json"
        mgr = SkillManager(catalog, installed_path=installed_file)

        mgr.install("web-search", "zeroclaw")
        result = mgr.uninstall("web-search", "zeroclaw")
        assert result["status"] == "uninstalled"
        assert not mgr.is_installed("web-search", "zeroclaw")

    def test_install_incompatible_platform(self, tmp_path):
        """install on incompatible platform should return error."""
        catalog_file = _create_test_catalog(tmp_path)
        catalog = SkillCatalog(catalog_path=catalog_file)
        installed_file = tmp_path / "installed.json"
        mgr = SkillManager(catalog, installed_path=installed_file)

        result = mgr.install("sentiment-analysis", "nanoclaw")
        assert result["status"] == "error"


class TestBundleInstallation:
    """Tests for bundle installation."""

    def test_install_bundle(self, tmp_path):
        """Bundle install should install all skills in the bundle."""
        catalog_file = _create_test_catalog(tmp_path)
        catalog = SkillCatalog(catalog_path=catalog_file)
        installed_file = tmp_path / "installed.json"
        mgr = SkillManager(catalog, installed_path=installed_file)
        bundle_mgr = BundleManager(catalog, mgr)

        result = bundle_mgr.install_bundle("dev-bundle", "zeroclaw")
        assert result["status"] == "completed"
        assert result["installed"] == 2
        assert mgr.is_installed("web-search", "zeroclaw")
        assert mgr.is_installed("code-review", "zeroclaw")

    def test_install_missing_bundle(self, tmp_path):
        """Installing a nonexistent bundle should return error."""
        catalog_file = _create_test_catalog(tmp_path)
        catalog = SkillCatalog(catalog_path=catalog_file)
        installed_file = tmp_path / "installed.json"
        mgr = SkillManager(catalog, installed_path=installed_file)
        bundle_mgr = BundleManager(catalog, mgr)

        result = bundle_mgr.install_bundle("nonexistent-bundle", "zeroclaw")
        assert result["status"] == "error"
