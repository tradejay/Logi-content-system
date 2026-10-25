"""Common execution context and standardized step result data structures.

All steps in the insights pipeline operate against an ExecutionContext and return
a standardized StepResult.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from services.blog_performance.insights.tracker import StepTracker, save_atomic_json


@dataclass
class StepResult:
    """Standardized outcome returned by every pipeline step."""
    status: str  # 'succeeded', 'waiting', 'blocked', 'failed', 'skipped'
    message: str = ""
    artifacts: Dict[str, Any] = field(default_factory=dict)
    metrics: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    required_inputs: List[str] = field(default_factory=list)
    worker_task_id: Optional[str] = None

    def is_success(self) -> bool:
        return self.status in ['succeeded', 'skipped']


class ExecutionContext:
    """Bounded, thread-safe runtime context passed to all pipeline steps."""
    def __init__(
        self,
        run_id: str,
        config: Dict[str, Any],
        config_hash: str,
        run_dir: Path,
        root: Path,
        state: Dict[str, Any],
        manifest: Dict[str, Any],
        tracker: Optional[StepTracker] = None
    ):
        self.run_id = run_id
        self.config = config
        self.config_hash = config_hash
        self.run_dir = Path(run_dir)
        self.root = Path(root)
        self.state = state
        self.manifest = manifest
        self.tracker = tracker
        self.test_only = bool(config.get('test_only', False))

    @property
    def is_online(self) -> bool:
        return self.config.get('execution', {}).get('mode') == 'online'

    @property
    def is_offline(self) -> bool:
        return not self.is_online

    @property
    def depth(self) -> int:
        return self.config.get('execution', {}).get('depth', 30)

    @property
    def start_step(self) -> str:
        return self.config.get('execution', {}).get('start_step', 'preflight')

    @property
    def stop_step(self) -> str:
        return self.config.get('execution', {}).get('stop_step', 'activation')

    @property
    def panel_queries(self) -> List[Dict[str, Any]]:
        # Check manifest first, then config
        if self.manifest and self.manifest.get('selected_queries'):
            return self.manifest['selected_queries']
        return self.config.get('panel', {}).get('queries') or []

    @property
    def common_queries(self) -> List[str]:
        return [q['keyword'] for q in self.panel_queries if q.get('panel') == 'common']

    @property
    def product_queries(self) -> List[str]:
        return [q['keyword'] for q in self.panel_queries if q.get('panel') == 'products']

    @property
    def has_common(self) -> bool:
        return len(self.common_queries) > 0

    @property
    def has_products(self) -> bool:
        return len(self.product_queries) > 0

    def update_state(self, stage: str, err: Optional[str] = None) -> None:
        """Atomically persist state update."""
        self.state['stage'] = stage
        self.state['updated_at'] = datetime.now(timezone.utc).isoformat()
        if err:
            self.state['errors'].append(str(err))
        save_atomic_json(self.run_dir / 'state.json', self.state)

    def save_manifest(self) -> None:
        """Atomically persist manifest update."""
        save_atomic_json(self.run_dir / 'manifest.json', self.manifest)

    def is_step_completed(self, step_name: str) -> bool:
        """Check if a step was already successfully finished and has valid required artifacts."""
        steps_state = self.state.get('steps', {})
        if step_name == 'preflight':
            return steps_state.get('preflight') == 'completed'
        elif step_name == 'panel_preparation':
            return bool(steps_state.get('query_panel_ready')) and (self.run_dir / 'manifest.json').exists()
        elif step_name == 'collection_dispatch':
            needs_c = self.has_common and not (self.run_dir / 'common/input.json').exists()
            needs_p = self.has_products and not (self.run_dir / 'products/input.json').exists()
            return not needs_c and not needs_p
        elif step_name == 'common_import':
            return not self.has_common or bool(steps_state.get('common_imported')) or (self.run_dir / 'common/body-analysis/report.json').exists() or (self.run_dir / 'common/report.json').exists()
        elif step_name == 'products_import':
            return not self.has_products or bool(steps_state.get('products_imported')) or (self.run_dir / 'products/manifest.json').exists()
        elif step_name == 'body_collection':
            c_ok = not self.has_common or bool(steps_state.get('common_bodies_analyzed')) or (self.run_dir / 'common/body-analysis/bodies.json').exists()
            p_ok = not self.has_products or bool(steps_state.get('products_bodies_analyzed')) or (self.run_dir / 'products/body-analysis/bodies.json').exists()
            return c_ok and p_ok
        elif step_name == 'term_review':
            return bool(steps_state.get('terms_reviewed')) or (self.run_dir / 'ai-decisions.json').exists()
        elif step_name == 'merge':
            c_ok = not self.has_common or bool(steps_state.get('common_merged')) or (self.run_dir / 'common/body-analysis/report.json').exists()
            p_ok = not self.has_products or bool(steps_state.get('products_merged')) or (self.run_dir / 'products/body-analysis/product-report.json').exists()
            return c_ok and p_ok
        elif step_name == 'top5_audit':
            return bool(steps_state.get('top5_audited'))
        elif step_name == 'html_build':
            return bool(steps_state.get('html_built')) or (self.run_dir / 'report.html').exists()
        elif step_name == 'qa_verification':
            return bool(steps_state.get('qa_verified'))
        elif step_name == 'activation':
            return bool(steps_state.get('activated'))
        return False
