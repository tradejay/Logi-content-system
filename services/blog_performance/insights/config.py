"""Configuration management and schema validation for the insights pipeline.

Strictly schema-driven:
- schema_version: insights-pipeline-config-v1
- Presets catalog (operational, mini-tests, replay, depth variation)
- Whitelist validation, bounded ranges, safe paths (no arbitrary shell/code execution)
- Hash generation for deterministic execution and tamper-proof resumes
"""
import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[3]
PRESETS_DIR = Path(__file__).resolve().parent / 'presets'

SCHEMA_VERSION = "insights-pipeline-config-v1"

ALLOWED_STEPS = [
    'preflight',
    'panel_preparation',
    'collection_dispatch',
    'common_import',
    'products_import',
    'body_collection',
    'term_review',
    'merge',
    'top5_audit',
    'html_build',
    'qa_verification',
    'activation'
]

COMMON_KEYWORDS = [
    "화상회의",
    "화상회의 장비",
    "화상회의 구축",
    "화상회의 솔루션",
    "회의실 화상카메라",
    "화상회의 장비 추천",
    "화상회의 시스템 구축"
]

ALLOWED_TOP_KEYS = {
    '$schema',
    'schema_version',
    'preset_id',
    'description',
    'test_only',
    'execution',
    'panel',
    'inputs',
    'qa',
    'storage'
}

ALLOWED_EXECUTION_KEYS = {'mode', 'start_step', 'stop_step', 'depth', 'max_retries'}
ALLOWED_PANEL_KEYS = {'type', 'queries', 'limit'}
ALLOWED_INPUTS_KEYS = {'common_json', 'products_json', 'ai_decisions_json'}
ALLOWED_QA_KEYS = {'check_browser', 'min_tables', 'require_top5_audit', 'min_audit_rows'}
ALLOWED_STORAGE_KEYS = {'run_dir', 'html_output'}


class ConfigValidationError(ValueError):
    """Raised when configuration violates schema or constraints."""
    def __init__(self, issues: List[str]):
        self.issues = issues
        super().__init__("; ".join(issues))


