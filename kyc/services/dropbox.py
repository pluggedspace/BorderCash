from functools import wraps
import dropbox
import os
import logging
import requests
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)

class DropboxTokenManager:
    CACHE_KEY = 'dropbox_access_token'
    TOKEN_REFRESH_LOCK = 'dropbox_token_refresh_lock'
    
    @staticmethod
    def refresh_token():
        """Refresh the Dropbox access token using the refresh token."""
        try:
            if cache.get(DropboxTokenManager.TOKEN_REFRESH_LOCK):
                logger.warning("Token refresh already in progress")
                return None
            
            cache.set(DropboxTokenManager.TOKEN_REFRESH_LOCK, True, timeout=30)
            
            refresh_token = os.getenv("DROPBOX_REFRESH_TOKEN")
            app_key = os.getenv("DROPBOX_APP_KEY")
            app_secret = os.getenv("DROPBOX_APP_SECRET")
            
            if not all([refresh_token, app_key, app_secret]):
                logger.error("Missing Dropbox credentials in environment")
                return None
            
            response = requests.post(
                'https://api.dropbox.com/oauth2/token',
                data={
                    'grant_type': 'refresh_token',
                    'refresh_token': refresh_token,
                    'client_id': app_key,
                    'client_secret': app_secret,
                }
            )
            
            if response.status_code == 200:
                new_token = response.json().get('access_token')
                if new_token:
                    DropboxTokenManager.store_token(new_token)
                    return new_token
            
            logger.error(f"Token refresh failed: {response.text}")
            return None
            
        except Exception as e:
            logger.error(f"Error refreshing token: {str(e)}")
            return None
        finally:
            cache.delete(DropboxTokenManager.TOKEN_REFRESH_LOCK)
    
    @staticmethod
    def store_token(token):
        """Store the token both in cache and environment variable."""
        try:
            cache.set(DropboxTokenManager.CACHE_KEY, token, timeout=3600)  # 1 hour cache
            os.environ["DROPBOX_OAUTH2_TOKEN"] = token
            logger.info("Successfully stored new Dropbox token")
            return True
        except Exception as e:
            logger.error(f"Error storing token: {str(e)}")
            return False
    
    @staticmethod
    def get_current_token():
        """Get the current token, first checking cache then environment."""
        return cache.get(DropboxTokenManager.CACHE_KEY) or os.getenv("DROPBOX_OAUTH2_TOKEN")

class DropboxService:
    _instance = None
    
    def __init__(self):
        self.client = None
        self.initialize_client()
    
    def initialize_client(self):
        """Initialize the Dropbox client with the latest token."""
        token = DropboxTokenManager.get_current_token()
        if token:
            self.client = dropbox.Dropbox(token)
        else:
            logger.error("No valid Dropbox token found!")

    @staticmethod
    def get_instance():
        """Singleton pattern to ensure only one instance of DropboxService exists."""
        if not DropboxService._instance:
            DropboxService._instance = DropboxService()
        return DropboxService._instance

    @staticmethod
    def handle_token_error(func):
        """Decorator to handle expired tokens and automatically refresh them."""
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            try:
                return func(self, *args, **kwargs)
            except dropbox.exceptions.AuthError:
                logger.warning("Dropbox token expired, attempting refresh...")
                
                new_token = DropboxTokenManager.refresh_token()
                if new_token:
                    self.initialize_client()  # Reinitialize client with new token
                    return func(self, *args, **kwargs)  # Retry request
                
                logger.error("Failed to refresh Dropbox token")
                raise Exception("Dropbox authentication failed - please contact support")
            except Exception as e:
                logger.error(f"Dropbox error: {str(e)}")
                raise
        return wrapper

    def validate_file(self, file_obj, file_name):
        """
        Validate the file size and format.
        Returns (True, None) if valid, otherwise (False, error_message).
        """
        MAX_SIZE_MB = 3
        ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".pdf"}

        # Check file extension
        ext = os.path.splitext(file_name)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            return False, "Invalid file format. Only PNG and JPG are allowed."

        # Check file size
        file_obj.seek(0, os.SEEK_END)  # Move to end of file to get size
        file_size_mb = file_obj.tell() / (1024 * 1024)  # Convert bytes to MB
        file_obj.seek(0)  # Reset file pointer

        if file_size_mb > MAX_SIZE_MB:
            return False, "File too large. Maximum allowed size is 3MB."

        return True, None

    

    @handle_token_error
    def upload_file(self, file_path, file_obj, file_name):
        """
        Upload a file to Dropbox with validation and return the file's direct URL.
        """
        try:
            is_valid, error = self.validate_file(file_obj, file_name)
            if not is_valid:
                return {"success": False, "error": error}

            # Upload the file
            self.client.files_upload(file_obj.read(), file_path, mode=dropbox.files.WriteMode("overwrite"))

            # Get a temporary link
            file_url = self.get_temporary_link(file_path)

            if file_url:
                return file_url  # Return only the file URL (not a dict)
            else:
                return None  # Handle failure properly
        except dropbox.exceptions.ApiError as e:
            logger.error(f"Dropbox upload error: {e}")
            return None  # Ensure failure cases return None



    @handle_token_error
    def get_temporary_link(self, file_path):
        """Generate a shortened Dropbox shared link."""
        try:
            shared_link_metadata = self.client.sharing_create_shared_link_with_settings(file_path)
            return shared_link_metadata.url.replace("?dl=0", "?raw=1")  # Convert to direct link
        except dropbox.exceptions.ApiError as e:
            logger.error(f"Failed to generate shared link: {e}")
            return None


    @handle_token_error
    def download_file(self, dropbox_path):
        """Download a file from Dropbox."""
        try:
            metadata, response = self.client.files_download(dropbox_path)
            return response.content
        except dropbox.exceptions.ApiError as e:
            logger.error(f"Dropbox download error: {e}")
            return None
