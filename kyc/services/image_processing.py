import cv2
import numpy as np
import pytesseract
from PIL import Image
from deepface import DeepFace


class ImageProcessing:

    @staticmethod
    def extract_text(image_path):
        img = Image.open(image_path)
        return pytesseract.image_to_string(img)

    @staticmethod
    def check_image_integrity(image_path):
        image = cv2.imread(image_path)
        gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray_image, 100, 200)
        edge_count = np.sum(edges > 0)
        return edge_count > 500  # Threshold for integrity; adjust as needed.

    @staticmethod
    def compare_images(id_image_path, selfie_image_path):
        id_image = Image.open(id_image_path).resize((300, 300))
        selfie_image = Image.open(selfie_image_path).resize((300, 300))
        difference = np.abs(np.array(id_image) - np.array(selfie_image))
        diff_sum = np.sum(difference)
        return diff_sum < 1000000  # Threshold for similarity; adjust as needed.

    @staticmethod
    def verify_faces(id_photo, selfie):
        return DeepFace.verify(id_photo, selfie)['verified']
