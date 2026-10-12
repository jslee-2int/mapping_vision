"""
Simple YOLO Detection Test - Minimal Version
"""
import cv2
import os
from pathlib import Path

def simple_detection_test():
    """Simple detection test"""
    print("=== Simple YOLO Detection Test ===")
    
    # Check ultralytics
    try:
        from ultralytics import YOLO
        print("✅ ultralytics available")
    except ImportError:
        print("❌ Install ultralytics: pip install ultralytics")
        return
    
    # Paths
    model_path = "models/dot_detection.pt"
    image_path = r"C:\Pycode\camera_test\imgs\25-10-14_23.png"
    
    # Check files
    if not os.path.exists(model_path):
        print(f"❌ Model not found: {model_path}")
        return
    
    if not os.path.exists(image_path):
        print(f"❌ Image not found: {image_path}")
        return
    
    print(f"✅ Model: {model_path}")
    print(f"✅ Image: {Path(image_path).name}")
    
    try:
        # Load model
        model = YOLO(model_path)
        print("✅ Model loaded")
        
        # Load image
        image = cv2.imread(image_path)
        print(f"✅ Image loaded: {image.shape}")
        
        # Detect
        results = model(image, conf=0.5)
        
        # Count detections
        total_dots = 0
        for result in results:
            if result.boxes is not None:
                total_dots += len(result.boxes)
        
        print(f"✅ Detected {total_dots} dots")
        
        # Create visualization
        vis_image = image.copy()
        for result in results:
            if result.boxes is not None:
                for box in result.boxes:
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                    center_x = int((x1 + x2) / 2)
                    center_y = int((y1 + y2) / 2)
                    
                    # Draw cross
                    cv2.line(vis_image, (center_x - 10, center_y), (center_x + 10, center_y), (255, 0, 255), 2)
                    cv2.line(vis_image, (center_x, center_y - 10), (center_x, center_y + 10), (255, 0, 255), 2)
        
        # Show result in window
        print("Showing detection result in window...")
        print("Press any key to close the window")
        
        # Resize image if too large for display
        display_image = vis_image.copy()
        height, width = display_image.shape[:2]
        if width > 1200 or height > 800:
            scale = min(1200/width, 800/height)
            new_width = int(width * scale)
            new_height = int(height * scale)
            display_image = cv2.resize(display_image, (new_width, new_height))
            print(f"Resized for display: {new_width}x{new_height}")
        
        # Show image
        cv2.imshow("YOLO Dot Detection Result", display_image)
        cv2.waitKey(0)  # Wait for any key press
        cv2.destroyAllWindows()  # Close all windows
        
        # Save result
        cv2.imwrite("simple_detection_result.png", vis_image)
        print("✅ Result saved: simple_detection_result.png")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    simple_detection_test()
