"""
services/gdrive_sync.py
Google Drive Cloud CDN Uploader and Sync Service
Uses Google Cloud Service Account credentials (config/service_account.json)
Provides permanent image CDN URLs (sz=w1600) for Naver Blog publication.
"""

import os
import sys
import json
import time

_drive_dependencies = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.drive-deps')
if os.path.isdir(_drive_dependencies):
    sys.path.insert(0, _drive_dependencies)

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CREDENTIALS_FILE = os.path.join(BASE_DIR, "config", "service_account.json")
USER_TOKEN_FILE = os.path.join(BASE_DIR, "config", "google-drive.token.json")
IMAGE_MAP_FILE = os.path.join(BASE_DIR, "content-system", "03_sources", "image_map.json")

# Target Drive folder ID (Logitech Blog Asset Drive folder)
DRIVE_FOLDER_ID = "14moKusN05Fusu8MbtHVUDSTFMvhMmUIp"

class GoogleDriveSync:
    def __init__(self, credentials_file=CREDENTIALS_FILE, folder_id=DRIVE_FOLDER_ID):
        self.scopes = ['https://www.googleapis.com/auth/drive']
        self.service = None
        self.last_error = None
        self.auth_type = None
        self.credentials_file = credentials_file
        self.folder_id = folder_id
        self.folder_cache = {}
        self.image_map = self._load_image_map()
        self._authenticate()

    def _authenticate(self):
        if os.path.exists(USER_TOKEN_FILE):
            try:
                creds=Credentials.from_authorized_user_file(USER_TOKEN_FILE, self.scopes)
                if creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                    with open(USER_TOKEN_FILE,'w',encoding='utf-8') as stream:
                        stream.write(creds.to_json())
                self.service=build('drive','v3',credentials=creds)
                self.auth_type='user'
                print('[OK] [GDrive] Google account OAuth connected.')
                return
            except Exception:
                self.last_error='Google Drive 사용자 인증이 만료되거나 무효화됐습니다. 다시 연결하세요.'
                return
        if not os.path.exists(self.credentials_file):
            print(f"[WARN] [GDrive] Credentials file not found: {self.credentials_file}. Running in offline mode.")
            return

        try:
            creds = service_account.Credentials.from_service_account_file(
                self.credentials_file, scopes=self.scopes
            )
            self.service = build('drive', 'v3', credentials=creds)
            self.auth_type='service_account'
            print("[OK] [GDrive] Google Drive API initialized via Service Account.")
        except Exception as e:
            print(f"[WARN] [GDrive] Authentication failed: {e}. Running in offline mode.")
            self.service = None

    def _load_image_map(self):
        if os.path.exists(IMAGE_MAP_FILE):
            try:
                with open(IMAGE_MAP_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠️ [GDrive] Failed to load image_map.json: {e}")
        return {}

    def _save_image_map(self):
        try:
            os.makedirs(os.path.dirname(IMAGE_MAP_FILE), exist_ok=True)
            with open(IMAGE_MAP_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.image_map, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ [GDrive] Failed to save image_map.json: {e}")

    def get_or_create_folder(self, folder_name):
        """Finds or creates a subfolder."""
        if not self.service or not folder_name:
            return self.folder_id

        if folder_name in self.folder_cache:
            return self.folder_cache[folder_name]

        try:
            query = f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
            if self.folder_id:
                query += f" and '{self.folder_id}' in parents"

            results = self.service.files().list(
                q=query, fields="files(id)", supportsAllDrives=True, includeItemsFromAllDrives=True
            ).execute()
            files = results.get('files', [])

            if files:
                folder_id = files[0]['id']
            else:
                folder_metadata = {
                    'name': folder_name,
                    'mimeType': 'application/vnd.google-apps.folder'
                }
                if self.folder_id:
                    folder_metadata['parents'] = [self.folder_id]

                folder = self.service.files().create(
                    body=folder_metadata, fields='id', supportsAllDrives=True
                ).execute()
                folder_id = folder.get('id')

                # Public reader permission
                try:
                    self.service.permissions().create(
                        fileId=folder_id,
                        body={'type': 'anyone', 'role': 'reader'},
                        supportsAllDrives=True
                    ).execute()
                except Exception:
                    pass

            self.folder_cache[folder_name] = folder_id
            return folder_id
        except Exception as e:
            print(f"⚠️ [GDrive] Folder create/find error: {e}")
            return self.folder_id

    def upload_file(self, file_path, filename=None, subfolder_name='naver-blog-assets', require_public=False):
        """Uploads a local image file to Google Drive and returns high-resolution public CDN URL."""
        if self.auth_type!='user' and os.path.exists(USER_TOKEN_FILE):
            self._authenticate()
        if not filename:
            filename = os.path.basename(file_path)

        # Check existing mapping first
        if filename in self.image_map:
            if require_public:
                from urllib.parse import urlparse, parse_qs
                file_id=parse_qs(urlparse(self.image_map[filename]).query).get('id',[None])[0]
                if not file_id or not self._public_readable(file_id):
                    return None
            return self.image_map[filename]

        if not self.service or not os.path.exists(file_path):
            self.last_error=self.last_error or 'Google Drive 인증 또는 업로드 파일을 확인하세요.'
            return None

        try:
            self.last_error=None
            if self.auth_type=='service_account':
                folder=self.service.files().get(fileId=self.folder_id,fields='driveId',supportsAllDrives=True).execute()
                if not folder.get('driveId'):
                    self.last_error='현재 서비스 계정은 일반 Drive 폴더에 새 파일을 업로드할 수 없습니다. Google 계정 OAuth 연결이 필요합니다 (저장 용량 0).'
                    return None
            parent_id = self.get_or_create_folder(subfolder_name)
            file_metadata = {'name': filename}
            if parent_id:
                file_metadata['parents'] = [parent_id]

            media = MediaFileUpload(file_path, resumable=True)
            uploaded_file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, webContentLink',
                supportsAllDrives=True
            ).execute()

            file_id = uploaded_file.get('id')

            # Make public
            try:
                self.service.permissions().create(
                    fileId=file_id,
                    body={'type': 'anyone', 'role': 'reader'},
                    supportsAllDrives=True
                ).execute()
            except Exception as pe:
                print(f"[WARN] [GDrive] Permission notice: {pe}")

            if require_public and not self._public_readable(file_id):
                self.last_error='업로드했지만 공개 읽기 권한을 확인할 수 없어 승인하지 않았습니다.'
                print('[WARN] [GDrive] Public reader permission could not be verified; approval blocked.')
                return None

            # Direct CDN thumbnail link (1600px wide, high quality)
            cdn_url = f"https://drive.google.com/thumbnail?id={file_id}&sz=w1600"
            self.image_map[filename] = cdn_url
            self._save_image_map()

            print(f"[OK] [GDrive] Uploaded {filename} -> {cdn_url}")
            return cdn_url

        except Exception as e:
            self.last_error='Google Drive 업로드 요청 실패. 연결 계정의 폴더 권한·저장 용량을 확인하세요.'
            print(f"[ERROR] [GDrive] Upload error ({filename}): {e}")
            return None

    def _public_readable(self, file_id):
        if not self.service:
            return False
        try:
            result=self.service.permissions().list(fileId=file_id, fields='permissions(type,role)',supportsAllDrives=True).execute()
            return any(p.get('type')=='anyone' and p.get('role') in {'reader','commenter','writer'} for p in result.get('permissions',[]))
        except Exception:
            return False

    def resolve_cdn_url(self, image_key):
        """Resolves local or relative image name to public Google Drive CDN URL if mapped."""
        if not image_key:
            return None

        # Clean key
        cleaned_key = image_key.replace("\\", "/").strip()
        if cleaned_key.startswith("/assets/images/"):
            cleaned_key = cleaned_key.replace("/assets/images/", "")
        elif cleaned_key.startswith("assets/images/"):
            cleaned_key = cleaned_key.replace("assets/images/", "")

        # 1. Exact match in image_map
        if cleaned_key in self.image_map:
            return self.image_map[cleaned_key]

        # 2. Basename match
        basename = os.path.basename(cleaned_key)
        if basename in self.image_map:
            return self.image_map[basename]

        # 3. Fuzzy search in image_map keys
        for k, url in self.image_map.items():
            if k.endswith(basename) or basename in k:
                return url

        return None


# Global singleton instance
gdrive_sync = GoogleDriveSync()


def test_sync():
    """Diagnostic test function."""
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
        tf.write(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc`\x00\x00\x00\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82")
        temp_path = tf.name

    try:
        url = gdrive_sync.upload_file(temp_path, filename=f"test_sync_{int(time.time())}.png")
        print("Test upload result URL:", url)
        return url
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


if __name__ == "__main__":
    test_sync()
