import os
import io
import cv2
import numpy as np
import pytesseract
import logging
from PIL import Image
from deepface import DeepFace
from skimage.metrics import structural_similarity as ssim
from .dropbox import DropboxService

logger = logging.getLogger(__name__)

class ImageProcessing:
    @staticmethod
    def download_from_dropbox(dropbox_path):
        """
        Fetches an image from Dropbox using centralized service.
        Returns BytesIO object containing the image data.
        """
        try:
            dropbox_service = DropboxService.get_instance()
            content = dropbox_service.download_file(dropbox_path)
            return io.BytesIO(content)
        except Exception as e:
            logger.error(f"Dropbox download error for path {dropbox_path}: {str(e)}")
            return None

    @staticmethod
    def extract_text(dropbox_path):
        """
        Extracts text from an image stored in Dropbox.
        Returns extracted text or empty string if processing fails.
        """
        image_file = ImageProcessing.download_from_dropbox(dropbox_path)
        if not image_file:
            logger.error(f"Failed to download image for text extraction: {dropbox_path}")
            return ""

        try:
            img = Image.open(image_file)
            text = pytesseract.image_to_string(img)
            logger.debug(f"Successfully extracted text from image: {dropbox_path}")
            return text
        except Exception as e:
            logger.error(f"Error extracting text from image {dropbox_path}: {str(e)}")
            return ""

    @staticmethod
    def check_image_integrity(dropbox_path):
        """
        Check image integrity using entropy analysis.
        Returns True if the image has sufficient detail/clarity.
        """
        image_file = ImageProcessing.download_from_dropbox(dropbox_path)
        if not image_file:
            logger.error(f"Failed to download image for integrity check: {dropbox_path}")
            return False

        try:
            image_data = image_file.read()
            image = cv2.imdecode(np.frombuffer(image_data, np.uint8), cv2.IMREAD_GRAYSCALE)
            if image is None:
                logger.error(f"Failed to decode image: {dropbox_path}")
                return False

            # Reset file pointer for potential reuse
            image_file.seek(0)
            
            # Compute image entropy (clarity check)
            entropy = -np.sum(image * np.log2(image + 1)) / (image.size)
            is_clear = entropy > 5.0
            
            if not is_clear:
                logger.warning(f"Image failed clarity check. Entropy: {entropy}")
            
            return is_clear

        except Exception as e:
            logger.error(f"Image integrity check failed for {dropbox_path}: {str(e)}")
            return False

    @staticmethod
    def compare_images(dropbox_path1, dropbox_path2):
        """
        Compare two images using SSIM.
        Returns True if images are sufficiently similar.
        """
        file1 = ImageProcessing.download_from_dropbox(dropbox_path1)
        file2 = ImageProcessing.download_from_dropbox(dropbox_path2)

        if not file1 or not file2:
            logger.error("Failed to download one or both images for comparison")
            return False

        try:
            img1_data = file1.read()
            img2_data = file2.read()
            
            img1 = cv2.imdecode(np.frombuffer(img1_data, np.uint8), cv2.IMREAD_GRAYSCALE)
            img2 = cv2.imdecode(np.frombuffer(img2_data, np.uint8), cv2.IMREAD_GRAYSCALE)

            if img1 is None or img2 is None:
                logger.error("Failed to decode one or both images for comparison")
                return False

            # Reset file pointers
            file1.seek(0)
            file2.seek(0)

            img1 = cv2.resize(img1, (300, 300))
            img2 = cv2.resize(img2, (300, 300))

            score, _ = ssim(img1, img2, full=True)
            
            if score <= 0.7:
                logger.warning(f"Images comparison failed. SSIM score: {score}")
                
            return score > 0.7

        except Exception as e:
            logger.error(f"Image comparison error: {str(e)}")
            return False

    @staticmethod
    def verify_faces(dropbox_id_photo, dropbox_selfie):
        """
        Verify if two face images belong to the same person using DeepFace.
        Returns True if faces match, False otherwise.
        """
        file1 = ImageProcessing.download_from_dropbox(dropbox_id_photo)
        file2 = ImageProcessing.download_from_dropbox(dropbox_selfie)

        if not file1 or not file2:
            logger.error("Failed to download one or both images for face verification")
            raise FileNotFoundError("One or both image files do not exist in Dropbox.")

        temp_files = []
        try:
            # Create temporary files with unique names
            temp_path1 = os.path.join("/tmp", f"id_photo_{os.urandom(8).hex()}.jpg")
            temp_path2 = os.path.join("/tmp", f"selfie_{os.urandom(8).hex()}.jpg")
            temp_files = [temp_path1, temp_path2]

            with open(temp_path1, "wb") as f1, open(temp_path2, "wb") as f2:
                f1.write(file1.read())
                f2.write(file2.read())

            result = DeepFace.verify(
                temp_path1, 
                temp_path2, 
                model_name="VGG-Face", 
                enforce_detection=False
            )
            
            is_verified = result.get('verified', False)
            if not is_verified:
                logger.warning("Face verification failed")
                
            return is_verified

        except Exception as e:
            logger.error(f"Face verification error: {str(e)}")
            return False
            
        finally:
            # Clean up temporary files
            for temp_file in temp_files:
                try:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                except Exception as e:
                    logger.warning(f"Failed to remove temporary file {temp_file}: {str(e)}")