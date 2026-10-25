"""Migrate an explicitly selected local project's Drive auth without changing it."""
import argparse
import datetime
import io
import json
from pathlib import Path
import pickle
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.drive-deps'))


def reuse(source):
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    source=Path(source).resolve()
    config=json.loads((source/'client_secrets.json').read_text(encoding='utf-8-sig'))
    if not config.get('installed',{}).get('client_id'):
        raise ValueError('데스크톱 앱 OAuth 설정을 확인하세요.')
    class TokenReader(pickle.Unpickler):
        def find_class(self,module,name):
            allowed={('google.oauth2.credentials','Credentials'):Credentials,
                     ('datetime','datetime'):datetime.datetime,
                     ('datetime','timezone'):datetime.timezone,
                     ('datetime','timedelta'):datetime.timedelta}
            if (module,name) not in allowed:
                raise ValueError('지원하지 않는 인증 캐시 형식: '+module+'.'+name)
            return allowed[module,name]
    creds=TokenReader(io.BytesIO((source/'token.json').read_bytes())).load()
    if not isinstance(creds,Credentials) or creds.client_id!=config['installed']['client_id']:
        raise ValueError('인증 토큰과 OAuth 클라이언트가 일치하지 않습니다.')
    if not creds.has_scopes(['https://www.googleapis.com/auth/drive']):
        raise ValueError('기존 인증에 필요한 Drive 권한이 없습니다. 다시 연결하세요.')
    if not creds.valid:
        if not creds.refresh_token:
            raise ValueError('다시 로그인해야 합니다.')
        try:creds.refresh(Request())
        except Exception:raise ValueError('기존 인증을 갱신할 수 없습니다. 다시 로그인해야 합니다.') from None
    service=build('drive','v3',credentials=creds)
    folder=service.files().get(fileId='14moKusN05Fusu8MbtHVUDSTFMvhMmUIp',
        fields='capabilities(canAddChildren)',supportsAllDrives=True).execute()
    if not folder.get('capabilities',{}).get('canAddChildren'):
        raise ValueError('기존 인증 계정에 블로그 자산 폴더 편집 권한이 없습니다.')
    destination=ROOT/'config';destination.mkdir(exist_ok=True)
    for name,value in [('google-drive.oauth-client.json',json.dumps(config,ensure_ascii=False)),
                       ('google-drive.token.json',creds.to_json())]:
        path=destination/name;tmp=path.with_suffix('.tmp')
        tmp.write_text(value,encoding='utf-8');tmp.replace(path)
    print('기존 OAuth 인증 재사용 완료. 대상 폴더 편집 권한 확인 완료. 원본 프로젝트는 변경하지 않았습니다.')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('source');args=parser.parse_args()
    try:reuse(args.source)
    except ValueError as e:parser.exit(1,str(e)+'\n')
