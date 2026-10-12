"""
Autoencoder 기반 Dot Filtering System

이 패키지는 Autoencoder를 사용하여 카메라 이미지에서 
valid/invalid 점을 자동으로 분류하는 시스템을 제공합니다.

주요 모듈:
- autoencoder_model: Autoencoder 모델 정의
- dataset: 데이터셋 로더
- train: 학습 코드
- test: 테스트 및 평가 코드
- inference: 실시간 추론
- visualize: 시각화 유틸리티

빠른 시작:
1. 학습: python run_training.py
2. 테스트: python run_testing.py
3. 추론: python run_inference_demo.py

자세한 내용은 README.md를 참고하세요.
"""

__version__ = "1.0.0"
__author__ = "Camera Test Project Team"

from .autoencoder_model import DotAutoencoder, ImprovedDotAutoencoder, create_model
from .dataset import DotPatchDataset, DotPatchTestDataset, create_dataloader, create_test_dataloader
from .inference import DotFilterPredictor

__all__ = [
    'DotAutoencoder',
    'ImprovedDotAutoencoder',
    'create_model',
    'DotPatchDataset',
    'DotPatchTestDataset',
    'create_dataloader',
    'create_test_dataloader',
    'DotFilterPredictor',
]

