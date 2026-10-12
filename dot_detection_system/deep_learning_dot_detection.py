"""
딥러닝 기반 점(Dot) 검출 및 필터링 시스템

사용자가 직접 유효한 점들을 선택하고, 그 데이터를 바탕으로 학습시킨 후
학습된 모델을 사용하여 자동으로 점을 필터링합니다.
"""

import cv2
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import torchvision.transforms as transforms
from sklearn.model_selection import train_test_split
import matplotlib.pyplot as plt
import os
import json
from datetime import datetime

class DotDataset(Dataset):
    """점 검출을 위한 데이터셋"""
    
    def __init__(self, images, labels, transform=None):
        self.images = images
        self.labels = labels
        self.transform = transform
    
    def __len__(self):
        return len(self.images)
    
    def __getitem__(self, idx):
        image = self.images[idx]
        label = self.labels[idx]
        
        if self.transform:
            image = self.transform(image)
        
        return image, label

class DotCNN(nn.Module):
    """점 검출을 위한 CNN 모델"""
    
    def __init__(self, input_size=32, num_classes=2):
        super(DotCNN, self).__init__()
        
        # Convolutional layers
        self.conv1 = nn.Conv2d(1, 32, kernel_size=3, padding=1)
        self.conv2 = nn.Conv2d(32, 64, kernel_size=3, padding=1)
        self.conv3 = nn.Conv2d(64, 128, kernel_size=3, padding=1)
        
        # Pooling
        self.pool = nn.MaxPool2d(2, 2)
        
        # Fully connected layers
        self.fc1 = nn.Linear(128 * (input_size//8) * (input_size//8), 512)
        self.fc2 = nn.Linear(512, 128)
        self.fc3 = nn.Linear(128, num_classes)
        
        # Dropout
        self.dropout = nn.Dropout(0.5)
        
        # Activation
        self.relu = nn.ReLU()
        
    def forward(self, x):
        # Convolutional layers
        x = self.pool(self.relu(self.conv1(x)))
        x = self.pool(self.relu(self.conv2(x)))
        x = self.pool(self.relu(self.conv3(x)))
        
        # Flatten
        x = x.view(x.size(0), -1)
        
        # Fully connected layers
        x = self.dropout(self.relu(self.fc1(x)))
        x = self.dropout(self.relu(self.fc2(x)))
        x = self.fc3(x)
        
        return x

class DeepLearningDotDetector:
    """딥러닝 기반 점 검출기"""
    
    def __init__(self, model_path=None):
        self.model = None
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.transform = transforms.Compose([
            transforms.ToPILImage(),
            transforms.Resize((32, 32)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.5], std=[0.5])
        ])
        
        if model_path and os.path.exists(model_path):
            self.load_model(model_path)
    
    def extract_patches(self, image, positions, patch_size=32):
        """이미지에서 점 주변 패치 추출"""
        patches = []
        h, w = image.shape
        
        for x, y in positions:
            # 패치 영역 계산
            x1 = max(0, x - patch_size // 2)
            y1 = max(0, y - patch_size // 2)
            x2 = min(w, x + patch_size // 2)
            y2 = min(h, y + patch_size // 2)
            
            # 패치 추출
            patch = image[y1:y2, x1:x2]
            
            # 크기 맞추기
            if patch.shape[0] != patch_size or patch.shape[1] != patch_size:
                patch = cv2.resize(patch, (patch_size, patch_size))
            
            patches.append(patch)
        
        return patches
    
    def create_training_data(self, image_paths, template_path, threshold=0.7):
        """학습 데이터 생성 (사용자 인터랙티브) - 여러 이미지 지원"""
        print("=== 학습 데이터 생성 ===")
        print("1. 이미지에서 점들을 자동 검출합니다.")
        print("2. 각 점을 클릭하여 유효한 점(1) 또는 무효한 점(0)으로 분류하세요.")
        print("3. 'q'를 눌러 완료하세요.")
        print("4. 'n'을 눌러 다음 이미지로 넘어가세요.")
        
        all_patches = []
        all_labels = []
        
        for img_idx, image_path in enumerate(image_paths):
            print(f"\n--- 이미지 {img_idx + 1}/{len(image_paths)}: {image_path} ---")
            
            # 이미지 로드
            image = cv2.imread(image_path)
            if image is None:
                print(f"이미지를 불러올 수 없습니다: {image_path}")
                continue
                
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # 템플릿 매칭으로 초기 점 검출
            template = cv2.imread(template_path, cv2.IMREAD_GRAYSCALE)
            if template is None:
                print(f"템플릿 파일을 찾을 수 없습니다: {template_path}")
                continue
            
            # 전처리
            blurred = cv2.GaussianBlur(gray, (3, 3), 0)
            equalized = cv2.equalizeHist(blurred)
            
            # 템플릿 매칭
            result = cv2.matchTemplate(equalized, template, cv2.TM_CCOEFF_NORMED)
            locations = np.where(result >= threshold)
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
            
            print(f"검출된 점 개수: {len(positions)}")
            
            if len(positions) == 0:
                print("검출된 점이 없습니다. 다음 이미지로 넘어갑니다.")
                continue
            
            # 사용자 인터랙티브 라벨링
            labels = []
            display_image = image.copy()
            
            for i, (x, y) in enumerate(positions):
                # 점 표시
                cv2.circle(display_image, (x, y), 10, (0, 255, 0), 1)
                cv2.putText(display_image, str(i), (x-10, y-15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            # 파일 이름을 창 제목에 표시
            filename = os.path.basename(image_path)
            window_title = f'점 분류 - {filename} (클릭: 유효, 우클릭: 무효, q: 완료, n: 다음)'
            cv2.imshow(window_title, display_image)
            
            def mouse_callback(event, x, y, flags, param):
                if event == cv2.EVENT_LBUTTONDOWN:
                    # 가장 가까운 점 찾기
                    distances = [np.sqrt((x - px)**2 + (y - py)**2) for px, py in positions]
                    closest_idx = np.argmin(distances)
                    
                    if distances[closest_idx] < 20:  # 20픽셀 이내
                        labels.append(1)  # 유효한 점
                        cv2.circle(display_image, positions[closest_idx], 8, (0, 255, 0), -1)
                        print(f"점 {closest_idx}: 유효")
                    else:
                        print("점을 클릭해주세요.")
                
                elif event == cv2.EVENT_RBUTTONDOWN:
                    # 가장 가까운 점 찾기
                    distances = [np.sqrt((x - px)**2 + (y - py)**2) for px, py in positions]
                    closest_idx = np.argmin(distances)
                    
                    if distances[closest_idx] < 20:  # 20픽셀 이내
                        labels.append(0)  # 무효한 점
                        cv2.circle(display_image, positions[closest_idx], 8, (0, 0, 255), -1)
                        print(f"점 {closest_idx}: 무효")
                    else:
                        print("점을 우클릭해주세요.")
                
                cv2.imshow(window_title, display_image)
            
            cv2.setMouseCallback(window_title, mouse_callback)
            
            # 모든 점에 대해 라벨링 완료할 때까지 대기
            while len(labels) < len(positions):
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    break
                elif key == ord('n'):
                    print("다음 이미지로 넘어갑니다.")
                    break
            
            cv2.destroyAllWindows()
            
            if len(labels) != len(positions):
                print("모든 점에 대한 라벨링이 완료되지 않았습니다.")
                if key == ord('q'):
                    break
                continue
            
            # 패치 추출
            patches = self.extract_patches(gray, positions)
            
            # 전체 데이터에 추가
            all_patches.extend(patches)
            all_labels.extend(labels)
            
            print(f"이미지 {img_idx + 1} 완료: {len(patches)}개 패치, {sum(labels)}개 유효 점")
            
            # 다음 이미지로 넘어갈지 확인
            if key == ord('n') and img_idx < len(image_paths) - 1:
                continue
            elif key == ord('q'):
                break
        
        if not all_patches:
            print("학습 데이터가 생성되지 않았습니다.")
            return None, None
        
        print(f"\n총 학습 데이터 생성 완료: {len(all_patches)}개 패치, {sum(all_labels)}개 유효 점")
        
        return all_patches, all_labels
    
    def train_model(self, patches, labels, epochs=50, batch_size=32):
        """모델 학습"""
        print("=== 모델 학습 시작 ===")
        
        # 데이터 분할
        X_train, X_test, y_train, y_test = train_test_split(
            patches, labels, test_size=0.2, random_state=42, stratify=labels
        )
        
        # 데이터셋 생성
        train_dataset = DotDataset(X_train, y_train, self.transform)
        test_dataset = DotDataset(X_test, y_test, self.transform)
        
        # 데이터로더 생성
        train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
        test_loader = DataLoader(test_dataset, batch_size=batch_size, shuffle=False)
        
        # 모델 초기화
        self.model = DotCNN().to(self.device)
        criterion = nn.CrossEntropyLoss()
        optimizer = optim.Adam(self.model.parameters(), lr=0.001)
        
        # 학습
        train_losses = []
        test_accuracies = []
        
        for epoch in range(epochs):
            # 학습
            self.model.train()
            train_loss = 0.0
            for batch_idx, (data, target) in enumerate(train_loader):
                data, target = data.to(self.device), target.to(self.device)
                
                optimizer.zero_grad()
                output = self.model(data)
                loss = criterion(output, target)
                loss.backward()
                optimizer.step()
                
                train_loss += loss.item()
            
            # 테스트
            self.model.eval()
            correct = 0
            total = 0
            with torch.no_grad():
                for data, target in test_loader:
                    data, target = data.to(self.device), target.to(self.device)
                    output = self.model(data)
                    _, predicted = torch.max(output.data, 1)
                    total += target.size(0)
                    correct += (predicted == target).sum().item()
            
            accuracy = 100 * correct / total
            avg_loss = train_loss / len(train_loader)
            
            train_losses.append(avg_loss)
            test_accuracies.append(accuracy)
            
            print(f'Epoch {epoch+1}/{epochs}, Loss: {avg_loss:.4f}, Accuracy: {accuracy:.2f}%')
        
        print(f"학습 완료! 최종 정확도: {test_accuracies[-1]:.2f}%")
        
        return train_losses, test_accuracies
    
    def save_model(self, model_path):
        """모델 저장"""
        if self.model is None:
            print("저장할 모델이 없습니다.")
            return
        
        torch.save({
            'model_state_dict': self.model.state_dict(),
            'model_class': 'DotCNN',
            'input_size': 32,
            'num_classes': 2
        }, model_path)
        print(f"모델 저장 완료: {model_path}")
    
    def load_model(self, model_path):
        """모델 불러오기"""
        try:
            checkpoint = torch.load(model_path, map_location=self.device)
            self.model = DotCNN(
                input_size=checkpoint['input_size'],
                num_classes=checkpoint['num_classes']
            ).to(self.device)
            self.model.load_state_dict(checkpoint['model_state_dict'])
            self.model.eval()
            print(f"모델 불러오기 완료: {model_path}")
            return True
        except Exception as e:
            print(f"모델 불러오기 실패: {e}")
            return False
    
    def predict(self, image, positions):
        """점 분류 예측"""
        if self.model is None:
            print("모델이 로드되지 않았습니다.")
            return None
        
        # 패치 추출
        patches = self.extract_patches(image, positions)
        
        # 예측
        self.model.eval()
        predictions = []
        confidences = []
        
        with torch.no_grad():
            for patch in patches:
                # 전처리
                patch_tensor = self.transform(patch).unsqueeze(0).to(self.device)
                
                # 예측
                output = self.model(patch_tensor)
                probabilities = torch.softmax(output, dim=1)
                confidence, predicted = torch.max(probabilities, 1)
                
                predictions.append(predicted.item())
                confidences.append(confidence.item())
        
        return predictions, confidences
    
    def filter_dots(self, image_path, template_path, threshold=0.7, confidence_threshold=0.8):
        """딥러닝 모델을 사용한 점 필터링"""
        if self.model is None:
            print("모델이 로드되지 않았습니다. 먼저 모델을 학습시키거나 불러오세요.")
            return None
        
        print("=== 딥러닝 기반 점 필터링 ===")
        
        # 이미지 로드
        image = cv2.imread(image_path)
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
        locations = np.where(result >= threshold)
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
        
        print(f"초기 검출된 점 개수: {len(positions)}")
        
        # 딥러닝 모델로 필터링
        predictions, confidences = self.predict(gray, positions)
        
        # 유효한 점만 선택
        valid_positions = []
        for i, (pos, pred, conf) in enumerate(zip(positions, predictions, confidences)):
            if pred == 1 and conf >= confidence_threshold:
                valid_positions.append(pos)
        
        print(f"딥러닝 필터링 후: {len(valid_positions)}개 점")
        
        # 결과 시각화
        result_image = image.copy()
        
        # 모든 점 (빨간색)
        for x, y in positions:
            cv2.drawMarker(result_image, (x, y), (0, 0, 255), cv2.MARKER_CROSS, 10, 1)
        
        # 유효한 점 (녹색)
        for x, y in valid_positions:
            cv2.drawMarker(result_image, (x, y), (0, 255, 0), cv2.MARKER_DIAMOND, 12, 2)
        
        # 결과 저장
        output_path = image_path.replace('.', '_dl_filtered.')
        cv2.imwrite(output_path, result_image)
        print(f"결과 이미지 저장: {output_path}")
        
        # 이미지 표시
        cv2.imshow('딥러닝 필터링 결과', result_image)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
        
        return valid_positions

def main():
    """메인 함수"""
    print("=== 딥러닝 기반 점 검출 시스템 ===")
    
    # 설정
    image_path = r"C:\Pycode\camera_test\imgs\25-10-14_1.png"
    template_path = "dot_img.png"
    model_path = "dot_detection_model.pth"
    
    # 검출기 초기화
    detector = DeepLearningDotDetector()
    
    # 모델이 존재하는지 확인
    if os.path.exists(model_path):
        print("기존 모델을 불러옵니다...")
        detector.load_model(model_path)
    else:
        print("새로운 모델을 학습시킵니다...")
        
        # 학습 데이터 생성 (단일 이미지 리스트로 변환)
        patches, labels = detector.create_training_data([image_path], template_path)
        
        if patches is None or labels is None:
            print("학습 데이터 생성에 실패했습니다.")
            return
        
        # 모델 학습
        detector.train_model(patches, labels)
        
        # 모델 저장
        detector.save_model(model_path)
    
    # 딥러닝 필터링 실행
    valid_positions = detector.filter_dots(image_path, template_path)
    
    if valid_positions:
        print(f"최종 유효한 점 개수: {len(valid_positions)}")
        print("딥러닝 필터링 완료!")
    else:
        print("필터링에 실패했습니다.")

if __name__ == "__main__":
    main()
