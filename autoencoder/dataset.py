"""
데이터셋 로더
라벨링 데이터에서 이미지 패치를 추출하여 학습 데이터 생성
"""

import os
import json
import numpy as np
from PIL import Image
import torch
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms
import cv2


class DotPatchDataset(Dataset):
    """
    점(dot) 주변의 이미지 패치를 추출하는 데이터셋
    """
    
    def __init__(self, 
                 label_dir,
                 patch_size=32,
                 only_valid=True,
                 transform=None,
                 augment=False):
        """
        Args:
            label_dir: 라벨링 JSON 파일이 있는 디렉토리
            patch_size: 추출할 패치의 크기
            only_valid: True면 valid 점만, False면 모든 점 사용
            transform: 커스텀 transform
            augment: 데이터 증강 사용 여부
        """
        self.label_dir = label_dir
        self.patch_size = patch_size
        self.only_valid = only_valid
        self.augment = augment
        
        # Load all labeling data
        self.data = []
        self._load_all_labels()
        
        # Setup transforms
        if transform is not None:
            self.transform = transform
        elif augment:
            self.transform = transforms.Compose([
                transforms.ToPILImage(),
                transforms.RandomHorizontalFlip(p=0.5),
                transforms.RandomVerticalFlip(p=0.5),
                transforms.RandomRotation(degrees=15),
                transforms.ColorJitter(brightness=0.2, contrast=0.2),
                transforms.ToTensor(),
            ])
        else:
            self.transform = transforms.Compose([
                transforms.ToPILImage(),
                transforms.ToTensor(),
            ])
    
    def _load_all_labels(self):
        """모든 라벨링 파일을 로드"""
        label_files = [f for f in os.listdir(self.label_dir) if f.endswith('_labels.json')]
        
        for label_file in label_files:
            label_path = os.path.join(self.label_dir, label_file)
            
            with open(label_path, 'r', encoding='utf-8') as f:
                label_data = json.load(f)
            
            image_path = label_data['image_path']
            
            # 이미지 파일이 존재하는지 확인
            if not os.path.exists(image_path):
                print(f"Warning: Image not found: {image_path}")
                continue
            
            # 이미지 로드
            image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
            if image is None:
                print(f"Warning: Failed to load image: {image_path}")
                continue
            
            # 각 점에 대해 패치 추출
            for point in label_data['points']:
                label = point['label']
                
                # only_valid가 True면 valid 점만 사용
                if self.only_valid and label == 0:
                    continue
                
                x, y = point['x'], point['y']
                
                # 패치를 추출할 수 있는지 확인
                half_patch = self.patch_size // 2
                if (x - half_patch < 0 or x + half_patch > image.shape[1] or
                    y - half_patch < 0 or y + half_patch > image.shape[0]):
                    continue
                
                # 데이터 저장
                self.data.append({
                    'image': image,
                    'x': x,
                    'y': y,
                    'label': label,
                    'image_path': image_path
                })
        
        print(f"Loaded {len(self.data)} patches from {len(label_files)} images")
        if self.only_valid:
            print(f"(Only valid points)")
    
    def __len__(self):
        return len(self.data)
    
    def __getitem__(self, idx):
        """
        패치를 추출하여 반환
        
        Returns:
            patch: (1, patch_size, patch_size) 텐서
            label: 0 (invalid) 또는 1 (valid)
        """
        item = self.data[idx]
        image = item['image']
        x, y = item['x'], item['y']
        label = item['label']
        
        # 패치 추출
        half_patch = self.patch_size // 2
        patch = image[y - half_patch:y + half_patch,
                     x - half_patch:x + half_patch]
        
        # 패치가 정확한 크기인지 확인
        if patch.shape != (self.patch_size, self.patch_size):
            # 패딩으로 크기 맞추기
            patch = cv2.copyMakeBorder(
                patch,
                0, self.patch_size - patch.shape[0],
                0, self.patch_size - patch.shape[1],
                cv2.BORDER_REPLICATE
            )
        
        # 정규화 (0-255 -> 0-1)
        patch = patch.astype(np.float32) / 255.0
        
        # Transform 적용
        patch = self.transform(patch)
        
        return patch, label


