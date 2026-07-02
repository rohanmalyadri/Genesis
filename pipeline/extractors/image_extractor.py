import pytesseract
from PIL import Image, ImageOps, ImageFilter
import cv2
import numpy as np

class ImageExtractor:
    def extract(self, file_path: str) -> str:
        # 1. Load image
        img = cv2.imread(file_path)
        
        # 2. Preprocessing
        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Thresholding to remove noise and make text pop
        # Use Otsu's thresholding
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # 3. OCR
        # Use PIL for Tesseract
        pil_img = Image.fromarray(thresh)
        text = pytesseract.image_to_string(pil_img, lang='eng', config='--psm 6')
        
        return text.strip()

image_extractor = ImageExtractor()
