"""
Autoencoder 사용 예제 코드
"""

import os
import sys
import cv2
import numpy as np
import json

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from inference import DotFilterPredictor
from visualize import visualize_predictions


def example_1_basic_usage():
    """예제 1: 기본 사용법"""
    print("=" * 70)
    print("예제 1: 기본 사용법")
    print("=" * 70)
    
    # 체크포인트 경로 설정
    checkpoint_path = './checkpoints/best_model.pth'
    
    if not os.path.exists(checkpoint_path):
        print("Error: 모델이 학습되지 않았습니다.")
        print("먼저 'python run_training.py'를 실행하세요.")
        return
    
    # 예측기 초기화
    print("\n1. 모델 로드 중...")
    predictor = DotFilterPredictor(
        checkpoint_path=checkpoint_path,
        model_type='improved',
        patch_size=32,
        latent_dim=128
    )
    
    # 테스트 이미지 로드
    image_path = r'C:\Pycode\camera_test\imgs\25-10-14_1.png'
    
    if not os.path.exists(image_path):
        print(f"Error: 이미지를 찾을 수 없습니다: {image_path}")
        return
    
    print(f"\n2. 이미지 로드: {os.path.basename(image_path)}")
    image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    
    # JSON 라벨링 파일에서 일부 점들 읽어오기
    json_path = r'C:\Pycode\camera_test\dot_detection_system\labeling_data\25-10-14_1_labels.json'
    
    with open(json_path, 'r', encoding='utf-8') as f:
        label_data = json.load(f)
    
    # 처음 10개 점만 선택 (데모용)
    selected_points_data = label_data['points'][:10]
    test_points = [(p['x'], p['y']) for p in selected_points_data]
    ground_truth_labels = [p['label'] for p in selected_points_data]
    
    print(f"\n3. {len(test_points)}개의 점 예측 중... (라벨링 파일에서 로드)")
    
    # 예측 수행
    predictions, errors, confidences = predictor.predict_batch(image, test_points)
    
    # 결과 출력
    print("\n결과:")
    print("-" * 70)
    correct_count = 0
    for i, (point, pred, error, conf, gt) in enumerate(zip(test_points, predictions, errors, confidences, ground_truth_labels)):
        pred_status = "VALID" if pred == 1 else "INVALID"
        gt_status = "Valid" if gt == 1 else "Invalid"
        is_correct = (pred == gt)
        correct_count += is_correct
        
        color = "\033[92m" if pred == 1 else "\033[91m"  # Green or Red
        reset = "\033[0m"
        status_symbol = "✓" if is_correct else "✗"
        
        print(f"{status_symbol} {i+1}. Point {point}: {color}{pred_status}{reset}")
        print(f"   Ground Truth: {gt_status} | Error: {error:.6f} | Confidence: {conf:.2%}")
    
    # Valid 점 개수 및 정확도
    num_valid = sum(predictions)
    accuracy = correct_count / len(test_points) * 100
    print(f"\nPredicted Valid 점: {num_valid}/{len(test_points)}")
    print(f"정확도: {accuracy:.1f}% ({correct_count}/{len(test_points)} 맞음)")
    
    # 시각화
    print("\n4. 결과 시각화 저장 중...")
    visualize_predictions(
        image_path=image_path,
        points=test_points,
        predictions=predictions,
        labels=ground_truth_labels,
        confidences=confidences,
        threshold=predictor.threshold,
        save_path='./example_1_result.png'
    )
    print("저장 완료: example_1_result.png")
    print("   (녹색=Valid 예측, 빨강=Invalid 예측, 노란 테두리=잘못된 예측)")