def compute_config_hash(config: Dict[str, Any]) -> str:
    """Compute deterministic SHA-256 digest of normalized config."""
    # Exclude non-functional metadata if present
    clean = copy.deepcopy(config)
    clean.pop('$schema', None)
    clean.pop('description', None)
    canonical = json.dumps(clean, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def _is_safe_path(p: str) -> bool:
    if not p:
        return True
    p_str = str(p)
    if '..' in p_str:
        return False
    # Check for shell metacharacters
    if any(c in p_str for c in ['|', '&', ';', '`', '$', '<', '>', '\n', '\r']):
        return False
    # Check Windows dangerous system directories
    lower = p_str.lower().replace('\\', '/')
    if '/windows/' in lower or '/system32/' in lower:
        return False
    return True


def get_registered_catalog_keywords(root: Path = ROOT) -> Dict[str, dict]:
    """Retrieve mapping of keyword -> product info from product-search-catalog.json."""
    cat_path = root / 'services/blog_performance/product-search-catalog.json'
    if not cat_path.exists():
        cat_path = ROOT / 'services/blog_performance/product-search-catalog.json'
    if not cat_path.exists():
        return {}
    catalog = json.loads(cat_path.read_text(encoding='utf-8'))
    result = {}
    for p in catalog:
        ko_queries = [q for q in p.get('queries', []) if any('가' <= c <= '힣' for c in q)]
        kw = ko_queries[0] if ko_queries else p['product']
        result[kw] = {
            'panel': 'products',
            'keyword': kw,
            'product_id': p.get('product_id'),
            'brand': p.get('brand'),
            'product': p.get('product'),
            'report_group': 'small' if p.get('product_id') in {'VC-016', 'VC-017'} else (
                'medium' if p.get('product_id') in {'VC-009', 'VC-002', 'VC-011', 'VC-014', 'VC-005'} else
                ('bar' if p.get('group') in {'bar', 'large'} else p.get('group', 'small'))
            ),
            'catalog_group': p.get('group')
        }
    return result


def validate_config(raw_config: Dict[str, Any], root: Path = ROOT) -> Tuple[bool, Dict[str, Any], List[str]]:
    """Validate config against schema, bounded types, whitelisted keys, and security constraints."""
    issues = []
    if not isinstance(raw_config, dict):
        return False, {}, ["Configuration must be a JSON object (dict)"]

    # 1. Whitelist top-level keys
    extra_top = set(raw_config.keys()) - ALLOWED_TOP_KEYS
    if extra_top:
        issues.append(f"Disallowed top-level config keys: {sorted(list(extra_top))}")

    # 2. Schema version
    version = raw_config.get('schema_version')
    if version != SCHEMA_VERSION:
        issues.append(f"Invalid schema_version '{version}'. Expected '{SCHEMA_VERSION}'")

    # 3. test_only
    test_only = raw_config.get('test_only')
    if not isinstance(test_only, bool):
        issues.append("Field 'test_only' must be a boolean (true or false)")

    # 4. execution
    execution = raw_config.get('execution', {})
    if not isinstance(execution, dict):
        issues.append("Field 'execution' must be an object")
        execution = {}
    else:
        extra_exec = set(execution.keys()) - ALLOWED_EXECUTION_KEYS
        if extra_exec:
            issues.append(f"Disallowed execution keys: {sorted(list(extra_exec))}")

    mode = execution.get('mode', 'offline')
    if mode not in ['offline', 'online']:
        issues.append(f"execution.mode must be 'offline' or 'online', got '{mode}'")

    start_step = execution.get('start_step', 'preflight')
    stop_step = execution.get('stop_step', 'activation')
    if start_step not in ALLOWED_STEPS:
        issues.append(f"execution.start_step '{start_step}' unknown. Allowed: {ALLOWED_STEPS}")
    if stop_step not in ALLOWED_STEPS:
        issues.append(f"execution.stop_step '{stop_step}' unknown. Allowed: {ALLOWED_STEPS}")
    if start_step in ALLOWED_STEPS and stop_step in ALLOWED_STEPS:
        if ALLOWED_STEPS.index(start_step) > ALLOWED_STEPS.index(stop_step):
            issues.append(f"start_step '{start_step}' cannot be after stop_step '{stop_step}'")

    depth = execution.get('depth', 30)
    if not isinstance(depth, int) or depth < 1 or depth > 100:
        issues.append(f"execution.depth must be an integer between 1 and 100, got {depth}")

    max_retries = execution.get('max_retries', 1)
    if not isinstance(max_retries, int) or max_retries < 0 or max_retries > 10:
        issues.append(f"execution.max_retries must be an integer between 0 and 10, got {max_retries}")

    # 5. panel
    panel = raw_config.get('panel', {})
    if not isinstance(panel, dict):
        issues.append("Field 'panel' must be an object")
        panel = {}
    else:
        extra_panel = set(panel.keys()) - ALLOWED_PANEL_KEYS
        if extra_panel:
            issues.append(f"Disallowed panel keys: {sorted(list(extra_panel))}")

    ptype = panel.get('type', 'catalog_full')
    if ptype not in ['catalog_full', 'explicit_queries']:
        issues.append(f"panel.type must be 'catalog_full' or 'explicit_queries', got '{ptype}'")

    limit = panel.get('limit', 34 if ptype == 'catalog_full' else 2)
    if not isinstance(limit, int) or limit < 1 or limit > 34:
        issues.append(f"panel.limit must be an integer between 1 and 34, got {limit}")

    catalog_map = get_registered_catalog_keywords(root)
    normalized_queries = []

    if ptype == 'explicit_queries':
        queries = panel.get('queries', [])
        if not isinstance(queries, list) or len(queries) == 0:
            issues.append("panel.queries must be a non-empty list for 'explicit_queries'")
        elif len(queries) > limit:
            issues.append(f"panel.queries count ({len(queries)}) exceeds limit ({limit})")
        else:
            seen_keywords = set()
            for q in queries:
                kw = q.get('keyword') if isinstance(q, dict) else str(q)
                if not kw or not kw.strip():
                    issues.append("Query keyword cannot be empty")
                    continue
                kw = kw.strip()
                if kw in seen_keywords:
                    issues.append(f"Duplicate query keyword rejected: '{kw}'")
                    continue
                seen_keywords.add(kw)

                if kw in COMMON_KEYWORDS:
                    normalized_queries.append({
                        'panel': 'common',
                        'keyword': kw,
                        'product_id': None,
                        'brand': None,
                        'product': None,
                        'report_group': 'common',
                        'catalog_group': None
                    })
                elif kw in catalog_map:
                    normalized_queries.append(catalog_map[kw])
                else:
                    issues.append(f"Query '{kw}' is not a registered panel query (must belong to 7 common keywords or product catalog)")

    # 6. inputs
    inputs = raw_config.get('inputs', {})
    if not isinstance(inputs, dict):
        issues.append("Field 'inputs' must be an object")
        inputs = {}
    else:
        extra_inputs = set(inputs.keys()) - ALLOWED_INPUTS_KEYS
        if extra_inputs:
            issues.append(f"Disallowed inputs keys: {sorted(list(extra_inputs))}")
        for k in ['common_json', 'products_json', 'ai_decisions_json']:
            val = inputs.get(k)
            if val is not None:
                if not isinstance(val, str):
                    issues.append(f"inputs.{k} must be a string path or null")
                elif not _is_safe_path(val):
                    issues.append(f"inputs.{k} contains unsafe path: '{val}'")

    # 7. qa
    qa = raw_config.get('qa', {})
    if not isinstance(qa, dict):
        issues.append("Field 'qa' must be an object")
        qa = {}
    else:
        extra_qa = set(qa.keys()) - ALLOWED_QA_KEYS
        if extra_qa:
            issues.append(f"Disallowed qa keys: {sorted(list(extra_qa))}")

    # 8. storage
    storage = raw_config.get('storage', {})
    if storage and isinstance(storage, dict):
        extra_storage = set(storage.keys()) - ALLOWED_STORAGE_KEYS
        if extra_storage:
            issues.append(f"Disallowed storage keys: {sorted(list(extra_storage))}")
        for k in ['run_dir', 'html_output']:
            val = storage.get(k)
            if val is not None and not _is_safe_path(str(val)):
                issues.append(f"storage.{k} contains unsafe path: '{val}'")

    if issues:
        return False, {}, issues

    # Assemble canonical sanitized configuration
    canonical: Dict[str, Any] = {
        'schema_version': SCHEMA_VERSION,
        'preset_id': raw_config.get('preset_id'),
        'description': raw_config.get('description', ''),
        'test_only': bool(test_only),
        'execution': {
            'mode': mode,
            'start_step': start_step,
            'stop_step': stop_step,
            'depth': depth,
            'max_retries': max_retries
        },
        'panel': {
            'type': ptype,
            'queries': normalized_queries if ptype == 'explicit_queries' else None,
            'limit': limit
        },
        'inputs': {
            'common_json': inputs.get('common_json'),
            'products_json': inputs.get('products_json'),
            'ai_decisions_json': inputs.get('ai_decisions_json')
        },
        'qa': {
            'check_browser': bool(qa.get('check_browser', not test_only)),
            'min_tables': qa.get('min_tables', 1),
            'require_top5_audit': bool(qa.get('require_top5_audit', True if not test_only else False))
        },
        'storage': {
            'run_dir': storage.get('run_dir') if storage else None,
            'html_output': storage.get('html_output') if storage else None
        }
    }

    return True, canonical, []


def load_preset(preset_id: str, root: Path = ROOT) -> Dict[str, Any]:
    """Load and validate preset from presets folder."""
    clean_id = preset_id.removesuffix('.json')
    preset_file = PRESETS_DIR / f"{clean_id}.json"
    if not preset_file.exists():
        # Fallback to config/insights_presets if exists
        alt_file = root / f"config/insights_presets/{clean_id}.json"
        if alt_file.exists():
            preset_file = alt_file
        else:
            raise FileNotFoundError(f"Preset '{preset_id}' not found at {preset_file}")

    raw = json.loads(preset_file.read_text(encoding='utf-8'))
    valid, canonical, issues = validate_config(raw, root=root)
    if not valid:
        raise ConfigValidationError(issues)
    return canonical


def list_presets(root: Path = ROOT) -> List[Dict[str, Any]]:
    """List all available presets with summary."""
    presets = []
    for f in sorted(PRESETS_DIR.glob('*.json')):
        try:
            cfg = json.loads(f.read_text(encoding='utf-8'))
            presets.append({
                'preset_id': cfg.get('preset_id', f.stem),
                'description': cfg.get('description', ''),
                'test_only': cfg.get('test_only', False),
                'panel_type': cfg.get('panel', {}).get('type'),
                'file': str(f.relative_to(root)) if root in f.parents else str(f)
            })
        except Exception:
            pass
    return presets


def build_config_from_args(args: Any, root: Path = ROOT) -> Dict[str, Any]:
    """
    Construct a validated canonical config from CLI arguments.
    Supports --preset, --config, and legacy CLI flags (--test, --query, --queries, --online, --offline, etc.)
    """
    # 1. Direct config file
    if getattr(args, 'config', None):
        cfg_path = Path(args.config)
        if not cfg_path.is_absolute():
            cfg_path = root / cfg_path
        if not cfg_path.exists():
            raise FileNotFoundError(f"Config file not found: {cfg_path}")
        raw = json.loads(cfg_path.read_text(encoding='utf-8'))
        valid, canonical, issues = validate_config(raw, root=root)
        if not valid:
            raise ConfigValidationError(issues)
        return canonical

    # 2. Preset reference
    if getattr(args, 'preset', None):
        cfg = load_preset(args.preset, root=root)
        # Apply command-line overrides if given
        if getattr(args, 'offline', None) is not None:
            cfg['execution']['mode'] = 'offline' if args.offline else 'online'
        if getattr(args, 'common_json', None):
            cfg['inputs']['common_json'] = str(args.common_json)
        if getattr(args, 'products_json', None):
            cfg['inputs']['products_json'] = str(args.products_json)
        if getattr(args, 'ai_decisions', None):
            cfg['inputs']['ai_decisions_json'] = str(args.ai_decisions)
        return cfg

    # 3. Construct from individual CLI flags
    is_test = bool(getattr(args, 'test', False) or getattr(args, 'test_only', False))
    raw_queries = []
    if getattr(args, 'query', None):
        raw_queries.extend(args.query if isinstance(args.query, list) else [args.query])
    if getattr(args, 'queries', None):
        raw_queries.extend(args.queries)

    if raw_queries:
        is_test = True

    limit = getattr(args, 'query_limit', None) or (len(raw_queries) if raw_queries else (2 if is_test else 34))

    offline = getattr(args, 'offline', True)
    mode = 'offline' if offline else 'online'

    raw_dict = {
        'schema_version': SCHEMA_VERSION,
        'preset_id': 'cli-generated',
        'description': 'CLI generated configuration',
        'test_only': is_test,
        'execution': {
            'mode': mode,
            'start_step': getattr(args, 'start_step', 'preflight') or 'preflight',
            'stop_step': getattr(args, 'stop_step', 'activation') or 'activation',
            'depth': getattr(args, 'depth', 30) or 30,
            'max_retries': getattr(args, 'max_retries', 1) or 1
        },
        'panel': {
            'type': 'explicit_queries' if (is_test and raw_queries) else ('explicit_queries' if is_test else 'catalog_full'),
            'queries': raw_queries if raw_queries else (['화상회의'] if is_test else None),
            'limit': limit
        },
        'inputs': {
            'common_json': str(args.common_json) if getattr(args, 'common_json', None) else None,
            'products_json': str(args.products_json) if getattr(args, 'products_json', None) else None,
            'ai_decisions_json': str(args.ai_decisions) if getattr(args, 'ai_decisions', None) else None
        },
        'qa': {
            'check_browser': not is_test,
            'min_tables': 1,
            'require_top5_audit': not is_test
        }
    }

    valid, canonical, issues = validate_config(raw_dict, root=root)
    if not valid:
        raise ConfigValidationError(issues)
    return canonical
