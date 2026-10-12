# Autoencoder 기반 Dot Filtering System

이 시스템은 Autoencoder를 사용하여 카메라 이미지에서 유효한(valid) 점과 무효한(invalid) 점을 자동으로 분류합니다.

## 개요

### 동작 원리

1. **Anomaly Detection 방식**: Valid 점들로만 Autoencoder를 학습
2. **Reconstruction Error**: Valid 점은 낮은 reconstruction error를, Invalid 점은 높은 reconstruction error를 생성
3. **Threshold 기반 분류**: Reconstruction error가 threshold보다 작으면 valid, 크면 invalid로 분류

### 구조

```
autoencoder/
├── autoencoder_model.py    # Autoencoder 모델 정의
├── dataset.py               # 데이터셋 로더
├── train.py                 # 학습 코드
├── test.py                  # 테스트 및 평가 코드
├── inference.py             # 실시간 추론 코드
├── visualize.py             # 시각화 유틸리티
├── checkpoints/             # 학습된 모델 체크포인트
├── test_results/            # 테스트 결과
└── README.md                # 이 파일
```

## 설치

필요한 패키지:

```bash
pip install torch torchvision numpy opencv-python matplotlib seaborn scikit-learn tqdm pillow
```

## 사용법

### 1. 데이터셋 준비

라벨링 데이터는 다음 형식이어야 합니다:

```json
{
  "image_path": "C:\\path\\to\\image.png",
  "points": [
    {
      "x": 100,
      "y": 200,
      "label": 1,  // 1: valid, 0: invalid
      "status": "valid"
    },
    ...
  ]
}
```

### 2. 모델 학습

```bash
cd autoencoder
python train.py
```

학습 설정은 `train.py`의 `CONFIG` 딕셔너리에서 수정할 수 있습니다:

```python
CONFIG = {
    'label_dir': r'C:\Pycode\camera_test\dot_detection_system\labeling_data',
    'model_type': 'improved',  # 'basic' or 'improved'
    'patch_size': 32,          # 패치 크기
    'latent_dim': 128,         # latent space 차원
    'batch_size': 64,
    'num_epochs': 100,
    'learning_rate': 1e-3,
    'val_split': 0.2,          # 검증 데이터 비율
    'augment': True,           # 데이터 증강 사용
}
```

학습 결과는 `checkpoints/` 폴더에 저장됩니다:
- `best_model.pth`: 가장 성능이 좋은 모델
- `training_history.png`: 학습 곡선
- `config.json`: 학습 설정

### 3. 모델 테스트

```bash
python test.py
```

테스트 결과는 `test_results/` 폴더에 저장됩니다:
- `confusion_matrix.png`: Confusion matrix
- `roc_curve.png`: ROC curve
- `error_distribution.png`: Error distribution
- `precision_recall_curve.png`: Precision-Recall curve
- `sample_predictions.png`: 예측 샘플 시각화
- `detailed_results.json`: 상세 결과 JSON
- `threshold.txt`: 최적 threshold 값

### 4. 실시간 추론

```python
from inference import DotFilterPredictor

# 예측기 초기화
predictor = DotFilterPredictor(
    checkpoint_path='./checkpoints/best_model.pth',
    threshold=0.01,  # 테스트에서 찾은 최적 threshold
    model_type='improved'
)

# 이미지와 점 좌표로 예측
import cv2
image = cv2.imread('image.png', cv2.IMREAD_GRAYSCALE)
points = [(100, 200), (300, 400), ...]

predictions = predictor.predict_batch(image, points)
# predictions: [1, 0, 1, ...] (1: valid, 0: invalid)
```

### 5. 시각화

```python
from visualize import visualize_predictions

# 예측 결과 시각화
visualize_predictions(
    image_path='image.png',
    points=[(100, 200), (300, 400), ...],
    predictions=[1, 0, 1, ...],
    save_path='result.png'
)
```

## 모델 아키텍처

### Basic Model (DotAutoencoder)

- **Encoder**: 4개의 Conv2D layers (32 → 64 → 128 → 256 channels)
- **Latent Space**: Fully connected layer (default: 64 dimensions)
- **Decoder**: 4개의 ConvTranspose2D layers (256 → 128 → 64 → 32 → 1)
- **파라미터 수**: ~1.5M

### Improved Model (ImprovedDotAutoencoder)

- **Encoder**: U-Net style with skip connections
- **Decoder**: Skip connections for better reconstruction
- **Latent Space**: 128 dimensions (default)
- **파라미터 수**: ~3.5M
- **장점**: 더 정교한 reconstruction, 더 좋은 성능

## 성능 최적화 팁

### 1. Threshold 조정

- **F1 score 기반**: 균형잡힌 성능
- **Youden's J**: ROC curve에서 최적점
- **수동 조정**: 특정 use case에 맞게 조정

```python
# test.py에서
CONFIG['threshold'] = 0.01  # 수동 설정
CONFIG['threshold_method'] = 'f1'  # 또는 'youden'
```

### 2. 데이터 증강

학습 시 데이터 증강을 사용하면 일반화 성능이 향상됩니다:

```python
CONFIG['augment'] = True
```

### 3. 모델 선택

- **Basic model**: 빠른 추론, 적은 메모리
- **Improved model**: 더 높은 정확도, 느린 추론

### 4. Patch Size

- **작은 패치 (16x16)**: 빠른 추론, 적은 context
- **큰 패치 (64x64)**: 느린 추론, 많은 context

## 문제 해결

### Out of Memory

```python
CONFIG['batch_size'] = 32  # 배치 크기 줄이기
CONFIG['model_type'] = 'basic'  # 작은 모델 사용
```

### Overfitting

```python
CONFIG['augment'] = True  # 데이터 증강 사용
CONFIG['early_stopping_patience'] = 10  # Early stopping
```

### Poor Performance

1. 더 많은 학습 데이터 수집
2. 더 긴 학습 시간 (`num_epochs` 증가)
3. Learning rate 조정
4. 더 큰 모델 사용 (`improved` model)
5. Threshold 재조정

## 라이선스

MIT License

## 작성자

Camera Test Project Team

