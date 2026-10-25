function doPost(e) {
    try {
        var data = JSON.parse(e.postData.contents);
        var logs = data.logs;

        // 로깅할 구글 시트 ID 
        var SPREADSHEET_ID = "YOUR_GOOGLE_SPREADSHEET_ID";
        var ss = SpreadsheetApp.openById(SPREADSHEET_ID);
        var sheet = ss.getSheets()[0];

        // 시트가 비어있으면 헤더(컬럼명) 자동 생성
        if (sheet.getLastRow() === 0) {
            sheet.appendRow([
                "Timestamp", "SessionID", "Action", "QueryRaw",
                "Mapped", "Status", "MissTokens", "ResultCount",
                "ZeroHitReason", "Filters", "Category", "LatencyMs", "UserAgent"
            ]);
        }

        // 로그 데이터 개별 행으로 추가
        logs.forEach(function (log) {
            var d = log.data || {};
            sheet.appendRow([
                log.timestamp,
                log.sessionId,
                log.action,
                d.queryRaw || "",
                JSON.stringify(d.queryMapped || []),
                d.mappingStatus || "",
                JSON.stringify(d.mappingMissTokens || []),
                d.resultCount !== undefined ? d.resultCount : 0,
                d.zeroHitReason || "",
                JSON.stringify(d.filters || []),
                d.category || "",
                d.latencyMs || 0,
                log.userAgent
            ]);
        });

        return ContentService.createTextOutput(JSON.stringify({ "result": "success" })).setMimeType(ContentService.MimeType.JSON);
    } catch (error) {
        return ContentService.createTextOutput(JSON.stringify({ "result": "error", "error": error.toString() })).setMimeType(ContentService.MimeType.JSON);
    }
}
