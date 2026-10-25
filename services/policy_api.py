"""Local single-owner policy editor endpoints (not a multi-user auth system)."""
from pathlib import Path
from urllib.parse import urlsplit
from flask import Blueprint, jsonify, request, send_from_directory
from services.policy_manager import PolicyManager, PolicyError, PolicyConflict

ROOT = Path(__file__).resolve().parents[1]
policy_bp = Blueprint('policy_editor', __name__)


@policy_bp.before_request
def guard_mutation():
    if request.method not in ('GET', 'HEAD', 'OPTIONS'):
        origin = request.headers.get('Origin')
        if origin and urlsplit(origin).netloc != request.host:
            return jsonify(error='다른 사이트에서 정책을 변경할 수 없습니다.'), 403
        if not request.is_json or request.headers.get('X-Policy-Editor') != '1':
            return jsonify(error='정책 편집기 JSON 요청이 필요합니다.'), 400


@policy_bp.errorhandler(PolicyConflict)
def conflict(error):
    return jsonify(error=str(error)), 409


@policy_bp.errorhandler(PolicyError)
def invalid(error):
    return jsonify(error=str(error)), 400


def manager():
    return PolicyManager(ROOT)


def payload():
    data = request.get_json()
    if not isinstance(data, dict):
        raise PolicyError('JSON 객체가 필요합니다.')
    return data


@policy_bp.get('/content-ops/policies')
def page():
    return send_from_directory(ROOT / 'static', 'policy-editor.html')


@policy_bp.get('/api/content-system/policies')
def list_policies():
    return jsonify(manager().public())


@policy_bp.post('/api/content-system/policies')
def create_policy():
    data = payload()
    return jsonify(manager().create(data.get('policy'), data.get('expected_revision')))


@policy_bp.put('/api/content-system/policies/<policy_id>')
def save_policy(policy_id):
    data = payload()
    return jsonify(manager().save(policy_id, data.get('policy'), data.get('expected_revision')))


@policy_bp.get('/api/content-system/policy-preview')
def preview():
    return jsonify(manager().preview())


@policy_bp.post('/api/content-system/policies/<policy_id>/split')
def split_policy(policy_id):
    data = payload()
    return jsonify(manager().split(policy_id, data.get('texts'), data.get('expected_revision'), data.get('review_note')))


@policy_bp.post('/api/content-system/policy-candidates')
def build():
    data = payload()
    return jsonify(manager().build(data.get('expected_revision'), data.get('reviewer'), data.get('review_note')))


@policy_bp.post('/api/content-system/policy-activate')
def activate():
    data = payload()
    return jsonify(manager().activate(data.get('release_id'), data.get('expected_active')))


@policy_bp.get('/api/content-system/policy-query')
def query_policies():
    from services.policy_query import PolicyQueryEngine
    topic = request.args.get('topic', 'product_recommendation')
    include_drafts = request.args.get('include_drafts', 'true').lower() in ('1', 'true', 'yes')
    engine = PolicyQueryEngine(ROOT)
    return jsonify(engine.query_by_topic(topic, include_drafts=include_drafts))

