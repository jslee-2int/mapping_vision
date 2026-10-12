"""
YOLO Detection Class for Dot Detection
"""
import cv2
import numpy as np
from typing import List, Tuple, Optional
import os


class YOLODetector:
    """
    YOLO-based dot detection class
    """
    
    def __init__(self, model_path: str = None, confidence_threshold: float = 0.5):
        """
        Initialize YOLO detector
        
        Args:
            model_path: Path to YOLO model file (.pt)
            confidence_threshold: Minimum confidence for detection
        """
        self.model_path = model_path
        self.confidence_threshold = confidence_threshold
        self.model = None
        self.is_initialized = False
        
        # Try to initialize YOLO model
        self._initialize_model()
    
    def _initialize_model(self):
        """
        Initialize YOLO model
        """
        try:
            # Try to import ultralytics
            from ultralytics import YOLO
            
            if self.model_path and os.path.exists(self.model_path):
                self.model = YOLO(self.model_path)
            else:
                # Use default YOLOv8 nano model
                self.model = YOLO('yolov8n.pt')
            
            self.is_initialized = True
            print("✅ YOLO model initialized successfully")
            
        except ImportError:
            print("❌ ultralytics not installed. Please install: pip install ultralytics")
            self.is_initialized = False
        except Exception as e:
            print(f"❌ Failed to initialize YOLO model: {e}")
            self.is_initialized = False
    
    def detect_dots(self, image: np.ndarray) -> List[Tuple[int, int]]:
        """
        Detect dots in image using YOLO
        
        Args:
            image: Input image as numpy array
            
        Returns:
            List of (x, y) coordinates of detected dots
        """
        if not self.is_initialized:
            print("❌ YOLO model not initialized")
            return []
        
        try:
            # Run YOLO detection
            results = self.model(image, conf=self.confidence_threshold)
            
            points = []
            for result in results:
                if result.boxes is not None:
                    for box in result.boxes:
                        # Get bounding box coordinates
                        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                        # Calculate center point
                        center_x = int((x1 + x2) / 2)
                        center_y = int((y1 + y2) / 2)
                        points.append((center_x, center_y))
            
            return points
            
        except Exception as e:
            print(f"❌ Error in YOLO detection: {e}")
            return []
    
    def detect_with_visualization(self, image: np.ndarray) -> Tuple[List[Tuple[int, int]], np.ndarray]:
        """
        Detect dots and return visualization
        
        Args:
            image: Input image as numpy array
            
        Returns:
            Tuple of (points, visualized_image)
        """
        points = self.detect_dots(image)
        
        # Create visualization
        vis_image = image.copy()
        for (x, y) in points:
            # Draw magenta cross marker
            cv2.line(vis_image, (x - 10, y), (x + 10, y), (255, 0, 255), 2)
            cv2.line(vis_image, (x, y - 10), (x, y + 10), (255, 0, 255), 2)
        
        return points, vis_image
    
    def is_available(self) -> bool:
        """
        Check if YOLO is available and initialized
        
        Returns:
            True if YOLO is available and initialized
        """
        return self.is_initialized
    
    def set_confidence_threshold(self, threshold: float):
        """
        Set confidence threshold for detection
        
        Args:
            threshold: Confidence threshold (0.0 to 1.0)
        """
        self.confidence_threshold = max(0.0, min(1.0, threshold))
    
    def get_model_info(self) -> dict:
        """
        Get model information
        
        Returns:
            Dictionary with model information
        """
        if not self.is_initialized:
            return {"status": "not_initialized"}
        
        return {
            "status": "initialized",
            "model_path": self.model_path,
            "confidence_threshold": self.confidence_threshold,
            "model_type": "YOLO"
        }
