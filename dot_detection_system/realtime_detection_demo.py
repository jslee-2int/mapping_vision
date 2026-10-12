"""
실시간 딥러닝 점 검출 데모

1. pth 파일을 불러들인다
2. 특정 폴더의 이미지를 불러들인다  
3. 각 이미지에 모델을 적용하고 오버레이로 결과를 보여준다
"""

import os
import cv2
import numpy as np
import torch
import glob
from improved_dot_training import ImprovedDotDetector

class RealtimeDetectionDemo:
    """실시간 검출 데모 클래스"""
    
    def __init__(self, model_path, image_dir, template_path="dot_img.png", confidence_threshold=0.5):
        self.model_path = model_path
        self.image_dir = image_dir
        self.template_path = template_path
        self.confidence_threshold = confidence_threshold
        
        # 검출기 초기화
        self.detector = ImprovedDotDetector()
        self.load_model()
        
        # 이미지 파일 목록
        self.image_files = self.get_image_files()
        self.current_index = 0
        
        print(f"초기화 완료:")
        print(f"  모델: {model_path}")
        print(f"  이미지 디렉토리: {image_dir}")
        print(f"  템플릿: {template_path}")
        print(f"  신뢰도 임계값: {confidence_threshold}")
        print(f"  발견된 이미지: {len(self.image_files)}개")
    
    def load_model(self):
        """모델 불러오기"""
        if not os.path.exists(self.model_path):
            print(f"모델 파일이 존재하지 않습니다: {self.model_path}")
            return False
        
        success = self.detector.load_model(self.model_path)
        if success:
            print(f"모델 불러오기 성공: {self.model_path}")
            return True
        else:
            print(f"모델 불러오기 실패")
            return False
    
    def get_image_files(self):
        """이미지 파일 목록 가져오기"""
        image_files = []
        for ext in ['*.png', '*.jpg', '*.jpeg']:
            pattern = os.path.join(self.image_dir, ext)
            image_files.extend(glob.glob(pattern))
        return sorted(image_files)
    
    def detect_dots(self, image):
        """이미지에서 점 검출"""
        # 그레이스케일 변환
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # 템플릿 매칭으로 초기 점 검출
        template = cv2.imread(self.template_path, cv2.IMREAD_GRAYSCALE)
        if template is None:
            print(f"템플릿 파일을 찾을 수 없습니다: {self.template_path}")
            return [], [], []
        
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
        
        if len(positions) == 0:
            return [], [], []
        
        # 딥러닝 모델로 필터링
        predictions, confidences = self.detector.predict(gray, positions)
        
        # 유효한 점만 선택
        valid_positions = []
        for i, (pos, pred, conf) in enumerate(zip(positions, predictions, confidences)):
            if pred == 1 and conf >= self.confidence_threshold:
                valid_positions.append(pos)
        
        return positions, valid_positions, confidences
    
    def create_overlay(self, image, positions, valid_positions, confidences):
        """오버레이 이미지 생성"""
        overlay = image.copy()
        
        # 모든 검출된 점 (빨간색 박스)
        for i, (x, y) in enumerate(positions):
            # 박스 그리기
            cv2.rectangle(overlay, (x-15, y-15), (x+15, y+15), (0, 0, 255), 2)
            
            # 점 번호 표시
            cv2.putText(overlay, str(i), (x-10, y-20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
        
        # 유효한 점 (초록색 박스)
        for i, (x, y) in enumerate(valid_positions):
            # 더 큰 박스로 강조
            cv2.rectangle(overlay, (x-20, y-20), (x+20, y+20), (0, 255, 0), 3)
            cv2.putText(overlay, "VALID", (x-25, y-25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        
        return overlay
    
    def show_current_image(self):
        """현재 이미지 표시"""
        if self.current_index >= len(self.image_files):
            print("모든 이미지를 처리했습니다.")
            return False
        
        image_path = self.image_files[self.current_index]
        filename = os.path.basename(image_path)
        
        print(f"\n--- 이미지 {self.current_index + 1}/{len(self.image_files)}: {filename} ---")
        
        # 이미지 로드
        image = cv2.imread(image_path)
        if image is None:
            print(f"이미지를 불러올 수 없습니다: {image_path}")
            return False
        
        # 점 검출
        positions, valid_positions, confidences = self.detect_dots(image)
        
        print(f"  초기 검출: {len(positions)}개")
        print(f"  필터링 후: {len(valid_positions)}개")
        print(f"  평균 신뢰도: {np.mean(confidences):.3f}" if confidences else "  평균 신뢰도: 0.000")
        
        # 오버레이 생성
        overlay = self.create_overlay(image, positions, valid_positions, confidences)
        
        # 정보 텍스트 추가
        info_text = f"Image: {self.current_index + 1}/{len(self.image_files)} | Initial: {len(positions)} | Valid: {len(valid_positions)}"
        cv2.putText(overlay, info_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        # 키보드 안내
        help_text = "Keys: [N]ext, [P]revious, [Q]uit, [R]eload"
        cv2.putText(overlay, help_text, (10, overlay.shape[0] - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        # 이미지 표시
        window_title = f"Real-time Detection Demo - {filename}"
        cv2.imshow(window_title, overlay)
        
        return True
    
    def run_demo(self):
        """데모 실행"""
        print("\n=== 실시간 딥러닝 점 검출 데모 ===")
        print("키보드 조작:")
        print("  N: 다음 이미지")
        print("  P: 이전 이미지") 
        print("  Q: 종료")
        print("  R: 현재 이미지 다시 로드")
        print("  +/-: 신뢰도 임계값 조정")
        
        if not self.image_files:
            print("이미지 파일이 없습니다.")
            return
        
        # 첫 번째 이미지 표시
        self.show_current_image()
        
        while True:
            key = cv2.waitKey(0) & 0xFF
            
            if key == ord('q') or key == ord('Q'):
                print("데모를 종료합니다.")
                break
            elif key == ord('n') or key == ord('N'):
                self.current_index = (self.current_index + 1) % len(self.image_files)
                self.show_current_image()
            elif key == ord('p') or key == ord('P'):
                self.current_index = (self.current_index - 1) % len(self.image_files)
                self.show_current_image()
            elif key == ord('r') or key == ord('R'):
                self.show_current_image()
            elif key == ord('+') or key == ord('='):
                self.confidence_threshold = min(1.0, self.confidence_threshold + 0.1)
                print(f"신뢰도 임계값: {self.confidence_threshold:.1f}")
                self.show_current_image()
            elif key == ord('-'):
                self.confidence_threshold = max(0.0, self.confidence_threshold - 0.1)
                print(f"신뢰도 임계값: {self.confidence_threshold:.1f}")
                self.show_current_image()
        
        cv2.destroyAllWindows()

def main():
    """메인 함수"""
    # 설정
    model_path = "batch_dot_detection_model.pth"
    image_dir = r"C:\Pycode\camera_test\imgs"
    template_path = "dot_img.png"
    confidence_threshold = 0.5
    
    # 파일 존재 확인
    if not os.path.exists(model_path):
        print(f"모델 파일이 존재하지 않습니다: {model_path}")
        return
    
    if not os.path.exists(image_dir):
        print(f"이미지 디렉토리가 존재하지 않습니다: {image_dir}")
        return
    
    if not os.path.exists(template_path):
        print(f"템플릿 파일이 존재하지 않습니다: {template_path}")
        return
    
    # 데모 실행
    demo = RealtimeDetectionDemo(model_path, image_dir, template_path, confidence_threshold)
    demo.run_demo()

if __name__ == "__main__":
    main()
