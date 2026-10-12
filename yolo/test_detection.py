"""
Simple YOLO Detection Test
Load trained model and detect dots in a single image
"""
import cv2
import numpy as np
from pathlib import Path
import os


def test_yolo_detection():
    """
    Test YOLO detection on a single image
    """
    print("=== YOLO Dot Detection Test ===")
    
    # Check if ultralytics is available
    try:
        from ultralytics import YOLO
        print("✅ ultralytics imported successfully")
    except ImportError:
        print("❌ ultralytics not installed. Please install: pip install ultralytics")
        return False
    
    # Paths
    model_path = "yolo/models/dot_detection.pt"
    image_path = r"C:\Pycode\camera_test\imgs\25-10-14_34.png"
    
    # Check if model exists
    if not Path(model_path).exists():
        print(f"❌ Model not found: {model_path}")
        print("Please train the model first using train_yolo.py")
        return False
    
    # Check if image exists
    if not Path(image_path).exists():
        print(f"❌ Image not found: {image_path}")
        return False
    
    print(f"Loading model: {model_path}")
    print(f"Loading image: {image_path}")
    
    try:
        # Load YOLO model
        model = YOLO(model_path)
        print("✅ Model loaded successfully")
        
        # Load and display image info
        image = cv2.imread(image_path)
        if image is None:
            print("❌ Failed to load image")
            return False
        
        height, width = image.shape[:2]
        print(f"Image size: {width}x{height}")
        
        # Run detection
        print("Running detection...")
        results = model(image, conf=0.5)  # confidence threshold 0.5
        
        # Process results
        detected_points = []
        for result in results:
            if result.boxes is not None:
                for box in result.boxes:
                    # Get bounding box coordinates
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                    confidence = box.conf[0].cpu().numpy()
                    
                    # Calculate center point
                    center_x = int((x1 + x2) / 2)
                    center_y = int((y1 + y2) / 2)
                    
                    detected_points.append((center_x, center_y, confidence))
        
        print(f"✅ Detection completed!")
        print(f"Detected {len(detected_points)} dots")
        
        # Display results
        if detected_points:
            print("\nDetected points:")
            for i, (x, y, conf) in enumerate(detected_points):
                print(f"  Point {i+1}: ({x}, {y}) - confidence: {conf:.3f}")
        else:
            print("No dots detected")
        
        # Create visualization
        vis_image = image.copy()
        for (x, y, conf) in detected_points:
            # Draw magenta cross marker
            cv2.line(vis_image, (x - 10, y), (x + 10, y), (255, 0, 255), 2)
            cv2.line(vis_image, (x, y - 10), (x, y + 10), (255, 0, 255), 2)
            
            # Draw confidence text
            cv2.putText(vis_image, f"{conf:.2f}", (x + 15, y - 10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 255), 1)
        
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
        output_path = "detection_result.png"
        cv2.imwrite(output_path, vis_image)
        print(f"✅ Result saved as: {output_path}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during detection: {e}")
        return False


def test_with_different_confidence():
    """
    Test detection with different confidence thresholds
    """
    print("\n=== Testing with Different Confidence Thresholds ===")
    
    try:
        from ultralytics import YOLO
        
        model_path = "models/dot_detection.pt"
        image_path = r"C:\Pycode\camera_test\imgs\25-10-14_23.png"
        
        if not Path(model_path).exists() or not Path(image_path).exists():
            print("❌ Model or image not found")
            return
        
        model = YOLO(model_path)
        image = cv2.imread(image_path)
        
        confidence_thresholds = [0.1, 0.3, 0.5, 0.7, 0.9]
        
        for conf_thresh in confidence_thresholds:
            results = model(image, conf=conf_thresh)
            
            total_detections = 0
            for result in results:
                if result.boxes is not None:
                    total_detections += len(result.boxes)
            
            print(f"Confidence {conf_thresh}: {total_detections} detections")
        
    except Exception as e:
        print(f"❌ Error in confidence testing: {e}")


def main():
    """Main test function"""
    print("YOLO Dot Detection Test")
    print("=" * 40)
    
    # Test basic detection
    success = test_yolo_detection()
    
    if success:
        # Test with different confidence levels
        test_with_different_confidence()
        print("\n🎉 Detection test completed successfully!")
    else:
        print("\n❌ Detection test failed")


if __name__ == "__main__":
    main()
