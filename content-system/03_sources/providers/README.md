# Source Provider Architecture & Plug-in Specifications

## 1. 개요 (Overview)

본 디렉터리는 향후 **로지텍 공식문서 로컬 CLI**, Zoom/Microsoft/Google 공식 포털 API 등 다양한 외부/로컬 기술 문서 공급자를 시스템에 플러그인 형태로 연결하기 위한 Provider 인터페이스 정의 공간입니다.

### 핵심 설계 원칙
1. **콘센트 & 플러그 모델**: Provider 인터페이스(`BaseProvider`)와 표준 검색 결과 규격(`provider-search-result.schema.yaml`)을 선구축하여, 향후 CLI 환경 정보가 주어졌을 때 기존 Research/Knowledge/Writer/QA 파이프라인의 변경 없이 즉시 연결합니다.
2. **Zero Dependency on External Providers**: 외부 Provider가 등록되지 않거나 CLI가 미가용 상태일 때도, 시스템은 내장 `LocalKnowledgeFallbackProvider`를 통해 기존 `03_sources/` 및 Knowledge Pack만으로 100% 정상 작동합니다.

---

## 2. 공급자 설정 파일 스키마 (`*.yaml`)

향후 공급자 추가 시 본 디렉터리에 `<provider_id>.yaml`을 생성합니다:

```yaml
provider_id: logitech-local
name: "Logitech B2B Local Documentation CLI"
authority: "OFFICIAL_VENDOR"
access_type: "local_cli"

supported_document_types:
  - GUIDE
  - SPEC
  - WHITE_PAPER
  - RELEASE_NOTE
  - SUPPORT

capabilities:
  search: true
  fetch_document: true
  fetch_section: true
  version_lookup: true

freshness_policy:
  short_ttl_days: 90      # Cloud / Admin UI
  medium_ttl_days: 180    # Firmware / Compatibility
  long_ttl_days: 365      # Hardware Specifications

adapter:
  type: "cli"
  entrypoint: "scripts.providers.logitech_provider"
  config:
    cli_command: "logi-docs"
    root_path: "C:/docs/logitech"
```

---

## 3. 표준 검색 결과 Contract (SearchResult)

모든 Provider의 `search(query, **kwargs)` 메서드는 반드시 다음 규격의 리스트를 반환해야 합니다:

```json
{
  "query": "RightSight 2 Speaker View 거리",
  "provider_id": "logitech-local",
  "results": [
    {
      "document_id": "DOC-LOGI-RS2-001",
      "title": "RightSight 2 Implementation and Tuning Guide",
      "document_type": "GUIDE",
      "section": "Recommended Operating Distances",
      "snippet": "Speaker View is recommended for distances up to 4.5 meters...",
      "source_location": "file:///C:/docs/logitech/rightsight2.md#L45",
      "version": "2.1.0",
      "published_at": "2025-11-10",
      "updated_at": "2026-03-15",
      "relevance_score": 0.94
    }
  ]
}
```
