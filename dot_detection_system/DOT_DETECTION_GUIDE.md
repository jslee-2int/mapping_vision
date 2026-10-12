# 점(Dot) 검출 및 필터링 가이드

## 문제 상황
격자 패턴의 점들을 찾아가는 시스템에서 다음과 같은 문제가 발생합니다:
1. 관심없는 점들이 섞여 있음
2. 의미없는 입자와 구별이 어려움
3. 격자 패턴이지만 비어있는 위치도 있음

## 해결 방법

### 1. 개선된 템플릿 매칭 (기본 활성화)

현재 시스템에 다음과 같은 3단계 필터링이 추가되었습니다:

#### Stage 1: 특징 기반 필터링
- **크기 (Size)**: 너무 작거나 큰 점 제거
- **원형도 (Circularity)**: 원형이 아닌 노이즈 제거
- **대비 (Contrast)**: 흐릿한 점 제거
- **밝기 (Brightness)**: 적절한 밝기 검증

#### Stage 2: 격자 패턴 검증
- 격자 간격을 자동으로 찾아냄
- 격자 패턴에 맞지 않는 점 제거
- 비어있는 위치도 처리 가능 (최소 1개의 이웃만 있으면 유지)

#### Stage 3: 클러스터링 기반 이상치 제거
- DBSCAN 알고리즘 사용
- 고립된 점들을 자동으로 제거
- scikit-learn 라이브러리 필요

### 2. 파라미터 조정

코드에서 다음 파라미터를 조정할 수 있습니다:

```python
# 크기 필터링
self.filter_min_size = 10        # 최소 점 크기 (픽셀)
self.filter_max_size = 500       # 최대 점 크기 (픽셀)

# 형태 필터링
self.filter_min_circularity = 0.3  # 최소 원형도 (0-1, 1이 완벽한 원)
self.filter_min_contrast = 5       # 최소 대비

# 격자 패턴 검증
self.grid_tolerance = 0.3          # 격자 간격 허용 오차 (30%)

# 클러스터링
self.clustering_eps = 50           # DBSCAN 최대 거리 (픽셀)
self.clustering_min_samples = 2    # 클러스터 최소 점 개수
```

### 3. 설치 요구사항

필터링 기능을 모두 사용하려면 다음 패키지가 필요합니다:

```bash
pip install -r requirements_pylablib.txt
```

또는 개별 설치:
```bash
pip install scikit-learn scipy
```

> 참고: scikit-learn이 없어도 기본 기능은 작동합니다 (클러스터링만 비활성화됨)

### 4. 사용 방법

#### 기본 사용
- UI에서 "Dot Detection Method"를 "Template"으로 선택
- 이미 개선된 필터링이 자동으로 적용됩니다
- Debug 모드를 켜면 각 단계별 필터링 결과를 확인할 수 있습니다

#### 디버그 모드 확인
```python
self.debug_mode = True  # main.py에서 설정
```

디버그 출력 예시:
```
Grid validation: 150 -> 120 points
Outlier removal: 120 -> 95 points
```

### 5. 고급 사용법

#### 파라미터 실시간 조정
UI를 통해 파라미터를 조정하고 싶다면, 다음과 같은 컨트롤을 추가할 수 있습니다:

```python
# init_ui() 메서드에 추가
self.slider_circularity = QSlider()
self.slider_circularity.setMinimum(0)
self.slider_circularity.setMaximum(100)
self.slider_circularity.setValue(30)
self.slider_circularity.valueChanged.connect(
    lambda v: setattr(self, 'filter_min_circularity', v/100.0)
)
```

### 6. 결과 검증

검출된 점들이 올바른지 확인하는 방법:

1. **시각적 확인**: 이미지에 마젠타 색 십자 마커가 표시됨
2. **개수 확인**: 예상 격자 개수와 비교
3. **위치 확인**: 모터 이동 후 올바른 위치로 이동하는지 확인

### 7. 문제 해결

#### 점이 너무 많이 검출되는 경우
- `filter_min_circularity` 증가 (예: 0.5)
- `filter_min_contrast` 증가 (예: 10)
- `clustering_eps` 감소 (예: 30)

#### 점이 너무 적게 검출되는 경우
- `filter_min_size` 감소
- `filter_max_size` 증가
- `filter_min_circularity` 감소 (예: 0.2)
- `grid_tolerance` 증가 (예: 0.5)

#### 격자 패턴 검증이 잘못된 경우
- 격자가 불규칙하면 `grid_tolerance` 증가
- 격자가 여러 개 있으면 클러스터링 파라미터 조정

### 8. 향후 개선 방안

딥러닝 기반 분류를 원하는 경우:

1. **YOLOv8**: 점 검출 및 분류
2. **간단한 CNN**: 유효한 점 vs 노이즈 분류
3. **데이터 수집**: 
   - 유효한 점 이미지 100장+
   - 노이즈 이미지 100장+
   - 라벨링 후 학습

간단한 CNN 분류기 예시는 필요시 별도 제공 가능합니다.

## 요약

현재 시스템은 다음과 같이 작동합니다:

```
템플릿 매칭 
  → 특징 추출 (크기, 원형도, 대비)
  → 특징 기반 필터링
  → 격자 패턴 검증
  → 클러스터링 이상치 제거
  → 최종 유효한 점들
```

이 방법으로 대부분의 노이즈를 효과적으로 제거할 수 있습니다!

