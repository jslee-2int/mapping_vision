"""
실시간 추론을 위한 Inference 코드
학습된 Autoencoder 모델을 사용하여 새로운 점들을 분류
"""

import os
import torch
import numpy as np
import cv2
from PIL import Image
from torchvision import transforms

from autoencoder_model import create_model


class DotFilterPredictor:
    """
    학습된 Autoencoder를 사용한 점 필터링 예측기
    """
    
    def __init__(self, 
                 checkpoint_path,
                 threshold=None,
                 model_type='improved',
                 patch_size=32,
                 latent_dim=128,
                 device=None):
        """
        Args:
            checkpoint_path: 학습된 모델 체크포인트 경로
            threshold: reconstruction error threshold (None이면 checkpoint에서 로드 시도)
            model_type: 모델 타입 ('basic' or 'improved')
            patch_size: 패치 크기
            latent_dim: latent dimension
            device: 디바이스 (None이면 자동 선택)
        """
        if device is None:
            self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        else:
            self.device = torch.device(device)
        
        self.patch_size = patch_size
        self.model_type = model_type
        
        # Create and load model
        self.model = create_model(
            model_type=model_type,
            patch_size=patch_size,
            latent_dim=latent_dim
        ).to(self.device)
        
        self.load_checkpoint(checkpoint_path)
        self.model.eval()
        
        # Set threshold
        if threshold is None:
            # Try to load from test_results
            threshold_file = os.path.join(
                os.path.dirname(checkpoint_path), 
                '../test_results/threshold.txt'
            )
            if os.path.exists(threshold_file):
                with open(threshold_file, 'r') as f:
                    self.threshold = float(f.read().strip())
                print(f"Loaded threshold from file: {self.threshold:.6f}")
            else:
                print("Warning: No threshold provided or found. Using default 0.01")
                self.threshold = 0.01
        else:
            self.threshold = threshold
        
        # Setup transform
        self.transform = transforms.Compose([
            transforms.ToPILImage(),
            transforms.ToTensor(),
        ])
        
        print(f"Predictor initialized on {self.device}")
        print(f"Model type: {model_type}")
        print(f"Threshold: {self.threshold:.6f}")
    
    def load_checkpoint(self, checkpoint_path):
        """체크포인트 로드"""
        if not os.path.exists(checkpoint_path):
            raise FileNotFoundError(f"Checkpoint not found: {checkpoint_path}")
        
        checkpoint = torch.load(checkpoint_path, map_location=self.device)
        self.model.load_state_dict(checkpoint['model_state_dict'])
        print(f"Loaded checkpoint from epoch {checkpoint.get('epoch', 'unknown')}")
    
    def extract_patch(self, image, x, y):
        """
        이미지에서 점 주변의 패치 추출
        
        Args:
            image: 그레이스케일 이미지 (numpy array)
            x, y: 점의 좌표
        
        Returns:
            patch: (1, 1, patch_size, patch_size) 텐서
        """
        half_patch = self.patch_size // 2
        
        # Check bounds
        if (x - half_patch < 0 or x + half_patch > image.shape[1] or
            y - half_patch < 0 or y + half_patch > image.shape[0]):
            # Pad image if needed
            pad_top = max(0, half_patch - y)
            pad_bottom = max(0, (y + half_patch) - image.shape[0])
            pad_left = max(0, half_patch - x)
            pad_right = max(0, (x + half_patch) - image.shape[1])
            
            image = cv2.copyMakeBorder(
                image,
                pad_top, pad_bottom, pad_left, pad_right,
                cv2.BORDER_REPLICATE
            )
            
            # Adjust coordinates
            x += pad_left
            y += pad_top
        
        # Extract patch
        patch = image[y - half_patch:y + half_patch,
                     x - half_patch:x + half_patch]
        
        # Ensure correct size
        if patch.shape != (self.patch_size, self.patch_size):
            patch = cv2.resize(patch, (self.patch_size, self.patch_size))
        
        # Normalize
        patch = patch.astype(np.float32) / 255.0
        
        # Transform
        patch = self.transform(patch)
        patch = patch.unsqueeze(0)  # Add batch dimension
        
        return patch
    
    def predict_single(self, image, x, y):
        """
        단일 점 예측
        
        Args:
            image: 그레이스케일 이미지 (numpy array)
            x, y: 점의 좌표
        
        Returns:
            prediction: 0 (invalid) or 1 (valid)
            error: reconstruction error
            confidence: 신뢰도 (0-1)
        """
        patch = self.extract_patch(image, x, y).to(self.device)
        
        with torch.no_grad():
            reconstruction, _ = self.model(patch)
            error = torch.mean((reconstruction - patch) ** 2).item()
        
        prediction = 1 if error < self.threshold else 0
        
        # Calculate confidence based on distance from threshold
        if prediction == 1:
            # Valid: lower error = higher confidence
            confidence = 1.0 - (error / self.threshold) if error < self.threshold else 0.0
        else:
            # Invalid: higher error = higher confidence
            confidence = min(1.0, (error - self.threshold) / self.threshold)
        
        confidence = max(0.0, min(1.0, confidence))  # Clamp to [0, 1]
        
        return prediction, error, confidence
    
    def predict_batch(self, image, points):
        """
        여러 점을 배치로 예측
        
        Args:
            image: 그레이스케일 이미지 (numpy array)
            points: 점들의 리스트 [(x1, y1), (x2, y2), ...]
        
        Returns:
            predictions: [0 or 1, ...]
            errors: [error1, error2, ...]
            confidences: [conf1, conf2, ...]
        """
        if len(points) == 0:
            return [], [], []
        
        # Extract all patches
        patches = []
        valid_indices = []
        
        for i, (x, y) in enumerate(points):
            try:
                patch = self.extract_patch(image, x, y)
                patches.append(patch)
                valid_indices.append(i)
            except Exception as e:
                print(f"Warning: Failed to extract patch at ({x}, {y}): {e}")
        
        if len(patches) == 0:
            return [0] * len(points), [float('inf')] * len(points), [0.0] * len(points)
        
        # Batch inference
        batch = torch.cat(patches, dim=0).to(self.device)
        
        with torch.no_grad():
            reconstruction, _ = self.model(batch)
            errors = torch.mean((reconstruction - batch) ** 2, dim=[1, 2, 3])
            errors = errors.cpu().numpy()
        
        # Make predictions
        predictions_array = (errors < self.threshold).astype(int)
        
        # Calculate confidences
        confidences_array = np.zeros_like(errors)
        for i, (pred, error) in enumerate(zip(predictions_array, errors)):
            if pred == 1:
                confidences_array[i] = 1.0 - (error / self.threshold) if error < self.threshold else 0.0
            else:
                confidences_array[i] = min(1.0, (error - self.threshold) / self.threshold)
        confidences_array = np.clip(confidences_array, 0.0, 1.0)
        
        # Fill results (including failed patches)
        predictions = [0] * len(points)
        all_errors = [float('inf')] * len(points)
        all_confidences = [0.0] * len(points)
        
        for i, valid_idx in enumerate(valid_indices):
            predictions[valid_idx] = int(predictions_array[i])
            all_errors[valid_idx] = float(errors[i])
            all_confidences[valid_idx] = float(confidences_array[i])
        
        return predictions, all_errors, all_confidences
    
    def filter_points(self, image, points, return_details=False):
        """
        점들을 필터링하여 valid 점만 반환
        
        Args:
            image: 그레이스케일 이미지 (numpy array)
            points: 점들의 리스트 [(x1, y1), (x2, y2), ...]
            return_details: True면 상세 정보도 반환
        
        Returns:
            valid_points: valid로 판정된 점들
            (optional) details: 각 점의 상세 정보
        """
        predictions, errors, confidences = self.predict_batch(image, points)
        
        valid_points = [point for point, pred in zip(points, predictions) if pred == 1]
        
        if return_details:
            details = []
            for point, pred, error, conf in zip(points, predictions, errors, confidences):
                details.append({
                    'point': point,
                    'prediction': pred,
                    'error': error,
                    'confidence': conf,
                    'status': 'valid' if pred == 1 else 'invalid'
                })
            return valid_points, details
        else:
            return valid_points
    
    def set_threshold(self, threshold):
        """Threshold 변경"""
        self.threshold = threshold
        print(f"Threshold updated to: {threshold:.6f}")


