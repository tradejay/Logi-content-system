import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from services.content_pipeline import ContentPipeline, main

def export_naver_html(content_id):
    ContentPipeline().export(content_id)
    return True

if __name__ == "__main__":
    export_naver_html(sys.argv[1])
