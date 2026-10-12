"""
학습된 모델을 사용한 일괄 테스트 시스템

학습된 딥러닝 모델을 불러와서 폴더의 모든 이미지에 대해 
점 검출 및 필터링을 수행하고 결과를 평가합니다.
"""

import os
import json
import glob
import cv2
import numpy as np
from datetime import datetime
from improved_dot_training import ImprovedDotDetector

def load_trained_model(model_path="batch_dot_detection_model.pth"):
    """학습된 모델 불러오기"""
    print(f"=== 학습된 모델 불러오기 ===")
    
    if not os.path.exists(model_path):
        print(f"❌ 모델 파일이 존재하지 않습니다: {model_path}")
        return None
    
    detector = ImprovedDotDetector()
    success = detector.load_model(model_path)
    
    if success:
        print(f"모델 불러오기 성공: {model_path}")
        return detector
    else:
        print(f"모델 불러오기 실패")
        return None

def test_single_image(detector, image_path, template_path, confidence_threshold=0.8):
    """단일 이미지에 대한 모델 테스트"""
    print(f"테스트 이미지: {os.path.basename(image_path)}")
    
    # 이미지 로드
    image = cv2.imread(image_path)
    if image is None:
        print(f"이미지를 불러올 수 없습니다: {image_path}")
        return None
    
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # 템플릿 매칭으로 초기 점 검출
    template = cv2.imread(template_path, cv2.IMREAD_GRAYSCALE)
    if template is None:
        print(f"템플릿 파일을 찾을 수 없습니다: {template_path}")
        return None
    
    # 전처리
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    equalized = cv2.equalizeHist(blurred)
    
    # 템플릿 매칭
    result = cv2.matchTemplate(equalized, template, cv2.TM_CCOEFF_NORMED)
    locations = np.where(result >= 0.7)
    locations = list(zip(*locations[::-1]))
    
    # 중복 제거
    template_h, template_w = template.shape
    rectangles = []
    for loc in locations:
        rect = [int(loc[0]), int(loc[1]), template_w, template_h]
        rectangles.append(rect)
        rectangles.append(rect)
    
    if len(rectangles) > 0:
        rectangles, weights = cv2.groupRectangles(rectangles, groupThreshold=1, eps=0.5)
    else:
        rectangles = []
    
    # 점 위치 계산
    positions = []
    for (x, y, w, h) in rectangles:
        center_x = x + int(w/2)
        center_y = y + int(h/2)
        positions.append((center_x, center_y))
    
    print(f"  초기 검출된 점: {len(positions)}개")
    
    if len(positions) == 0:
        return {
            'image_path': image_path,
            'initial_dots': 0,
            'filtered_dots': 0,
            'valid_dots': 0,
            'invalid_dots': 0,
            'confidence_avg': 0.0,
            'filter_ratio': 0.0
        }
    
    # 딥러닝 모델로 필터링
    predictions, confidences = detector.predict(gray, positions)
    
    # 결과 분석
    valid_positions = []
    valid_confidences = []
    
    for i, (pos, pred, conf) in enumerate(zip(positions, predictions, confidences)):
        if pred == 1 and conf >= confidence_threshold:
            valid_positions.append(pos)
            valid_confidences.append(conf)
    
    # 통계 계산 (Python 기본 타입으로 변환)
    initial_dots = int(len(positions))
    filtered_dots = int(len(valid_positions))
    valid_dots = int(sum(predictions))
    invalid_dots = int(len(predictions) - valid_dots)
    confidence_avg = float(np.mean(confidences)) if confidences else 0.0
    filter_ratio = float((filtered_dots / initial_dots * 100)) if initial_dots > 0 else 0.0
    
    print(f"  딥러닝 필터링 후: {filtered_dots}개")
    print(f"  유효한 점: {valid_dots}개")
    print(f"  무효한 점: {invalid_dots}개")
    print(f"  평균 신뢰도: {confidence_avg:.3f}")
    print(f"  필터링 비율: {filter_ratio:.1f}%")
    
    return {
        'image_path': image_path,
        'initial_dots': initial_dots,
        'filtered_dots': filtered_dots,
        'valid_dots': valid_dots,
        'invalid_dots': invalid_dots,
        'confidence_avg': confidence_avg,
        'filter_ratio': filter_ratio,
        'positions': [[int(pos[0]), int(pos[1])] for pos in positions],
        'valid_positions': [[int(pos[0]), int(pos[1])] for pos in valid_positions],
        'predictions': [int(pred) for pred in predictions],
        'confidences': [float(conf) for conf in confidences]
    }

