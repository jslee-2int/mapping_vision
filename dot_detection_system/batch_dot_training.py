"""
일괄 딥러닝 점 검출 학습 시스템

폴더의 모든 이미지에 대해 일괄로 라벨링하고, 
라벨링 데이터를 JSON 파일로 저장합니다.
"""

import os
import json
import glob
from datetime import datetime
from improved_dot_training import ImprovedDotDetector

def save_labeling_data(image_path, positions, labels, output_dir="labeling_data"):
    """라벨링 데이터를 JSON 파일로 저장"""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    qq
    # 파일명에서 확장자 제거
    base_name = os.path.splitext(os.path.basename(image_path))[0]
    json_path = os.path.join(output_dir, f"{base_name}_labels.json")
    
    # 라벨링 데이터 구성
    labeling_data = {
        "image_path": image_path,
        "timestamp": datetime.now().isoformat(),
        "total_points": len(positions),
        "valid_points": sum(labels),
        "invalid_points": len(labels) - sum(labels),
        "points": []
    }
    
    # 각 점의 정보 저장
    for i, (pos, label) in enumerate(zip(positions, labels)):
        labeling_data["points"].append({
            "index": i,
            "x": int(pos[0]),
            "y": int(pos[1]),
            "label": int(label),
            "status": "valid" if label == 1 else "invalid"
        })
    
    # JSON 파일로 저장
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(labeling_data, f, ensure_ascii=False, indent=2)
    
    print(f"라벨링 데이터 저장: {json_path}")
    return json_path

def load_existing_labels(image_path, output_dir="labeling_data"):
    """기존 라벨링 데이터가 있는지 확인"""
    base_name = os.path.splitext(os.path.basename(image_path))[0]
    json_path = os.path.join(output_dir, f"{base_name}_labels.json")
    
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            print(f"기존 라벨링 데이터 발견: {json_path}")
            return data
        except:
            return None
    return None

def batch_process_images(image_dir, template_path, output_dir="labeling_data", skip_existing=True):
    """폴더의 모든 이미지를 일괄 처리"""
    print("=== 일괄 딥러닝 점 검출 학습 ===")
    print(f"이미지 디렉토리: {image_dir}")
    print(f"템플릿 파일: {template_path}")
    print(f"출력 디렉토리: {output_dir}")
    
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
    
    # 검출기 초기화
    detector = ImprovedDotDetector()
    
    # 전체 통계
    total_images = len(image_paths)
    processed_images = 0
    skipped_images = 0
    all_patches = []
    all_labels = []
    
    print(f"\n=== 일괄 처리 시작 ===")
    
    for img_idx, image_path in enumerate(image_paths):
        print(f"\n--- 이미지 {img_idx + 1}/{total_images}: {os.path.basename(image_path)} ---")
        
        # 기존 라벨링 데이터 확인
        if skip_existing:
            existing_data = load_existing_labels(image_path, output_dir)
            if existing_data:
                print("기존 라벨링 데이터가 있습니다. 건너뜁니다.")
                skipped_images += 1
                continue
        
        try:
            # 단일 이미지 처리
            patches, labels = detector.create_training_data_improved([image_path], template_path)
            
            if patches is None or labels is None:
                print("이미지 처리에 실패했습니다.")
                continue
            
            # 라벨링 데이터 저장
            # 템플릿 매칭으로 점 위치 다시 찾기 (저장용)
            import cv2
            import numpy as np
            
            image = cv2.imread(image_path)
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            template = cv2.imread(template_path, cv2.IMREAD_GRAYSCALE)
            
            if template is not None:
                blurred = cv2.GaussianBlur(gray, (3, 3), 0)
                equalized = cv2.equalizeHist(blurred)
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
                
                # 라벨링 데이터 저장
                save_labeling_data(image_path, positions, labels, output_dir)
            
            # 전체 학습 데이터에 추가
            all_patches.extend(patches)
            all_labels.extend(labels)
            
            processed_images += 1
            print(f"이미지 {img_idx + 1} 완료: {len(patches)}개 패치, {sum(labels)}개 유효 점")
            
        except Exception as e:
            print(f"이미지 처리 중 오류 발생: {e}")
            continue
    
    # 전체 통계 출력
    print(f"\n=== 일괄 처리 완료 ===")
    print(f"총 이미지: {total_images}개")
    print(f"처리된 이미지: {processed_images}개")
    print(f"건너뛴 이미지: {skipped_images}개")
    print(f"총 학습 데이터: {len(all_patches)}개 패치")
    print(f"유효한 점: {sum(all_labels)}개")
    print(f"무효한 점: {len(all_labels) - sum(all_labels)}개")
    
    # 학습 데이터가 있으면 모델 학습
    if all_patches:
        print(f"\n=== 모델 학습 시작 ===")
        detector.train_model(all_patches, all_labels, epochs=50, batch_size=32)
        
        # 모델 저장
        model_path = "batch_dot_detection_model.pth"
        detector.save_model(model_path)
        
        print(f"\n=== 학습 완료! ===")
        print(f"모델이 저장되었습니다: {model_path}")
        print(f"라벨링 데이터가 저장되었습니다: {output_dir}/")
    else:
        print("학습할 데이터가 없습니다.")

def main():
    """메인 함수"""
    # 설정
    image_dir = r"C:\Pycode\camera_test\imgs"
    template_path = "dot_img.png"
    output_dir = "labeling_data"
    
    # 일괄 처리 실행
    batch_process_images(image_dir, template_path, output_dir, skip_existing=True)

if __name__ == "__main__":
    main()
