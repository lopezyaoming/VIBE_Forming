import sys
import os
import json
import subprocess
import time
import threading
import random
import shutil
import io
from pathlib import Path
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QLabel, QLineEdit, QGraphicsOpacityEffect, 
    QGraphicsDropShadowEffect, QSizePolicy, QFrame, QDesktopWidget
)
from PyQt5.QtCore import Qt, QSize, QPropertyAnimation, QTimer, QUrl, pyqtSignal, QThread
from PyQt5.QtGui import QFont, QColor, QPalette, QImage, QPixmap, QCursor, QPainter, QBrush, QFontDatabase

# Project paths
BASE_DIR = r"C:\CODING\VIBE\VIBE_Forming"
OPTIONS_DIR = os.path.join(BASE_DIR, "input", "options")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
TEXTOPT_DIR = os.path.join(BASE_DIR, "input", "COMFYINPUTS", "textOptions")
INPUT_TEXT_FILE = os.path.join(BASE_DIR, "input", "input.txt")
OPTIONS_API_SCRIPT = os.path.join(BASE_DIR, "src", "comfyworkflows", "options_API.py")
MULTIVIEW_API_SCRIPT = os.path.join(BASE_DIR, "src", "comfyworkflows", "multiview_API.py")

# Ensure all necessary directories exist
for path in [OPTIONS_DIR, OUTPUT_DIR, TEXTOPT_DIR]:
    os.makedirs(path, exist_ok=True)

# Function to verify if a PNG file is valid
def is_valid_png(file_path):
    try:
        # Check if file exists and has content
        if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
            return False
            
        # Try to read the first 8 bytes to verify PNG signature
        with open(file_path, 'rb') as f:
            header = f.read(8)
            # Check for PNG signature (89 50 4E 47 0D 0A 1A 0A)
            return header == b'\x89\x50\x4E\x47\x0D\x0A\x1A\x0A'
    except Exception as e:
        print(f"Error checking PNG file {file_path}: {str(e)}")
        return False

# Worker thread for running scripts
class ScriptRunner(QThread):
    finished = pyqtSignal(bool, str)
    progress = pyqtSignal(str)
    
    def __init__(self, script_path, working_dir=None):
        super().__init__()
        self.script_path = script_path
        self.working_dir = working_dir or os.path.dirname(script_path)
        
    def run(self):
        try:
            self.progress.emit("Running script...")
            
            # Start the process
            process = subprocess.Popen(
                [sys.executable, self.script_path], 
                cwd=self.working_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Monitor output
            while process.poll() is None:
                stdout_line = process.stdout.readline()
                if stdout_line:
                    self.progress.emit(stdout_line.strip())
                
            # Get any remaining output
            stdout, stderr = process.communicate()
            if stdout:
                self.progress.emit(stdout.strip())
                
            if process.returncode == 0:
                self.finished.emit(True, "Script completed successfully")
            else:
                self.finished.emit(False, f"Script failed: {stderr}")
                
        except Exception as e:
            self.finished.emit(False, f"Error: {str(e)}")

# Custom button style
class MinimalButton(QPushButton):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setStyleSheet("""
            QPushButton {
                background-color: rgba(40, 40, 40, 180);
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: rgba(60, 60, 60, 200);
            }
            QPushButton:pressed {
                background-color: rgba(80, 80, 80, 220);
            }
        """)
        
        # Add drop shadow effect
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 150))
        shadow.setOffset(2, 2)
        self.setGraphicsEffect(shadow)

# Custom text input
class MinimalLineEdit(QLineEdit):
    def __init__(self, placeholder="", parent=None):
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        self.setStyleSheet("""
            QLineEdit {
                background-color: rgba(30, 30, 30, 150);
                color: white;
                border: none;
                border-radius: 4px;
                padding: 10px;
                font-size: 14px;
            }
            QLineEdit:focus {
                background-color: rgba(40, 40, 40, 180);
            }
        """)
        
        # Add drop shadow effect
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 150))
        shadow.setOffset(2, 2)
        self.setGraphicsEffect(shadow)

