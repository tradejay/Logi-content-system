"""One-time Google account authorization for the existing blog asset folder."""
import argparse
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.drive-deps'))


def main():
    parser=argparse.ArgumentParser(description='Google Drive 일반 계정 최초 연결')
    parser.add_argument('--port',type=int,default=5015)
    args=parser.parse_args()
    client=ROOT/'config/google-drive.oauth-client.json'
    token=ROOT/'config/google-drive.token.json'
    if not client.is_file():
        parser.exit(1,'Google Cloud에서 OAuth 클라이언트(데스크톱 앱) JSON을 다운로드하고\n'
                      f'{client}\n에 저장한 뒤 다시 실행하세요. 서비스 계정 JSON/API 키와는 다릅니다.\n')
    from google_auth_oauthlib.flow import InstalledAppFlow
    flow=InstalledAppFlow.from_client_secrets_file(str(client),scopes=['https://www.googleapis.com/auth/drive'])
    credentials=flow.run_local_server(host='127.0.0.1',port=args.port,open_browser=False,
        authorization_prompt_message='아래 URL을 브라우저에서 열고 자산 폴더에 접근 가능한 Google 계정으로 로그인하세요:\n{url}',
        success_message='Google Drive 연결 완료. 이 창을 닫고 승인 화면으로 돌아가세요.',timeout_seconds=300)
    from googleapiclient.discovery import build
    service=build('drive','v3',credentials=credentials)
    folder=service.files().get(fileId='14moKusN05Fusu8MbtHVUDSTFMvhMmUIp',fields='capabilities(canAddChildren)',supportsAllDrives=True).execute()
    if not folder.get('capabilities',{}).get('canAddChildren'):
        parser.exit(1,'로그인한 계정에 블로그 자산 폴더의 편집 권한이 없습니다. 토큰을 저장하지 않았습니다.\n')
    temporary=token.with_suffix('.tmp')
    temporary.write_text(credentials.to_json(),encoding='utf-8');temporary.replace(token)
    print('연결 완료. 승인 화면에서 이미지 승인 버튼을 다시 누르세요.')


if __name__=='__main__':main()
