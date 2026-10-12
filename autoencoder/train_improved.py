"""
개선된 설정으로 학습
"""

import os
import sys
import json
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, random_split
from datetime import datetime

from autoencoder_model import create_model
from dataset import DotPatchDataset
from train import AutoencoderTrainer

def main():
    """개선된 설정으로 학습"""
    
    # 개선된 Configuration
    CONFIG = {
        'label_dir': r'C:\Pycode\camera_test\dot_detection_system\labeling_data',
        'model_type': 'improved',
        'patch_size': 64,          # 32 -> 64 (더 많은 컨텍스트)
        'latent_dim': 256,         # 128 -> 256 (더 큰 표현력)
        'batch_size': 32,          # 64 -> 32 (더 안정적)
        'num_epochs': 200,         # 100 -> 200 (더 긴 학습)
        'learning_rate': 5e-4,     # 1e-3 -> 5e-4 (더 천천히)
        'val_split': 0.2,
        'augment': True,
        'early_stopping_patience': 30,  # 15 -> 30 (더 인내심있게)
        'device': 'cuda' if torch.cuda.is_available() else 'cpu',
        'num_workers': 0,
    }
    
    print("=" * 70)
    print("개선된 Autoencoder 학습")
    print("=" * 70)
    print("\n주요 변경사항:")
    print("  • Patch Size: 32 -> 64")
    print("  • Latent Dim: 128 -> 256")
    print("  • Batch Size: 64 -> 32")
    print("  • Epochs: 100 -> 200")
    print("  • Learning Rate: 1e-3 -> 5e-4")
    print("  • Patience: 15 -> 30")
    print("\n이 설정으로 성능이 크게 향상될 것으로 예상됩니다.")
    print("=" * 70)
    print()
    
    print("Configuration:")
    for key, value in CONFIG.items():
        print(f"  {key}: {value}")
    print()
    
    # Create dataset
    print("Loading dataset...")
    full_dataset = DotPatchDataset(
        label_dir=CONFIG['label_dir'],
        patch_size=CONFIG['patch_size'],
        only_valid=True,
        augment=CONFIG['augment']
    )
    
    # Split
    val_size = int(len(full_dataset) * CONFIG['val_split'])
    train_size = len(full_dataset) - val_size
    train_dataset, val_dataset = random_split(
        full_dataset, 
        [train_size, val_size],
        generator=torch.Generator().manual_seed(42)
    )
    
    print(f"Train dataset size: {len(train_dataset)}")
    print(f"Val dataset size: {len(val_dataset)}")
    
    # Create dataloaders
    train_loader = DataLoader(
        train_dataset,
        batch_size=CONFIG['batch_size'],
        shuffle=True,
        num_workers=CONFIG['num_workers'],
        pin_memory=True if torch.cuda.is_available() else False
    )
    
    val_loader = DataLoader(
        val_dataset,
        batch_size=CONFIG['batch_size'],
        shuffle=False,
        num_workers=CONFIG['num_workers'],
        pin_memory=True if torch.cuda.is_available() else False
    )
    
    # Create model
    print(f"\nCreating {CONFIG['model_type']} model...")
    model = create_model(
        model_type=CONFIG['model_type'],
        patch_size=CONFIG['patch_size'],
        latent_dim=CONFIG['latent_dim']
    )
    
    total_params = sum(p.numel() for p in model.parameters())
    print(f"Total parameters: {total_params:,}")
    
    # Create save directory
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    save_dir = f'./checkpoints/improved_{timestamp}'
    os.makedirs(save_dir, exist_ok=True)
    
    # Save configuration
    with open(os.path.join(save_dir, 'config.json'), 'w') as f:
        json.dump(CONFIG, f, indent=2)
    
    # Create trainer and train
    trainer = AutoencoderTrainer(
        model=model,
        train_loader=train_loader,
        val_loader=val_loader,
        device=CONFIG['device'],
        lr=CONFIG['learning_rate'],
        save_dir=save_dir
    )
    
    trainer.train(
        num_epochs=CONFIG['num_epochs'],
        early_stopping_patience=CONFIG['early_stopping_patience']
    )
    
    print(f"\nModel saved to: {save_dir}")
    print("\n다음 단계:")
    print("  1. 테스트 실행: python run_testing.py")
    print(f"     (checkpoints/best_model.pth를 {save_dir}/best_model.pth로 변경)")
    print("  2. 또는 test.py의 checkpoint_path를 수정")


if __name__ == "__main__":
    main()

