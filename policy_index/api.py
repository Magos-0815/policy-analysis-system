from __future__ import annotations

from flask import Flask, jsonify

from .crawler import PolicyCrawler
from .exporter import SnapshotExporter
from .policy_signal import PolicySignalCalculator
from .repository import PolicyRepository
from .runtime_guard import assert_policy_project_isolated
from .ssi_engine import StateSupportIntensityCalculator
from .ssi_engine.agent_review import AgentReviewStore
from .ssi_engine.storage import SSIStorage


def create_app() -> Flask:
    assert_policy_project_isolated()
    app = Flask(__name__)
    repository = PolicyRepository()
    ssi_storage = SSIStorage()
    agent_review_store = AgentReviewStore()

    @app.route("/health")
    def health():
        return jsonify({"success": True, "service": "china policy analyse", "status": "ok"})

    @app.route("/api/sources")
    def sources():
        return jsonify({"success": True, "data": PolicyCrawler(repository).sources()})

    @app.route("/api/documents")
    def documents():
        return jsonify({"success": True, "data": repository.list_documents()})

    @app.route("/api/index/policy-signal")
    def policy_signal():
        return jsonify({"success": True, "data": repository.load_index_snapshot()})

    @app.route("/api/index/state-support")
    def state_support():
        return jsonify({"success": True, "data": ssi_storage.load_snapshot()})

    @app.route("/api/support-observations")
    def support_observations():
        return jsonify({"success": True, "data": ssi_storage.load_observations()})

    @app.route("/api/methodology")
    def methodology():
        snapshot = ssi_storage.load_snapshot()
        return jsonify({"success": True, "data": snapshot.get("methodology", {})})

    @app.route("/api/agent-reviews")
    def agent_reviews():
        return jsonify({"success": True, "data": agent_review_store.list_reviews()})

    @app.route("/api/exports/latest")
    def exports_latest():
        return jsonify({"success": True, "data": SnapshotExporter(repository).export_latest()})

    @app.route("/api/index/rebuild", methods=["POST"])
    def rebuild_index():
        snapshot = PolicySignalCalculator(repository).build_snapshot()
        export = SnapshotExporter(repository).export_latest()
        return jsonify({"success": True, "data": {"snapshot": snapshot, "exports": export}})

    @app.route("/api/index/state-support/rebuild", methods=["POST"])
    def rebuild_state_support():
        snapshot = StateSupportIntensityCalculator(ssi_storage).build_snapshot()
        return jsonify({"success": True, "data": snapshot})

    return app
