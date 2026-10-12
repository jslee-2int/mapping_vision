"""
Autoencoder 학습 코드
Valid 점들로만 학습하여 Invalid 점을 탐지하는 Anomaly Detection 방식
"""

import os
import sys
import json
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, random_split
import numpy as np
import matplotlib.pyplot as plt
from tqdm import tqdm
from datetime import datetime

from autoencoder_model import create_model
from dataset import DotPatchDataset


class AutoencoderTrainer:
    """Autoencoder 학습 클래스"""
    
    def __init__(self,
                 model,
                 train_loader,
                 val_loader,
                 device='cuda',
                 lr=1e-3,
                 save_dir='./checkpoints'):
        """
        Args:
            model: Autoencoder 모델
            train_loader: 학습 데이터로더
            val_loader: 검증 데이터로더
            device: 학습 디바이스
            lr: learning rate
            save_dir: 체크포인트 저장 디렉토리
        """
        self.model = model.to(device)
        self.train_loader = train_loader
        self.val_loader = val_loader
        self.device = device
        self.save_dir = save_dir
        
        # Loss and optimizer
        self.criterion = nn.MSELoss()
        self.optimizer = optim.Adam(model.parameters(), lr=lr)
        self.scheduler = optim.lr_scheduler.ReduceLROnPlateau(
            self.optimizer, 
            mode='min', 
            factor=0.5, 
            patience=5
        )
        
        # Training history
        self.train_losses = []
        self.val_losses = []
        self.best_val_loss = float('inf')
        
        # Create save directory
        os.makedirs(save_dir, exist_ok=True)
        
    def train_epoch(self):
        """한 에폭 학습"""
        self.model.train()
        total_loss = 0
        
        pbar = tqdm(self.train_loader, desc='Training')
        for batch_idx, (patches, labels) in enumerate(pbar):
            patches = patches.to(self.device)
            
            # Forward pass
            reconstruction, latent = self.model(patches)
            loss = self.criterion(reconstruction, patches)
            
            # Backward pass
            self.optimizer.zero_grad()
            loss.backward()
            self.optimizer.step()
            
            total_loss += loss.item()
            pbar.set_postfix({'loss': f'{loss.item():.6f}'})
        
        avg_loss = total_loss / len(self.train_loader)
        return avg_loss
    
    def validate(self):
        """검증"""
        self.model.eval()
        total_loss = 0
        
        with torch.no_grad():
            for patches, labels in self.val_loader:
                patches = patches.to(self.device)
                
                reconstruction, latent = self.model(patches)
                loss = self.criterion(reconstruction, patches)
                
                total_loss += loss.item()
        
        avg_loss = total_loss / len(self.val_loader)
        return avg_loss
    
    def train(self, num_epochs=100, early_stopping_patience=15):
        """
        전체 학습 루프
        
        Args:
            num_epochs: 학습 에폭 수
            early_stopping_patience: Early stopping patience
        """
        print(f"Starting training for {num_epochs} epochs...")
        print(f"Device: {self.device}")
        print(f"Train batches: {len(self.train_loader)}")
        print(f"Val batches: {len(self.val_loader)}")
        
        patience_counter = 0
        
        for epoch in range(1, num_epochs + 1):
            print(f"\nEpoch {epoch}/{num_epochs}")
            
            # Train
            train_loss = self.train_epoch()
            self.train_losses.append(train_loss)
            
            # Validate
            val_loss = self.validate()
            self.val_losses.append(val_loss)
            
            # Learning rate scheduling
            old_lr = self.optimizer.param_groups[0]['lr']
            self.scheduler.step(val_loss)
            new_lr = self.optimizer.param_groups[0]['lr']
            
            # Print results
            print(f"Train Loss: {train_loss:.6f} | Val Loss: {val_loss:.6f}")
            if old_lr != new_lr:
                print(f"Learning rate reduced: {old_lr:.6f} -> {new_lr:.6f}")
            
            # Save best model
            if val_loss < self.best_val_loss:
                self.best_val_loss = val_loss
                self.save_checkpoint(epoch, is_best=True)
                print(f"Best model saved! (Val Loss: {val_loss:.6f})")
                patience_counter = 0
            else:
                patience_counter += 1
            
            # Save regular checkpoint every 10 epochs
            if epoch % 10 == 0:
                self.save_checkpoint(epoch, is_best=False)
            
            # Early stopping
            if patience_counter >= early_stopping_patience:
                print(f"\nEarly stopping triggered after {epoch} epochs")
                break
        
        # Save final checkpoint
        self.save_checkpoint(epoch, is_best=False, name='final')
        
        # Plot training history
        self.plot_history()
        
        print("\nTraining completed!")
        print(f"Best validation loss: {self.best_val_loss:.6f}")
    
    def save_checkpoint(self, epoch, is_best=False, name=None):
        """체크포인트 저장"""
        checkpoint = {
            'epoch': epoch,
            'model_state_dict': self.model.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
            'scheduler_state_dict': self.scheduler.state_dict(),
            'train_losses': self.train_losses,
            'val_losses': self.val_losses,
            'best_val_loss': self.best_val_loss,
        }
        
        if is_best:
            path = os.path.join(self.save_dir, 'best_model.pth')
        elif name:
            path = os.path.join(self.save_dir, f'{name}_model.pth')
        else:
            path = os.path.join(self.save_dir, f'checkpoint_epoch_{epoch}.pth')
        
        torch.save(checkpoint, path)
    
    def plot_history(self):
        """학습 히스토리 시각화"""
        plt.figure(figsize=(10, 5))
        plt.plot(self.train_losses, label='Train Loss')
        plt.plot(self.val_losses, label='Val Loss')
        plt.xlabel('Epoch')
        plt.ylabel('Loss')
        plt.title('Training History')
        plt.legend()
        plt.grid(True)
        plt.savefig(os.path.join(self.save_dir, 'training_history.png'))
        plt.close()
        
        # Save loss history as JSON
        history = {
            'train_losses': self.train_losses,
            'val_losses': self.val_losses,
            'best_val_loss': self.best_val_loss
        }
        with open(os.path.join(self.save_dir, 'training_history.json'), 'w') as f:
            json.dump(history, f, indent=2)