def save_test_results(results, output_file="test_results.json"):
    """테스트 결과를 JSON 파일로 저장"""
    test_data = {
        'timestamp': datetime.now().isoformat(),
        'total_images': len(results),
        'total_initial_dots': int(sum(r['initial_dots'] for r in results)),
        'total_filtered_dots': int(sum(r['filtered_dots'] for r in results)),
        'total_valid_dots': int(sum(r['valid_dots'] for r in results)),
        'total_invalid_dots': int(sum(r['invalid_dots'] for r in results)),
        'avg_confidence': float(np.mean([r['confidence_avg'] for r in results])),
        'avg_filter_ratio': float(np.mean([r['filter_ratio'] for r in results])),
        'results': results
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(test_data, f, ensure_ascii=False, indent=2)
    
    print(f"테스트 결과 저장: {output_file}")

def batch_test_model(image_dir, template_path, model_path="batch_dot_detection_model.pth", 
                    confidence_threshold=0.8, output_dir="test_results"):
    """학습된 모델로 일괄 테스트"""
    print("=== 학습된 모델 일괄 테스트 ===")
    print(f"이미지 디렉토리: {image_dir}")
    print(f"템플릿 파일: {template_path}")
    print(f"모델 파일: {model_path}")
    print(f"신뢰도 임계값: {confidence_threshold}")
    
    # 출력 디렉토리 생성
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # 모델 불러오기
    detector = load_trained_model(model_path)
    if detector is None:
        return
    
    # 이미지 파일 찾기
    image_paths = []
    for ext in ['*.png', '*.jpg', '*.jpeg']:
        pattern = os.path.join(image_dir, ext)
        image_paths.extend(glob.glob(pattern))
    image_paths = sorted(image_paths)
    
    if not image_paths:
        print(f"이미지 디렉토리에서 이미지를 찾을 수 없습니다: {image_dir}")
        return
    
    print(f"발견된 이미지: {len(image_paths)}개")
    
    # 각 이미지에 대해 테스트
    results = []
    print(f"\n=== 일괄 테스트 시작 ===")
    
    for i, image_path in enumerate(image_paths):
        print(f"\n--- 이미지 {i+1}/{len(image_paths)} ---")
        
        try:
            result = test_single_image(detector, image_path, template_path, confidence_threshold)
            if result:
                results.append(result)
        except Exception as e:
            print(f"테스트 중 오류 발생: {e}")
            continue
    
    # 전체 통계
    if results:
        print(f"\n=== 전체 테스트 결과 ===")
        print(f"테스트된 이미지: {len(results)}개")
        print(f"총 초기 점: {sum(r['initial_dots'] for r in results)}개")
        print(f"총 필터링된 점: {sum(r['filtered_dots'] for r in results)}개")
        print(f"총 유효한 점: {sum(r['valid_dots'] for r in results)}개")
        print(f"총 무효한 점: {sum(r['invalid_dots'] for r in results)}개")
        print(f"평균 신뢰도: {np.mean([r['confidence_avg'] for r in results]):.3f}")
        print(f"평균 필터링 비율: {np.mean([r['filter_ratio'] for r in results]):.1f}%")
        
        # 결과 저장
        output_file = os.path.join(output_dir, "test_results.json")
        save_test_results(results, output_file)
        
        print(f"\n일괄 테스트 완료!")
        print(f"결과가 저장되었습니다: {output_file}")
    else:
        print("테스트할 수 있는 이미지가 없습니다.")

def main():
    """메인 함수"""
    # 설정
    image_dir = r"C:\Pycode\camera_test\imgs"
    template_path = "dot_img.png"
    model_path = "batch_dot_detection_model.pth"
    output_dir = "test_results"
    confidence_threshold = 0.8
    
    # 일괄 테스트 실행
    batch_test_model(image_dir, template_path, model_path, confidence_threshold, output_dir)

if __name__ == "__main__":
    main()
