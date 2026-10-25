"""Exercise Drive gates with mocked SDK; never load production credentials."""
import ast
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock


class DriveGateTests(unittest.TestCase):
    def setUp(self):
        tree=ast.parse(Path('services/gdrive_sync.py').read_text(encoding='utf-8'))
        definition=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='GoogleDriveSync')
        namespace={'os':os,'USER_TOKEN_FILE':'nonexistent-token-for-test','CREDENTIALS_FILE':'unused','DRIVE_FOLDER_ID':'unused','MediaFileUpload':Mock()}
        exec(compile(ast.Module(body=[definition],type_ignores=[]),'gdrive-isolated','exec'),namespace)
        self.drive=object.__new__(namespace['GoogleDriveSync'])
        self.drive.service=Mock();self.drive.auth_type='service_account';self.drive.last_error=None
        self.drive.folder_id='folder';self.drive.image_map={}
        temp=tempfile.NamedTemporaryFile(delete=False,dir='scratch/test-tmp');temp.write(b'image');temp.close()
        self.file=temp.name;self.addCleanup(lambda:os.unlink(self.file))

    def test_service_account_my_drive_blocked_before_upload(self):
        self.drive.service.files().get().execute.return_value={}
        self.assertIsNone(self.drive.upload_file(self.file,require_public=True))
        self.assertIn('OAuth',self.drive.last_error)
        self.drive.service.files().create.assert_not_called()

    def test_unverified_public_permission_blocks_success(self):
        self.drive.auth_type='user'
        self.drive.get_or_create_folder=Mock(return_value='folder')
        self.drive.service.files().create().execute.return_value={'id':'file'}
        self.drive.service.permissions().create().execute.side_effect=RuntimeError('permission denied')
        self.drive.service.permissions().list().execute.return_value={'permissions':[]}
        self.assertIsNone(self.drive.upload_file(self.file,require_public=True))
        self.assertIn('공개',self.drive.last_error)
        self.assertEqual(self.drive.image_map,{})


if __name__=='__main__':unittest.main()
