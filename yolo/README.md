# YOLO Custom Training for Dot Detection

이 디렉토리는 점(dot) 감지를 위한 YOLO 커스텀 트레이닝을 위한 파일들을 포함합니다.

## 📁 디렉토리 구조

```
yolo/
├── data/                    # 트레이닝 데이터
│   ├── images/             # 이미지 파일들
│   ├── labels/             # YOLO 형식 라벨 파일들
│   ├── train/              # 훈련 데이터 (자동 생성)
│   ├── val/                # 검증 데이터 (자동 생성)
│   └── test/               # 테스트 데이터 (자동 생성)
├── models/                 # 훈련된 모델 저장
├── results/                # 훈련 결과
├── yolo_detector.py        # YOLO 감지 클래스
├── test_yolo.py           # YOLO 테스트 스크립트
├── convert_data.py        # 데이터 변환 스크립트
├── split_data.py          # 데이터 분할 스크립트
├── train_yolo.py          # YOLO 훈련 스크립트
└── run_training.py        # 전체 워크플로우 실행
```

## 🚀 사용 방법

### 1. 의존성 설치
```bash
pip install ultralytics
pip install torch torchvision
pip install opencv-python
pip install numpy
```

### 2. 전체 워크플로우 실행
```bash
cd yolo
python run_training.py
```

### 3. 단계별 실행

#### 데이터 변환
```bash
python convert_data.py
```

#### 데이터 분할
```bash
python split_data.py
```

#### 모델 훈련
```bash
python train_yolo.py
```

### 4. YOLO 테스트
```bash
python test_yolo.py
```

## 📊 데이터 형식

### 입력 데이터
- **이미지**: `../imgs/*.png`
- **라벨**: `../dot_detection_system/labeling_data/*_labels.json`

### YOLO 형식 변환
- **이미지**: `data/images/*.png`
- **라벨**: `data/labels/*.txt` (YOLO 형식)

### 데이터 분할
- **훈련**: 70% (train/)
- **검증**: 20% (val/)
- **테스트**: 10% (test/)

## 🎯 클래스 정의

- **클래스 0**: 유효한 점 (valid dot)
- **배경**: 무효한 점들은 배경으로 처리

## ⚙️ 훈련 설정

### 기본 설정
- **모델**: YOLOv8n (nano)
- **이미지 크기**: 640x640
- **배치 크기**: 8
- **에포크**: 30 (시작값)

### 고급 설정
`train_yolo.py`에서 다음 매개변수들을 조정할 수 있습니다:
- `model_size`: 모델 크기 (n, s, m, l, x)
- `epochs`: 훈련 에포크 수
- `batch_size`: 배치 크기
- `img_size`: 이미지 크기

## 📈 결과 확인

훈련 완료 후:
- **모델**: `models/dot_detection.pt`
- **결과**: `results/dot_detection/`
- **메트릭**: mAP50, mAP50-95

## 🔧 문제 해결

### 1. ultralytics 설치 오류
```bash
pip install --upgrade ultralytics
```

### 2. CUDA 메모리 부족
- `batch_size`를 줄이세요 (예: 4, 2)
- `img_size`를 줄이세요 (예: 416, 320)

### 3. 데이터 부족
- 더 많은 이미지와 라벨을 추가하세요
- 데이터 증강을 고려하세요

## 📝 주의사항

1. **데이터 품질**: 라벨링이 정확한지 확인하세요
2. **클래스 불균형**: 유효한 점과 무효한 점의 비율을 확인하세요
3. **하이퍼파라미터**: 데이터 크기에 따라 조정하세요
4. **검증**: 훈련 후 반드시 검증 데이터로 테스트하세요