def demo():
    """간단한 데모"""
    import sys
    
    # Configuration
    checkpoint_path = './checkpoints/best_model.pth'
    image_path = r'C:\Pycode\camera_test\imgs\25-10-14_1.png'
    
    if not os.path.exists(checkpoint_path):
        print("Error: Please train the model first!")
        print("Run: python train.py")
        return
    
    if not os.path.exists(image_path):
        print(f"Error: Image not found at {image_path}")
        return
    
    # Load image
    image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if image is None:
        print(f"Error: Failed to load image")
        return
    
    # Example points
    points = [
        (620, 234),   # Should be valid
        (467, 239),   # Should be valid
        (503, 68),    # Should be invalid
        (769, 77),    # Should be invalid
    ]
    
    # Create predictor
    print("Initializing predictor...")
    predictor = DotFilterPredictor(
        checkpoint_path=checkpoint_path,
        model_type='improved',
        patch_size=32,
        latent_dim=128
    )
    
    # Predict
    print("\nPredicting...")
    valid_points, details = predictor.filter_points(image, points, return_details=True)
    
    print("\nResults:")
    print("-" * 60)
    for detail in details:
        x, y = detail['point']
        print(f"Point ({x}, {y}):")
        print(f"  Prediction: {detail['status']}")
        print(f"  Error: {detail['error']:.6f}")
        print(f"  Confidence: {detail['confidence']:.2%}")
        print()
    
    print(f"Valid points: {len(valid_points)}/{len(points)}")
    print(f"Valid point coordinates: {valid_points}")


if __name__ == "__main__":
    demo()