# Custom frame for displaying images
class ImageFrame(QFrame):
    doubleClicked = pyqtSignal(str)
    
    def __init__(self, option="", parent=None):
        super().__init__(parent)
        self.option = option
        self.image_path = ""
        self.pixmap = None
        
        # Set up frame appearance
        self.setFixedSize(240, 240)
        self.setStyleSheet("""
            QFrame {
                background-color: rgba(20, 20, 20, 150);
                border: none;
                border-radius: 10px;
            }
        """)
        
        # Create layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)
        
        # Create image label
        self.image_label = QLabel(self)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setScaledContents(True)
        self.image_label.setStyleSheet("background: transparent;")
        layout.addWidget(self.image_label)
        
        # Add option label
        self.option_label = QLabel(option, self)
        self.option_label.setAlignment(Qt.AlignCenter)
        self.option_label.setStyleSheet("""
            color: white;
            background: transparent;
            font-size: 16px;
            padding: 5px;
        """)
        layout.addWidget(self.option_label)
        
        # Add drop shadow effect
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 180))
        shadow.setOffset(3, 3)
        self.setGraphicsEffect(shadow)
        
    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.doubleClicked.emit(self.option)
        super().mouseDoubleClickEvent(event)
        
    def load_image(self, image_path):
        # First verify that the image path exists and is a valid PNG
        if not os.path.exists(image_path):
            print(f"Image path does not exist: {image_path}")
            return False
            
        # Verify PNG integrity
        if not is_valid_png(image_path):
            print(f"Invalid PNG file: {image_path}")
            return False
            
        try:
            self.image_path = image_path
            
            # Try to load the image with error handling
            for attempt in range(3):  # Try up to 3 times
                try:
                    self.pixmap = QPixmap(image_path)
                    if not self.pixmap.isNull():
                        self.image_label.setPixmap(self.pixmap.scaled(
                            220, 220, Qt.KeepAspectRatio, Qt.SmoothTransformation
                        ))
                        return True
                    else:
                        # If pixmap is null, wait a moment and try again
                        time.sleep(0.5)
                except Exception as e:
                    print(f"Error loading image (attempt {attempt+1}): {str(e)}")
                    time.sleep(0.5)  # Wait before retry
            
            # If we got here, all attempts failed
            return False
        except Exception as e:
            print(f"Critical error loading image {image_path}: {str(e)}")
            return False

