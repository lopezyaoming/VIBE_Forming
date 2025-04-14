import os
import cv2
import logging
from pathlib import Path
import numpy as np

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

# Define the directory path
DIRECTORY = r"C:\CODING\VIBE\VIBE_Forming\input\COMFYINPUTS\textOptions"

def copy_text_file(source_file: str, target_file: str) -> None:
    """Copy the contents of source file to target file"""
    try:
        source_path = os.path.join(DIRECTORY, source_file)
        target_path = os.path.join(DIRECTORY, target_file)
        
        if not os.path.exists(source_path):
            logging.error(f"Source file not found: {source_path}")
            return
            
        with open(source_path, 'r', encoding='utf-8') as source:
            content = source.read()
            
        with open(target_path, 'w', encoding='utf-8') as target:
            target.write(content)
            
        logging.info(f"Successfully copied {source_file} to {target_file}")
    except Exception as e:
        logging.error(f"Error copying file: {e}")

def main():
    # Create a small window for key detection
    cv2.namedWindow('Text Selector', cv2.WINDOW_NORMAL)
    cv2.resizeWindow('Text Selector', 300, 100)
    
    logging.info("Text selector started. Press A, B, or C to select a text file. Press Q to quit.")
    
    while True:
        # Create a black image for the window
        img = np.zeros((100, 300, 3), dtype=np.uint8)
        cv2.putText(img, "Press A/B/C to select, Q to quit", (10, 30), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        cv2.imshow('Text Selector', img)
        
        # Wait for key press
        key = cv2.waitKey(1) & 0xFF
        
        if key == ord('a'):
            copy_text_file('A_0001.txt', 'prompt.txt')
        elif key == ord('b'):
            copy_text_file('B_0001.txt', 'prompt.txt')
        elif key == ord('c'):
            copy_text_file('C_0001.txt', 'prompt.txt')
        elif key == ord('q'):
            logging.info("Quitting text selector...")
            break
    
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main() 