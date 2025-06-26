import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ['https://www.googleapis.com/auth/drive.file']
SERVICE_ACCOUNT_FILE = os.path.join(os.path.dirname(__file__), '..', 'service_account.json')
FOLDER_ID = '1kijLRigdV33vIHGBFPLjB7yqo7-N17JA'  # Your shared Google Drive folder

def get_service():
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    return build('drive', 'v3', credentials=credentials)

def upload_to_drive(file_path):
    service = get_service()
    file_metadata = {
        'name': os.path.basename(file_path),
        'parents': [FOLDER_ID]
    }
    media = MediaFileUpload(file_path, mimetype='application/zip')
    file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id,webViewLink'
    ).execute()
    return file