class DotPatchTestDataset(Dataset):
    """
    테스트용 데이터셋 - valid와 invalid 점을 모두 포함
    """
    
    def __init__(self, label_dir, patch_size=32, transform=None):
        """
        Args:
            label_dir: 라벨링 JSON 파일이 있는 디렉토리
            patch_size: 추출할 패치의 크기
            transform: 커스텀 transform
        """
        self.label_dir = label_dir
        self.patch_size = patch_size
        
        # Load all data (both valid and invalid)
        self.data = []
        self._load_all_labels()
        
        # Setup transforms
        if transform is not None:
            self.transform = transform
        else:
            self.transform = transforms.Compose([
                transforms.ToPILImage(),
                transforms.ToTensor(),
            ])
    
    def _load_all_labels(self):
        """모든 라벨링 파일을 로드"""
        label_files = [f for f in os.listdir(self.label_dir) if f.endswith('_labels.json')]
        
        valid_count = 0
        invalid_count = 0
        
        for label_file in label_files:
            label_path = os.path.join(self.label_dir, label_file)
            
            with open(label_path, 'r', encoding='utf-8') as f:
                label_data = json.load(f)
            
            image_path = label_data['image_path']
            
            if not os.path.exists(image_path):
                print(f"Warning: Image not found: {image_path}")
                continue
            
            image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
            if image is None:
                print(f"Warning: Failed to load image: {image_path}")
                continue
            
            for point in label_data['points']:
                label = point['label']
                x, y = point['x'], point['y']
                
                # 패치를 추출할 수 있는지 확인
                half_patch = self.patch_size // 2
                if (x - half_patch < 0 or x + half_patch > image.shape[1] or
                    y - half_patch < 0 or y + half_patch > image.shape[0]):
                    continue
                
                self.data.append({
                    'image': image,
                    'x': x,
                    'y': y,
                    'label': label,
                    'image_path': image_path,
                    'point_index': point['index']
                })
                
                if label == 1:
                    valid_count += 1
                else:
                    invalid_count += 1
        
        print(f"Loaded {len(self.data)} patches from {len(label_files)} images")
        print(f"Valid: {valid_count}, Invalid: {invalid_count}")
    
    def __len__(self):
        return len(self.data)
    
    def __getitem__(self, idx):
        """패치를 추출하여 반환"""
        item = self.data[idx]
        image = item['image']
        x, y = item['x'], item['y']
        label = item['label']
        
        # 패치 추출
        half_patch = self.patch_size // 2
        patch = image[y - half_patch:y + half_patch,
                     x - half_patch:x + half_patch]
        
        # 패치 크기 확인 및 패딩
        if patch.shape != (self.patch_size, self.patch_size):
            patch = cv2.copyMakeBorder(
                patch,
                0, self.patch_size - patch.shape[0],
                0, self.patch_size - patch.shape[1],
                cv2.BORDER_REPLICATE
            )
        
        # 정규화
        patch = patch.astype(np.float32) / 255.0
        
        # Transform 적용
        patch = self.transform(patch)
        
        return patch, label, item['image_path'], item['point_index']


def create_dataloader(label_dir, 
                      batch_size=32,
                      patch_size=32,
                      only_valid=True,
                      augment=False,
                      shuffle=True,
                      num_workers=0):
    """
    데이터로더 생성 헬퍼 함수
    
    Args:
        label_dir: 라벨링 JSON 파일이 있는 디렉토리
        batch_size: 배치 크기
        patch_size: 패치 크기
        only_valid: valid 점만 사용할지 여부
        augment: 데이터 증강 사용 여부
        shuffle: 셔플 여부
        num_workers: 워커 수
    
    Returns:
        DataLoader 인스턴스
    """
    dataset = DotPatchDataset(
        label_dir=label_dir,
        patch_size=patch_size,
        only_valid=only_valid,
        augment=augment
    )
    
    dataloader = DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=shuffle,
        num_workers=num_workers,
        pin_memory=True if torch.cuda.is_available() else False
    )
    
    return dataloader


def create_test_dataloader(label_dir,
                          batch_size=32,
                          patch_size=32,
                          num_workers=0):
    """
    테스트용 데이터로더 생성
    
    Returns:
        DataLoader 인스턴스
    """
    dataset = DotPatchTestDataset(
        label_dir=label_dir,
        patch_size=patch_size
    )
    
    dataloader = DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
        pin_memory=True if torch.cuda.is_available() else False
    )
    
    return dataloader


if __name__ == "__main__":
    # 데이터셋 테스트
    import sys
    sys.path.append('..')
    
    label_dir = r"C:\Pycode\camera_test\dot_detection_system\labeling_data"
    
    print("Testing DotPatchDataset (only valid)...")
    dataset = DotPatchDataset(label_dir, patch_size=32, only_valid=True)
    print(f"Dataset size: {len(dataset)}")
    
    if len(dataset) > 0:
        patch, label = dataset[0]
        print(f"Patch shape: {patch.shape}")
        print(f"Patch value range: [{patch.min():.3f}, {patch.max():.3f}]")
        print(f"Label: {label}")
    
    print("\nTesting DotPatchTestDataset (all points)...")
    test_dataset = DotPatchTestDataset(label_dir, patch_size=32)
    print(f"Test dataset size: {len(test_dataset)}")
    
    if len(test_dataset) > 0:
        patch, label, img_path, point_idx = test_dataset[0]
        print(f"Patch shape: {patch.shape}")
        print(f"Label: {label}")
        print(f"Image path: {img_path}")
        print(f"Point index: {point_idx}")
    
    print("\nTesting DataLoader...")
    dataloader = create_dataloader(label_dir, batch_size=4, only_valid=True)
    for batch_idx, (patches, labels) in enumerate(dataloader):
        print(f"Batch {batch_idx}: patches shape = {patches.shape}, labels shape = {labels.shape}")
        if batch_idx >= 2:
            break