def example_2_filter_points():
    """예제 2: 점 필터링"""
    print("\n\n" + "=" * 70)
    print("예제 2: Valid 점만 추출하기")
    print("=" * 70)
    
    checkpoint_path = './checkpoints/best_model.pth'
    
    if not os.path.exists(checkpoint_path):
        print("Error: 모델이 학습되지 않았습니다.")
        return
    
    # 예측기 초기화
    predictor = DotFilterPredictor(
        checkpoint_path=checkpoint_path,
        model_type='improved'
    )
    
    # 이미지 로드
    image_path = r'C:\Pycode\camera_test\imgs\25-10-14_1.png'
    
    if not os.path.exists(image_path):
        print(f"Error: 이미지를 찾을 수 없습니다: {image_path}")
        return
    
    image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    
    # JSON 라벨링 파일에서 실제 점들 읽어오기
    json_path = r'C:\Pycode\camera_test\dot_detection_system\labeling_data\25-10-14_1_labels.json'
    
    print(f"\n라벨링 파일에서 점 데이터 로드: {os.path.basename(json_path)}")
    
    with open(json_path, 'r', encoding='utf-8') as f:
        label_data = json.load(f)
    
    # 모든 점 추출
    all_points = [(p['x'], p['y']) for p in label_data['points']]
    ground_truth_labels = [p['label'] for p in label_data['points']]
    
    print(f"총 {len(all_points)}개 점 로드")
    print(f"  - Ground Truth Valid: {sum(ground_truth_labels)}개")
    print(f"  - Ground Truth Invalid: {len(ground_truth_labels) - sum(ground_truth_labels)}개")
    
    # Valid 점만 필터링
    valid_points, details = predictor.filter_points(
        image, 
        all_points, 
        return_details=True
    )
    
    print(f"\n필터링 후 Valid 점: {len(valid_points)}개")
    print(f"제거된 Invalid 점: {len(all_points) - len(valid_points)}개")
    
    # Ground truth와 비교
    predictions_list = [detail['prediction'] for detail in details]
    correct_predictions = sum(p == gt for p, gt in zip(predictions_list, ground_truth_labels))
    accuracy = correct_predictions / len(all_points) * 100
    
    print(f"\n정확도: {accuracy:.1f}% ({correct_predictions}/{len(all_points)} 맞음)")
    
    # 상세 정보 출력 (처음 10개)
    print("\n상세 정보 (처음 10개):")
    print("-" * 70)
    for i, (detail, gt_label) in enumerate(zip(details[:10], ground_truth_labels[:10])):
        pred_correct = detail['prediction'] == gt_label
        status_symbol = "✓" if pred_correct else "✗"
        gt_status = "Valid" if gt_label == 1 else "Invalid"
        
        print(f"{status_symbol} Point {detail['point']}:")
        print(f"  Predicted: {detail['status'].upper()} | Ground Truth: {gt_status}")
        print(f"  Error: {detail['error']:.6f} | Confidence: {detail['confidence']:.2%}")
    
    if len(details) > 10:
        print(f"... (생략 {len(details) - 10}개)")
    
    # 시각화 저장
    print("\n결과 시각화 저장 중...")
    visualize_predictions(
        image_path=image_path,
        points=all_points,
        predictions=predictions_list,
        labels=ground_truth_labels,
        confidences=[d['confidence'] for d in details],
        threshold=predictor.threshold,
        save_path='./example_2_result.png'
    )
    print("저장 완료: example_2_result.png")