def main():
    """메인 학습 함수"""
    # Configuration - IMPROVED SETTINGS FOR BETTER PERFORMANCE
    CONFIG = {
        'label_dir': r'C:\Pycode\camera_test\dot_detection_system\labeling_data',
        'model_type': 'improved',  # 'basic' or 'improved'
        'patch_size': 64,          # 32 -> 64: More context
        'latent_dim': 256,         # 128 -> 256: Larger representation
        'batch_size': 32,          # 64 -> 32: More stable training
        'num_epochs': 200,         # 100 -> 200: Longer training
        'learning_rate': 5e-4,     # 1e-3 -> 5e-4: Slower, more stable
        'val_split': 0.2,
        'augment': True,
        'early_stopping_patience': 30,  # 15 -> 30: More patience
        'device': 'cuda' if torch.cuda.is_available() else 'cpu',
        'num_workers': 0,
    }
    
    print("=" * 60)
    print("Autoencoder Training for Dot Filtering")
    print("=" * 60)
    print("\nConfiguration:")
    for key, value in CONFIG.items():
        print(f"  {key}: {value}")
    print()
    
    # Create dataset
    print("Loading dataset...")
    full_dataset = DotPatchDataset(
        label_dir=CONFIG['label_dir'],
        patch_size=CONFIG['patch_size'],
        only_valid=True,  # Only use valid points for training
        augment=CONFIG['augment']
    )
    
    # Split into train and validation
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
    save_dir = f'./checkpoints/{CONFIG["model_type"]}_{timestamp}'
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


if __name__ == "__main__":
    main()

