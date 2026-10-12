"""
YOLO Detection Test Script
"""
import cv2
import numpy as np
import os
import sys

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from yolo_detector import YOLODetector


def test_yolo_initialization():
    """Test YOLO initialization"""
    print("=== Testing YOLO Initialization ===")
    
    detector = YOLODetector()
    
    if detector.is_available():
        print("✅ YOLO detector initialized successfully")
        print(f"Model info: {detector.get_model_info()}")
        return True
    else:
        print("❌ YOLO detector failed to initialize")
        return False


def test_detection_with_sample_image():
    """Test detection with sample image"""
    print("\n=== Testing Detection with Sample Image ===")
    
    detector = YOLODetector()
    
    if not detector.is_available():
        print("❌ YOLO not available, skipping detection test")
        return False
    
    # Create a sample image (white background with some colored circles)
    sample_image = np.ones((480, 640, 3), dtype=np.uint8) * 255
    
    # Draw some circles to simulate dots
    cv2.circle(sample_image, (100, 100), 10, (0, 0, 0), -1)
    cv2.circle(sample_image, (200, 150), 8, (0, 0, 0), -1)
    cv2.circle(sample_image, (300, 200), 12, (0, 0, 0), -1)
    
    print("Sample image created with 3 circles")
    
    # Test detection
    points = detector.detect_dots(sample_image)
    print(f"Detected {len(points)} points: {points}")
    
    # Test with visualization
    points_vis, vis_image = detector.detect_with_visualization(sample_image)
    print(f"Visualization test - detected {len(points_vis)} points")
    
    # Save result image
    cv2.imwrite('yolo_test_result.png', vis_image)
    print("✅ Test result saved as 'yolo_test_result.png'")
    
    return True


def test_confidence_threshold():
    """Test confidence threshold adjustment"""
    print("\n=== Testing Confidence Threshold ===")
    
    detector = YOLODetector()
    
    if not detector.is_available():
        print("❌ YOLO not available, skipping threshold test")
        return False
    
    # Test different confidence thresholds
    thresholds = [0.1, 0.3, 0.5, 0.7, 0.9]
    
    for threshold in thresholds:
        detector.set_confidence_threshold(threshold)
        print(f"Confidence threshold set to: {threshold}")
    
    print("✅ Confidence threshold test completed")
    return True


def main():
    """Main test function"""
    print("YOLO Detection Test")
    print("=" * 50)
    
    # Test 1: Initialization
    init_success = test_yolo_initialization()
    
    if not init_success:
        print("\n❌ YOLO initialization failed. Please install ultralytics:")
        print("pip install ultralytics")
        return
    
    # Test 2: Detection with sample image
    detection_success = test_detection_with_sample_image()
    
    # Test 3: Confidence threshold
    threshold_success = test_confidence_threshold()
    
    print("\n" + "=" * 50)
    print("Test Summary:")
    print(f"Initialization: {'✅ PASS' if init_success else '❌ FAIL'}")
    print(f"Detection: {'✅ PASS' if detection_success else '❌ FAIL'}")
    print(f"Threshold: {'✅ PASS' if threshold_success else '❌ FAIL'}")
    
    if all([init_success, detection_success, threshold_success]):
        print("\n🎉 All tests passed! YOLO is ready to use.")
    else:
        print("\n⚠️  Some tests failed. Check the output above.")


if __name__ == "__main__":
    main()
