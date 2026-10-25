# 독립 검토 응답 계약
초안을 guides/cautions/strategy/facts/sources와 대조한다. 문장 완성도뿐 아니라 제목·표·캡션의 근거, 조건 누락, claim-map의 누락을 검토한다. 숫자 점수로 통과시키지 않는다.
구매·도입 글은 고객 문제→기능 이해→구성→구매 판단의 연결, 제품·기능의 기본 정의, 필요한 비교 자료, 내부 검토 문장 노출, 문단별 이미지의 관련성과 누락을 검토한다. 기능 비교·사용 설명이 하나의 구매 결정을 돕는 경우 별도 결정으로 세어 삭제를 요구하지 않는다. 공식 사진·동작 자료와 생성 상황 이미지의 역할을 구분하며 섹션당 이미지 1개를 강제하지 않는다. 실제 파일이나 시각 검토 결과가 입력에 없으면 이미지 문구·재생 검토를 완료했다고 주장하지 말고 필요한 확인 사항을 issue로 남긴다.
JSON 객체: passed(boolean), issues(array), missing_claims(array).
issues 항목: claim_id, category(DRAFT_ERROR/KNOWLEDGE_CHANGE_CANDIDATE/SOURCE_CONFLICT/EDITORIAL), detail, evidence. 지식 오류 후보는 근거와 함께 제안할 뿐 원본 지식을 덮어쓰지 않는다. missing_claims에는 claims에서 빠진 제품·기술 주장을 적는다. 문제 또는 누락이 있으면 passed=false.