# Main window class
class TransparentWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Set window flags for transparency and always on top
        self.setWindowFlags(
            Qt.FramelessWindowHint | 
            Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # Set up the UI
        self.init_ui()
        
        # Set up timer for periodic image refresh
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.load_images)
        self.refresh_timer.start(5000)  # Refresh every 5 seconds
        
        # Load initial images
        self.load_images()
        
        # Make fullscreen
        self.showFullScreen()
        
    def init_ui(self):
        # Window configuration
        self.setWindowTitle("VIBE UI Overlay")
        
        # Create central widget with transparent background
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        
        # Create main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(40, 40, 40, 40)
        main_layout.setSpacing(20)  # Reduced spacing
        main_layout.setAlignment(Qt.AlignCenter)
        
        # Create images container - vertical orientation
        images_container = QWidget()
        images_layout = QVBoxLayout(images_container)
        images_layout.setSpacing(30)  # Reduced vertical spacing
        images_layout.setAlignment(Qt.AlignCenter)
        
        # Create image frames
        self.image_frames = {}
        for option in ["A", "B", "C"]:
            frame = ImageFrame(option)
            frame.doubleClicked.connect(self.select_option)
            self.image_frames[option] = frame
            images_layout.addWidget(frame, alignment=Qt.AlignCenter)
        
        # Create a container widget to position images on the right
        right_container = QWidget()
        right_layout = QHBoxLayout(right_container)
        right_layout.addStretch(4)  # Increased to push content more to the right
        right_layout.addWidget(images_container)
        right_layout.setContentsMargins(0, 0, 20, 0)  # Add right margin to keep a bit of space from edge
        main_layout.addWidget(right_container)
        
        # Create prompt input area in the middle (after images but before stretcher)
        prompt_container = QWidget()
        prompt_layout = QHBoxLayout(prompt_container)
        prompt_layout.setContentsMargins(50, 10, 50, 10)
        
        self.prompt_input = MinimalLineEdit(placeholder="prompt:")
        self.prompt_input.setFixedWidth(500)
        # Connect Enter key press to submit
        self.prompt_input.returnPressed.connect(self.submit_prompt)
        prompt_layout.addWidget(self.prompt_input, alignment=Qt.AlignCenter)
        
        # Submit button
        self.submit_btn = MinimalButton("Generate")
        self.submit_btn.clicked.connect(self.submit_prompt)
        prompt_layout.addWidget(self.submit_btn)
        
        # Add prompt container with horizontal centering
        prompt_wrapper = QWidget()
        prompt_wrapper_layout = QHBoxLayout(prompt_wrapper)
        prompt_wrapper_layout.addStretch(1)
        prompt_wrapper_layout.addWidget(prompt_container)
        prompt_wrapper_layout.addStretch(1)
        main_layout.addWidget(prompt_wrapper)
        
        # Small space after prompt
        main_layout.addSpacing(20)  # Small spacing instead of large stretch
        
        # Status bar for showing messages
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("""
            color: rgba(200, 200, 200, 150);
            font-size: 12px;
        """)
        self.status_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.status_label)
        
        # Add a stretcher to push everything up from the bottom
        main_layout.addStretch(1)
        
        # Close button in top-right corner
        close_button = MinimalButton("×")
        close_button.setFixedSize(30, 30)
        close_button.clicked.connect(self.close)
        close_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(40, 40, 40, 180);
                color: white;
                border: none;
                border-radius: 15px;
                font-size: 20px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(255, 0, 0, 180);
            }
        """)
        
        # Position the close button in the top-right corner
        close_button.setParent(self)
        close_button.move(self.width() - 40, 10)
        
    def load_images(self):
        """Load or refresh the option images"""
        successful_loads = 0
        for option in ["A", "B", "C"]:
            try:
                image_path = os.path.join(OPTIONS_DIR, f"{option}.png")
                
                # First, verify the PNG file integrity
                if not is_valid_png(image_path):
                    print(f"Image {option}.png is not a valid PNG file")
                    self.status_label.setText(f"Image {option}.png is invalid or corrupted")
                    
                    # Try to find a backup or alternative file
                    alt_path = os.path.join(OPTIONS_DIR, f"{option}_backup.png")
                    if os.path.exists(alt_path) and is_valid_png(alt_path):
                        print(f"Using backup image for {option}")
                        image_path = alt_path
                    else:
                        continue  # Skip this image
                
                # Check file size and existence before loading
                if os.path.exists(image_path):
                    file_size = os.path.getsize(image_path)
                    if file_size == 0:
                        self.status_label.setText(f"Image {option}.png exists but is empty")
                        continue
                        
                    # Wait for file to be fully written
                    time.sleep(0.1)
                    
                    if self.image_frames[option].load_image(image_path):
                        successful_loads += 1
                    else:
                        self.status_label.setText(f"Failed to load image {option}.png")
                else:
                    print(f"Image not found: {image_path}")
            except Exception as e:
                self.status_label.setText(f"Error loading {option}.png: {str(e)}")
                
        if successful_loads > 0:
            self.status_label.setText(f"Loaded {successful_loads} images successfully")
            
    def select_option(self, option):
        """Handle option selection - double click"""
        try:
            # Save selection to output directory
            with open(os.path.join(OUTPUT_DIR, "selected_option.txt"), "w") as f:
                f.write(f"Selected Option: {option}\n")
                f.write(f"Timestamp: {time.time()}\n")
                
            # Copy text prompt
            source_file = os.path.join(TEXTOPT_DIR, f"{option}_0001.txt")
            target_file = os.path.join(TEXTOPT_DIR, "prompt.txt")
            
            if os.path.exists(source_file):
                shutil.copy2(source_file, target_file)
                self.status_label.setText(f"Selected option {option} and applied its prompt")
            else:
                self.status_label.setText(f"Selected option {option} but prompt file not found")
                
            # Create a highlight effect for the selected image
            for opt, frame in self.image_frames.items():
                if opt == option:
                    frame.setStyleSheet("""
                        QFrame {
                            background-color: rgba(40, 40, 40, 200);
                            border: 2px solid rgba(100, 200, 255, 200);
                            border-radius: 10px;
                        }
                    """)
                else:
                    frame.setStyleSheet("""
                        QFrame {
                            background-color: rgba(20, 20, 20, 150);
                            border: none;
                            border-radius: 10px;
                        }
                    """)
                    
            # Run the multiview_API script to generate and import the mesh
            self.status_label.setText(f"Selected option {option}. Running multiview workflow...")
            
            # Create worker thread for multiview API
            self.multiview_worker = ScriptRunner(MULTIVIEW_API_SCRIPT)
            self.multiview_worker.progress.connect(self.update_status)
            self.multiview_worker.finished.connect(self.handle_multiview_completion)
            self.multiview_worker.start()
                    
        except Exception as e:
            self.status_label.setText(f"Error selecting option: {str(e)}")
            
    def submit_prompt(self):
        """Submit a new prompt and generate images"""
        prompt = self.prompt_input.text().strip()
        if not prompt:
            self.status_label.setText("Please enter a prompt first")
            return
            
        try:
            # Write prompt to input.txt
            with open(INPUT_TEXT_FILE, "w", encoding="utf-8") as f:
                f.write(prompt)
                
            # Change the status and button
            self.status_label.setText("Generating images...")
            self.submit_btn.setEnabled(False)
            self.submit_btn.setText("Processing...")
            
            # Create worker thread
            self.worker = ScriptRunner(OPTIONS_API_SCRIPT)
            self.worker.progress.connect(self.update_status)
            self.worker.finished.connect(self.handle_completion)
            self.worker.start()
            
        except Exception as e:
            self.status_label.setText(f"Error: {str(e)}")
            self.submit_btn.setEnabled(True)
            self.submit_btn.setText("Generate")
            
    def update_status(self, message):
        """Update status with script progress"""
        self.status_label.setText(message)
        
    def handle_completion(self, success, message):
        """Handle script completion"""
        if success:
            self.status_label.setText("Generation complete! Loading new images...")
            self.load_images()
        else:
            self.status_label.setText(f"Error: {message}")
            
        self.submit_btn.setEnabled(True)
        self.submit_btn.setText("Generate")
        
    def handle_multiview_completion(self, success, message):
        """Handle multiview script completion"""
        if success:
            self.status_label.setText("3D model generation complete! Model imported.")
        else:
            self.status_label.setText(f"Error generating 3D model: {message}")
            
    def mousePressEvent(self, event):
        """Enable window dragging"""
        if event.button() == Qt.LeftButton:
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()
            
    def mouseMoveEvent(self, event):
        """Handle window dragging"""
        if event.buttons() == Qt.LeftButton:
            self.move(event.globalPos() - self.drag_position)
            event.accept()
            
    def resizeEvent(self, event):
        """Reposition close button when window is resized"""
        close_buttons = [child for child in self.children() if isinstance(child, MinimalButton) and child.text() == "×"]
        if close_buttons:
            close_buttons[0].move(self.width() - 40, 10)
        super().resizeEvent(event)
        
    def keyPressEvent(self, event):
        """Handle key press events"""
        # Exit fullscreen with Escape key
        if event.key() == Qt.Key_Escape:
            self.close()
        super().keyPressEvent(event)

# Run the application
if __name__ == "__main__":
    # Set application attributes
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    
    app = QApplication(sys.argv)
    
    # Use a system font instead of requiring Roboto
    font = QFont("Segoe UI" if sys.platform == "win32" else "Helvetica")
    font.setPointSize(10)
    app.setFont(font)
    
    window = TransparentWindow()
    window.show()
    
    sys.exit(app.exec_()) 