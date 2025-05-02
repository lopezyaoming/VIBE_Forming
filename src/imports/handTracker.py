import cv2
import time
import json
import os
import mediapipe as mp
from pathlib import Path

# Determine project root (two levels up from this file) and write output there
BASE_DIR = Path(__file__).resolve().parents[2]
OUTPUT_JSON = str(BASE_DIR / "output" / "live_hand_data.json")

# Window name and size
WINDOW_NAME = "HandTracker"

# Initialize MediaPipe Hands
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=2,
    min_detection_confidence=0.3,
    min_tracking_confidence=0.5
)
# Debug: report detection thresholds
print("MediaPipe Hands initialized with detection_confidence=0.3, tracking_confidence=0.5")
mp_drawing = mp.solutions.drawing_utils
mp_drawing_styles = mp.solutions.drawing_styles

# Utility: extract normalized fingertip coordinates
def get_fingertips(hand_landmarks):
    indices = [4, 8, 12, 16, 20]
    return [{"x": lm.x, "y": lm.y, "z": lm.z}
            for i, lm in enumerate(hand_landmarks.landmark) if i in indices]


def main():
    # Open webcam
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Cannot open camera")
        return
    # Ensure output directory exists
    os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)

    # Create a window for exit key and debug display
    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WINDOW_NAME, 640, 480)

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Frame capture failed, stopping.")
            break
        # Debug: log frame size
        print(f"Frame size: {frame.shape}")

        # Keep original frame for detection, flip only for display
        display_frame = cv2.flip(frame, 1)

        # Process frame with MediaPipe on the flipped display for aligned detection
        rgb = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
        results = hands.process(rgb)
        # Debug: print number of hands detected
        num = len(results.multi_hand_landmarks) if results.multi_hand_landmarks else 0
        print(f"Detected {num} hand(s)")

        # Draw landmarks on the mirrored display for visual feedback
        if results.multi_hand_landmarks:
            for landmarks in results.multi_hand_landmarks:
                mp_drawing.draw_landmarks(
                    display_frame,
                    landmarks,
                    mp_hands.HAND_CONNECTIONS,
                    mp_drawing_styles.get_default_hand_landmarks_style(),
                    mp_drawing_styles.get_default_hand_connections_style()
                )

        # Initialize empty fingertip lists
        left_fingertips = []
        right_fingertips = []

        if results.multi_hand_landmarks and results.multi_handedness:
            for landmarks, handedness in zip(results.multi_hand_landmarks, results.multi_handedness):
                label = handedness.classification[0].label  # 'Left' or 'Right'
                tips = get_fingertips(landmarks)
                if label == 'Left':
                    left_fingertips = tips
                    print(f"Left hand detected with {len(tips)} fingertips")
                elif label == 'Right':
                    right_fingertips = tips
                    print(f"Right hand detected with {len(tips)} fingertips")

        # Build JSON payload
        data = {
            "left_hand": {"fingertips": left_fingertips},
            "right_hand": {"fingertips": right_fingertips}
        }

        # Debug: log JSON data to be written
        print(f"Writing JSON data: {data}")
        # Write atomically
        tmp = OUTPUT_JSON + ".tmp"
        with open(tmp, 'w') as f:
            json.dump(data, f)
        # Atomic replace with fallback for Windows file locks
        try:
            os.replace(tmp, OUTPUT_JSON)
        except PermissionError:
            # If replace fails (file locked), delete target and rename
            try:
                os.remove(OUTPUT_JSON)
            except OSError:
                pass
            os.rename(tmp, OUTPUT_JSON)
        except Exception as e:
            print(f"Error writing JSON: {e}")

        # Show minimal window (mirrored view)
        cv2.imshow(WINDOW_NAME, display_frame)
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q') or key == 27:
            break

    # Cleanup
    cap.release()
    cv2.destroyAllWindows()
    hands.close()

if __name__ == '__main__':
    main()
