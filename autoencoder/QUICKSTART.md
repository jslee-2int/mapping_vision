# 빠른 시작 가이드

이 가이드는 Autoencoder 기반 Dot Filtering 시스템을 빠르게 시작하는 방법을 설명합니다.

## 1단계: 환경 설정

### 필수 패키지 설치

```bash
cd autoencoder
pip install -r requirements.txt
```

또는 개별 설치:

```bash
pip install torch torchvision numpy opencv-python matplotlib seaborn scikit-learn tqdm pillow
```

## 2단계: 모델 학습

### 기본 학습

```bash
python run_training.py
```

이 명령은 다음을 수행합니다:
- 라벨링 데이터에서 valid 점만 추출
- Autoencoder 모델 학습 (약 100 에폭)
- 최적 모델을 `checkpoints/` 폴더에 저장
- 학습 곡선을 `training_history.png`로 저장

### 학습 설정 변경

`train.py` 파일을 열고 `CONFIG` 딕셔너리를 수정:

```python
CONFIG = {
    'label_dir': r'C:\Pycode\camera_test\dot_detection_system\labeling_data',
    'model_type': 'improved',  # 'basic' 또는 'improved'
    'patch_size': 32,          # 패치 크기 (16, 32, 64 등)
    'latent_dim': 128,         # latent space 차원
    'batch_size': 64,          # 배치 크기
    'num_epochs': 100,         # 학습 에폭 수
    'learning_rate': 1e-3,     # 학습률
    'augment': True,           # 데이터 증강 사용
}
```

### 학습 시간

- GPU 사용 시: 약 10-20분
- CPU 사용 시: 약 1-2시간

## 3단계: 모델 테스트

```bash
python run_testing.py
```

이 명령은 다음을 수행합니다:
- 학습된 모델을 로드
- 모든 라벨링 데이터에 대해 평가
- 최적 threshold 자동 계산
- 결과를 `test_results/` 폴더에 저장:
  - `confusion_matrix.png`: Confusion matrix
  - `roc_curve.png`: ROC curve
  - `error_distribution.png`: Error 분포
  - `precision_recall_curve.png`: Precision-Recall curve
  - `sample_predictions.png`: 예측 샘플
  - `detailed_results.json`: 상세 결과
  - `threshold.txt`: 최적 threshold 값

### 결과 해석

테스트 결과에서 다음을 확인:
1. **Accuracy**: 전체 정확도
2. **Precision/Recall**: Valid/Invalid 각각의 성능
3. **Threshold**: 최적 threshold 값 (추론 시 사용)

## 4단계: 추론 데모

```bash
python run_inference_demo.py
```

이 데모는 학습된 모델을 사용하여 새로운 점들을 분류합니다.

## 5단계: 실제 사용

### Python 코드에서 사용

```python
from autoencoder.inference import DotFilterPredictor
import cv2

# 모델 초기화
predictor = DotFilterPredictor(
    checkpoint_path='./autoencoder/checkpoints/best_model.pth',
    threshold=0.01,  # 테스트에서 찾은 최적 threshold
    model_type='improved'
)

# 이미지 로드
image = cv2.imread('your_image.png', cv2.IMREAD_GRAYSCALE)

# 점들 정의
points = [(100, 200), (300, 400), (500, 600)]

# 예측
predictions, errors, confidences = predictor.predict_batch(image, points)

# 결과 출력
for point, pred, error, conf in zip(points, predictions, errors, confidences):
    status = "VALID" if pred == 1 else "INVALID"
    print(f"Point {point}: {status} (error={error:.4f}, confidence={conf:.2f})")

# Valid 점만 필터링
valid_points = predictor.filter_points(image, points)
print(f"\nValid points: {valid_points}")
```

### 기존 코드에 통합

기존 점 검출 시스템에 Autoencoder 필터를 추가:

```python
# 점 검출 (기존 방법)
detected_points = your_dot_detection_function(image)

# Autoencoder로 필터링
valid_points = predictor.filter_points(image, detected_points)

# Valid 점만 사용
process_dots(valid_points)
```

### 시각화

```python
from autoencoder.visualize import visualize_predictions

visualize_predictions(
    image_path='your_image.png',
    points=points,
    predictions=predictions,
    confidences=confidences,
    save_path='result.png'
)
```

## 고급 사용법

### Threshold 조정

Threshold를 조정하여 민감도를 변경:

```python
# 더 엄격한 필터 (더 많은 점을 invalid로 판정)
predictor.set_threshold(0.005)

# 더 관대한 필터 (더 많은 점을 valid로 판정)
predictor.set_threshold(0.02)
```

### 배치 처리

여러 이미지를 효율적으로 처리:

```python
import os
import glob

image_files = glob.glob('images/*.png')

for image_file in image_files:
    image = cv2.imread(image_file, cv2.IMREAD_GRAYSCALE)
    
    # 점 검출
    points = detect_dots(image)
    
    # 필터링
    valid_points = predictor.filter_points(image, points)
    
    # 저장
    save_results(image_file, valid_points)
```

### 상세 정보 확인

```python
valid_points, details = predictor.filter_points(
    image, 
    points, 
    return_details=True
)

# 각 점의 상세 정보
for detail in details:
    print(f"Point: {detail['point']}")
    print(f"  Status: {detail['status']}")
    print(f"  Error: {detail['error']:.6f}")
    print(f"  Confidence: {detail['confidence']:.2%}")
```

## 문제 해결

### Q: "Out of memory" 에러가 발생합니다.

A: 배치 크기를 줄이세요:

```python
CONFIG['batch_size'] = 32  # 또는 16
```

### Q: 학습이 너무 오래 걸립니다.

A: 다음을 시도:
1. GPU 사용 확인 (`torch.cuda.is_available()`)
2. 에폭 수 줄이기 (`num_epochs = 50`)
3. Basic 모델 사용 (`model_type = 'basic'`)

### Q: 성능이 좋지 않습니다.

A: 다음을 시도:
1. 더 많은 학습 데이터 수집
2. 데이터 증강 사용 (`augment = True`)
3. Threshold 재조정
4. Improved 모델 사용 (`model_type = 'improved'`)
5. 더 긴 학습 (`num_epochs = 200`)

### Q: Threshold를 어떻게 설정해야 하나요?

A: 테스트 결과의 `threshold.txt` 파일을 참고하거나, 용도에 따라 조정:
- **높은 정밀도 필요**: threshold를 낮춤 (예: 0.005)
- **높은 재현율 필요**: threshold를 높임 (예: 0.02)

## 다음 단계

1. 더 많은 라벨링 데이터 수집
2. 하이퍼파라미터 튜닝
3. 앙상블 모델 구축
4. 실시간 처리 최적화

## 도움이 필요하신가요?

자세한 내용은 `README.md`를 참고하세요.

