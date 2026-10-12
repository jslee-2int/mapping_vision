"""
검출 결과 시각화

학습된 모델의 검출 결과를 이미지 위에 박스로 표시하여 시각화합니다.
"""

import os
import json
import cv2
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime

def load_test_results(results_file="test_results_low_threshold/test_results.json"):
    """테스트 결과 불러오기"""
    if not os.path.exists(results_file):
        print(f"테스트 결과 파일이 존재하지 않습니다: {results_file}")
        return None
    
    try:
        with open(results_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"테스트 결과 불러오기 성공: {results_file}")
        return data
    except Exception as e:
        print(f"테스트 결과 불러오기 실패: {e}")
        return None

def visualize_single_image(image_path, positions, valid_positions, predictions, confidences, output_dir="detection_visualization"):
    """단일 이미지의 검출 결과 시각화"""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # 이미지 로드
    image = cv2.imread(image_path)
    if image is None:
        print(f"이미지를 불러올 수 없습니다: {image_path}")
        return None
    
    # 결과 이미지 생성
    result_image = image.copy()
    
    # 모든 검출된 점 (빨간색 박스)
    for i, (x, y) in enumerate(positions):
        # 박스 그리기
        cv2.rectangle(result_image, (x-15, y-15), (x+15, y+15), (0, 0, 255), 2)
        
        # 예측 결과와 신뢰도 표시
        pred = predictions[i] if i < len(predictions) else 0
        conf = confidences[i] if i < len(confidences) else 0.0
        
        # 텍스트 색상 (유효한 점은 초록색, 무효한 점은 빨간색)
        color = (0, 255, 0) if pred == 1 else (0, 0, 255)
        text = f"{i}: {pred} ({conf:.2f})"
        
        # 텍스트 배경
        text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)[0]
        cv2.rectangle(result_image, (x-15, y-25), (x-15+text_size[0], y-25-text_size[1]-5), (255, 255, 255), -1)
        cv2.putText(result_image, text, (x-15, y-25), cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)
    
    # 유효한 점 강조 (초록색 박스)
    for x, y in valid_positions:
        cv2.rectangle(result_image, (x-20, y-20), (x+20, y+20), (0, 255, 0), 3)
        cv2.putText(result_image, "VALID", (x-20, y-25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
    
    # 결과 저장
    filename = os.path.basename(image_path)
    base_name = os.path.splitext(filename)[0]
    output_path = os.path.join(output_dir, f"{base_name}_detection_result.png")
    cv2.imwrite(output_path, result_image)
    
    print(f"검출 결과 시각화 저장: {output_path}")
    return output_path

def visualize_all_detections(data, output_dir="detection_visualization"):
    """모든 이미지의 검출 결과 시각화"""
    if not data:
        return
    
    results = data['results']
    print(f"\n=== 검출 결과 시각화 시작 ===")
    print(f"총 {len(results)}개 이미지 처리")
    
    # 출력 디렉토리 생성
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # 각 이미지별 시각화
    for i, result in enumerate(results):
        print(f"\n--- 이미지 {i+1}/{len(results)}: {os.path.basename(result['image_path'])} ---")
        
        # 데이터 추출
        image_path = result['image_path']
        positions = result['positions']
        valid_positions = result['valid_positions']
        predictions = result['predictions']
        confidences = result['confidences']
        
        print(f"  초기 검출: {len(positions)}개")
        print(f"  필터링 후: {len(valid_positions)}개")
        print(f"  유효한 점: {sum(predictions)}개")
        print(f"  평균 신뢰도: {np.mean(confidences):.3f}")
        
        # 시각화
        try:
            output_path = visualize_single_image(
                image_path, positions, valid_positions, 
                predictions, confidences, output_dir
            )
            if output_path:
                print(f"  시각화 완료: {os.path.basename(output_path)}")
        except Exception as e:
            print(f"  시각화 실패: {e}")
    
    print(f"\n=== 시각화 완료 ===")
    print(f"결과가 저장되었습니다: {output_dir}/")

def create_summary_visualization(data, output_dir="detection_visualization"):
    """요약 시각화 생성"""
    if not data:
        return
    
    results = data['results']
    
    # 통계 계산
    total_images = len(results)
    total_initial = sum(r['initial_dots'] for r in results)
    total_filtered = sum(r['filtered_dots'] for r in results)
    total_valid = sum(r['valid_dots'] for r in results)
    avg_confidence = np.mean([r['confidence_avg'] for r in results])
    avg_filter_ratio = np.mean([r['filter_ratio'] for r in results])
    
    # 요약 이미지 생성
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    fig.suptitle('Deep Learning Dot Detection Results Summary', fontsize=16)
    
    # 1. 점 개수 비교
    image_names = [os.path.basename(r['image_path']) for r in results]
    initial_dots = [r['initial_dots'] for r in results]
    filtered_dots = [r['filtered_dots'] for r in results]
    valid_dots = [r['valid_dots'] for r in results]
    
    x = np.arange(len(image_names))
    width = 0.25
    
    axes[0, 0].bar(x - width, initial_dots, width, label='Initial Dots', alpha=0.8, color='red')
    axes[0, 0].bar(x, filtered_dots, width, label='Filtered Dots', alpha=0.8, color='blue')
    axes[0, 0].bar(x + width, valid_dots, width, label='Valid Dots', alpha=0.8, color='green')
    
    axes[0, 0].set_xlabel('Images')
    axes[0, 0].set_ylabel('Number of Dots')
    axes[0, 0].set_title('Dot Count Comparison')
    axes[0, 0].legend()
    axes[0, 0].tick_params(axis='x', rotation=45)
    
    # 2. 신뢰도 분포
    confidences = [r['confidence_avg'] for r in results]
    axes[0, 1].hist(confidences, bins=20, alpha=0.7, color='skyblue', edgecolor='black')
    axes[0, 1].set_xlabel('Average Confidence')
    axes[0, 1].set_ylabel('Frequency')
    axes[0, 1].set_title('Confidence Distribution')
    axes[0, 1].axvline(avg_confidence, color='red', linestyle='--', 
                      label=f'Average: {avg_confidence:.3f}')
    axes[0, 1].legend()
    
    # 3. 필터링 비율
    filter_ratios = [r['filter_ratio'] for r in results]
    axes[1, 0].bar(range(len(image_names)), filter_ratios, alpha=0.7, color='lightgreen')
    axes[1, 0].set_xlabel('Images')
    axes[1, 0].set_ylabel('Filtering Ratio (%)')
    axes[1, 0].set_title('Filtering Ratio per Image')
    axes[1, 0].tick_params(axis='x', rotation=45)
    axes[1, 0].axhline(avg_filter_ratio, color='red', linestyle='--', 
                      label=f'Average: {avg_filter_ratio:.1f}%')
    axes[1, 0].legend()
    
    # 4. 전체 통계
    total_valid = sum(valid_dots)
    total_invalid = total_initial - total_valid
    
    labels = ['Valid Dots', 'Invalid Dots']
    sizes = [total_valid, total_invalid]
    colors = ['lightgreen', 'lightcoral']
    
    axes[1, 1].pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90)
    axes[1, 1].set_title('Overall Dot Classification')
    
    plt.tight_layout()
    
    # 요약 이미지 저장
    summary_path = os.path.join(output_dir, "detection_summary.png")
    plt.savefig(summary_path, dpi=300, bbox_inches='tight')
    print(f"요약 시각화 저장: {summary_path}")
    
    plt.show()

def main():
    """메인 함수"""
    print("검출 결과 시각화")
    print("=" * 50)
    
    # 테스트 결과 파일 경로
    results_file = "test_results_low_threshold/test_results.json"
    
    # 결과 불러오기
    data = load_test_results(results_file)
    if not data:
        return
    
    # 모든 이미지 시각화
    visualize_all_detections(data)
    
    # 요약 시각화
    try:
        create_summary_visualization(data)
        print("요약 시각화 완료!")
    except Exception as e:
        print(f"요약 시각화 중 오류 발생: {e}")

if __name__ == "__main__":
    main()