def example_3_threshold_adjustment():
    """예제 3: Threshold 조정"""
    print("\n\n" + "=" * 70)
    print("예제 3: Threshold 조정으로 민감도 변경")
    print("=" * 70)
    
    checkpoint_path = './checkpoints/best_model.pth'
    
    if not os.path.exists(checkpoint_path):
        print("Error: 모델이 학습되지 않았습니다.")
        return
    
    # 예측기 초기화
    predictor = DotFilterPredictor(
        checkpoint_path=checkpoint_path,
        model_type='improved'
    )
    
    # 이미지 로드
    image_path = r'C:\Pycode\camera_test\imgs\25-10-14_1.png'
    
    if not os.path.exists(image_path):
        print(f"Error: 이미지를 찾을 수 없습니다: {image_path}")
        return
    
    image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    
    # JSON 라벨링 파일에서 점들 읽어오기
    json_path = r'C:\Pycode\camera_test\dot_detection_system\labeling_data\25-10-14_1_labels.json'
    
    with open(json_path, 'r', encoding='utf-8') as f:
        label_data = json.load(f)
    
    # 처음 20개 점 선택
    selected_points_data = label_data['points'][:20]
    test_points = [(p['x'], p['y']) for p in selected_points_data]
    ground_truth_labels = [p['label'] for p in selected_points_data]
    
    gt_valid_count = sum(ground_truth_labels)
    print(f"\n테스트 점: {len(test_points)}개 (GT Valid: {gt_valid_count}, GT Invalid: {len(test_points) - gt_valid_count})")
    
    # 여러 threshold 값으로 테스트
    thresholds = [0.005, 0.01, 0.02, 0.05]
    
    print("\nThreshold에 따른 결과 변화:")
    print("-" * 70)
    
    for threshold in thresholds:
        predictor.set_threshold(threshold)
        predictions, _, _ = predictor.predict_batch(image, test_points)
        num_valid = sum(predictions)
        
        # 정확도 계산
        correct = sum(p == gt for p, gt in zip(predictions, ground_truth_labels))
        accuracy = correct / len(test_points) * 100
        
        print(f"Threshold = {threshold:.4f}: Valid 점 = {num_valid:2d}/{len(test_points)} | 정확도 = {accuracy:5.1f}%")
    
    print("\n* Threshold가 낮을수록 더 엄격한 필터링 (더 적은 valid 점)")
    print("* Threshold가 높을수록 더 관대한 필터링 (더 많은 valid 점)")


def example_4_batch_processing():
    """예제 4: 여러 이미지 배치 처리"""
    print("\n\n" + "=" * 70)
    print("예제 4: 여러 이미지 배치 처리")
    print("=" * 70)
    
    checkpoint_path = './checkpoints/best_model.pth'
    
    if not os.path.exists(checkpoint_path):
        print("Error: 모델이 학습되지 않았습니다.")
        return
    
    # 예측기 초기화
    predictor = DotFilterPredictor(
        checkpoint_path=checkpoint_path,
        model_type='improved'
    )
    
    # 여러 이미지 파일
    image_dir = r'C:\Pycode\camera_test\imgs'
    
    if not os.path.exists(image_dir):
        print(f"Error: 이미지 디렉토리를 찾을 수 없습니다: {image_dir}")
        return
    
    import glob
    image_files = glob.glob(os.path.join(image_dir, '*.png'))[:3]  # 처음 3개만
    
    if len(image_files) == 0:
        print(f"Error: 이미지 파일을 찾을 수 없습니다.")
        return
    
    print(f"\n{len(image_files)}개의 이미지 처리 중...\n")
    
    for i, image_file in enumerate(image_files):
        print(f"{i+1}. {os.path.basename(image_file)}")
        
        image = cv2.imread(image_file, cv2.IMREAD_GRAYSCALE)
        
        # 임의의 점들 (실제로는 검출 시스템에서 가져옴)
        # 여기서는 예시로 이미지 중앙 근처의 점들 생성
        h, w = image.shape
        test_points = [
            (w//2, h//2),
            (w//2 + 50, h//2 + 50),
            (w//2 - 50, h//2 - 50),
        ]
        
        # 필터링
        valid_points = predictor.filter_points(image, test_points)
        
        print(f"   검출: {len(test_points)}개 -> 필터링 후: {len(valid_points)}개")


def main():
    """모든 예제 실행"""
    print("\n")
    print("*" * 70)
    print("*" + " " * 68 + "*")
    print("*" + " " * 18 + "Autoencoder 사용 예제 모음" + " " * 22 + "*")
    print("*" + " " * 68 + "*")
    print("*" * 70)
    
    try:
        example_1_basic_usage()
        example_2_filter_points()
        example_3_threshold_adjustment()
        example_4_batch_processing()
        
        print("\n\n" + "=" * 70)
        print("모든 예제 완료!")
        print("=" * 70)
        
    except Exception as e:
        print(f"\n\nError: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

