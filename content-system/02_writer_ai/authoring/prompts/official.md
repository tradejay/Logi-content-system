# 로지텍 사실 검토 응답 계약
각 claim의 제품·기능·스펙·적용 조건을 공식 근거와 대조한다. JSON 객체만 반환한다: claims(array).
입력 claim마다 정확히 한 항목: id, verdict(confirmed/contradicted/insufficient_evidence/out_of_scope), evidence(string: 공식 문서 URL 및 관련 근거), detail(string).
근거를 찾지 못하면 insufficient_evidence. 단어 '일치'가 포함됐다는 이유로 통과시키지 않는다. contradicted 판정도 자동 지식 수정 명령이 아니며 사람이 검토할 차이 후보이다.
