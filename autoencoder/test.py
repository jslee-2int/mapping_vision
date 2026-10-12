"""
Autoencoder 테스트 및 평가 코드
학습된 모델을 사용하여 valid/invalid 점 분류 성능 평가
"""

import os
import sys
import json
import torch
import numpy as np
import matplotlib.pyplot as plt
from sklearn.metrics import (
    classification_report, 
    confusion_matrix, 
    roc_curve, 
    auc,
    precision_recall_curve,
    average_precision_score
)
import seaborn as sns
from tqdm import tqdm

from autoencoder_model import create_model
from dataset import create_test_dataloader


class AutoencoderTester:
    """Autoencoder 테스트 클래스"""
    
    def __init__(self, model, checkpoint_path, device='cuda'):
        """
        Args:
            model: Autoencoder 모델
            checkpoint_path: 체크포인트 파일 경로
            device: 디바이스
        """
        self.model = model.to(device)
        self.device = device
        self.checkpoint_path = checkpoint_path
        
        # Load checkpoint
        self.load_checkpoint(checkpoint_path)
        self.model.eval()
        
    def load_checkpoint(self, checkpoint_path):
        """체크포인트 로드"""
        print(f"Loading checkpoint from {checkpoint_path}")
        checkpoint = torch.load(checkpoint_path, map_location=self.device)
        self.model.load_state_dict(checkpoint['model_state_dict'])
        print(f"Loaded model from epoch {checkpoint['epoch']}")
        print(f"Best validation loss: {checkpoint['best_val_loss']:.6f}")
    
    def compute_reconstruction_errors(self, dataloader):
        """
        모든 샘플에 대해 reconstruction error 계산
        
        Returns:
            errors: reconstruction error 리스트
            labels: ground truth label 리스트
            image_paths: 이미지 경로 리스트
            point_indices: 점 인덱스 리스트
        """
        errors = []
        labels = []
        image_paths = []
        point_indices = []
        
        print("Computing reconstruction errors...")
        with torch.no_grad():
            for patches, batch_labels, batch_paths, batch_indices in tqdm(dataloader):
                patches = patches.to(self.device)
                
                # Compute reconstruction
                reconstruction, _ = self.model(patches)
                
                # Compute MSE for each sample
                batch_errors = torch.mean(
                    (reconstruction - patches) ** 2,
                    dim=[1, 2, 3]
                ).cpu().numpy()
                
                errors.extend(batch_errors.tolist())
                labels.extend(batch_labels.numpy().tolist())
                image_paths.extend(batch_paths)
                point_indices.extend(batch_indices.numpy().tolist())
        
        return np.array(errors), np.array(labels), image_paths, point_indices
    
    def find_optimal_threshold(self, errors, labels, method='f1'):
        """
        최적의 threshold 찾기
        
        Args:
            errors: reconstruction errors
            labels: ground truth labels (0: invalid, 1: valid)
            method: 'f1', 'youden', 'precision_recall'
        
        Returns:
            optimal_threshold
        """
        # Label 1 (valid)는 낮은 error, Label 0 (invalid)는 높은 error를 가져야 함
        # 따라서 error가 threshold보다 크면 invalid (0), 작으면 valid (1)로 예측
        
        if method == 'f1':
            # F1 score를 최대화하는 threshold 찾기
            best_threshold = 0
            best_f1 = 0
            
            thresholds = np.linspace(errors.min(), errors.max(), 100)
            for threshold in thresholds:
                predictions = (errors < threshold).astype(int)
                
                tp = np.sum((predictions == 1) & (labels == 1))
                fp = np.sum((predictions == 1) & (labels == 0))
                fn = np.sum((predictions == 0) & (labels == 1))
                
                precision = tp / (tp + fp) if (tp + fp) > 0 else 0
                recall = tp / (tp + fn) if (tp + fn) > 0 else 0
                f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
                
                if f1 > best_f1:
                    best_f1 = f1
                    best_threshold = threshold
            
            print(f"Optimal threshold (F1): {best_threshold:.6f} (F1: {best_f1:.4f})")
            return best_threshold
        
        elif method == 'youden':
            # Youden's J statistic을 최대화
            fpr, tpr, thresholds = roc_curve(labels, -errors)  # -errors because lower error = valid
            j_scores = tpr - fpr
            optimal_idx = np.argmax(j_scores)
            optimal_threshold = -thresholds[optimal_idx]
            
            print(f"Optimal threshold (Youden): {optimal_threshold:.6f}")
            return optimal_threshold
        
        else:
            raise ValueError(f"Unknown method: {method}")
    
    def evaluate(self, dataloader, threshold=None, threshold_method='f1', save_dir='./test_results'):
        """
        모델 평가
        
        Args:
            dataloader: 테스트 데이터로더
            threshold: reconstruction error threshold (None이면 자동 계산)
            threshold_method: threshold 계산 방법
            save_dir: 결과 저장 디렉토리
        """
        os.makedirs(save_dir, exist_ok=True)
        
        # Compute reconstruction errors
        errors, labels, image_paths, point_indices = self.compute_reconstruction_errors(dataloader)
        
        # Find optimal threshold if not provided
        if threshold is None:
            threshold = self.find_optimal_threshold(errors, labels, method=threshold_method)
        else:
            print(f"Using provided threshold: {threshold:.6f}")
        
        # Make predictions
        # error < threshold -> valid (1), error >= threshold -> invalid (0)
        predictions = (errors < threshold).astype(int)
        
        # Print statistics
        print("\n" + "=" * 60)
        print("Evaluation Results")
        print("=" * 60)
        print(f"\nThreshold: {threshold:.6f}")
        print(f"Valid samples (label=1): {np.sum(labels == 1)}")
        print(f"Invalid samples (label=0): {np.sum(labels == 0)}")
        print(f"Mean error for valid: {errors[labels == 1].mean():.6f}")
        print(f"Mean error for invalid: {errors[labels == 0].mean():.6f}")
        print(f"Std error for valid: {errors[labels == 1].std():.6f}")
        print(f"Std error for invalid: {errors[labels == 0].std():.6f}")
        
        # Classification report
        print("\nClassification Report:")
        print(classification_report(
            labels, 
            predictions,
            target_names=['Invalid', 'Valid'],
            digits=4
        ))
        
        # Confusion matrix
        cm = confusion_matrix(labels, predictions)
        print("\nConfusion Matrix:")
        print("                Predicted")
        print("              Invalid  Valid")
        print(f"Actual Invalid  {cm[0, 0]:6d}  {cm[0, 1]:5d}")
        print(f"       Valid    {cm[1, 0]:6d}  {cm[1, 1]:5d}")
        
        # Plot confusion matrix
        self.plot_confusion_matrix(cm, save_dir)
        
        # Plot ROC curve
        self.plot_roc_curve(labels, errors, save_dir)
        
        # Plot error distribution
        self.plot_error_distribution(errors, labels, threshold, save_dir)
        
        # Plot precision-recall curve
        self.plot_precision_recall_curve(labels, errors, save_dir)
        
        # Visualize some examples
        self.visualize_examples(dataloader, errors, labels, predictions, threshold, save_dir)
        
        # Save detailed results
        self.save_detailed_results(
            errors, labels, predictions, 
            image_paths, point_indices, 
            threshold, save_dir
        )
        
        print(f"\nResults saved to: {save_dir}")
        
        return threshold, predictions, errors
    
    def plot_confusion_matrix(self, cm, save_dir):
        """Confusion matrix 시각화"""
        plt.figure(figsize=(8, 6))
        sns.heatmap(
            cm, 
            annot=True, 
            fmt='d', 
            cmap='Blues',
            xticklabels=['Invalid', 'Valid'],
            yticklabels=['Invalid', 'Valid']
        )
        plt.title('Confusion Matrix')
        plt.ylabel('Actual')
        plt.xlabel('Predicted')
        plt.tight_layout()
        plt.savefig(os.path.join(save_dir, 'confusion_matrix.png'), dpi=150)
        plt.close()
    
    def plot_roc_curve(self, labels, errors, save_dir):
        """ROC curve 시각화"""
        # Lower error = valid이므로 -errors를 사용
        fpr, tpr, thresholds = roc_curve(labels, -errors)
        roc_auc = auc(fpr, tpr)
        
        plt.figure(figsize=(8, 6))
        plt.plot(fpr, tpr, color='darkorange', lw=2, label=f'ROC curve (AUC = {roc_auc:.4f})')
        plt.plot([0, 1], [0, 1], color='navy', lw=2, linestyle='--', label='Random')
        plt.xlim([0.0, 1.0])
        plt.ylim([0.0, 1.05])
        plt.xlabel('False Positive Rate')
        plt.ylabel('True Positive Rate')
        plt.title('Receiver Operating Characteristic (ROC) Curve')
        plt.legend(loc="lower right")
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(os.path.join(save_dir, 'roc_curve.png'), dpi=150)
        plt.close()
    
    def plot_error_distribution(self, errors, labels, threshold, save_dir):
        """Error distribution 시각화"""
        plt.figure(figsize=(12, 5))
        
        # Histogram
        plt.subplot(1, 2, 1)
        plt.hist(errors[labels == 1], bins=50, alpha=0.7, label='Valid', color='green')
        plt.hist(errors[labels == 0], bins=50, alpha=0.7, label='Invalid', color='red')
        plt.axvline(threshold, color='black', linestyle='--', linewidth=2, label=f'Threshold: {threshold:.4f}')
        plt.xlabel('Reconstruction Error')
        plt.ylabel('Count')
        plt.title('Error Distribution')
        plt.legend()
        plt.grid(True, alpha=0.3)
        
        # Box plot
        plt.subplot(1, 2, 2)
        data_to_plot = [errors[labels == 1], errors[labels == 0]]
        plt.boxplot(data_to_plot, labels=['Valid', 'Invalid'])
        plt.axhline(threshold, color='red', linestyle='--', linewidth=2, label=f'Threshold: {threshold:.4f}')
        plt.ylabel('Reconstruction Error')
        plt.title('Error Distribution (Box Plot)')
        plt.legend()
        plt.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(os.path.join(save_dir, 'error_distribution.png'), dpi=150)
        plt.close()
    
    def plot_precision_recall_curve(self, labels, errors, save_dir):
        """Precision-Recall curve 시각화"""
        # Lower error = valid이므로 -errors를 사용
        precision, recall, thresholds = precision_recall_curve(labels, -errors)
        avg_precision = average_precision_score(labels, -errors)
        
        plt.figure(figsize=(8, 6))
        plt.plot(recall, precision, color='blue', lw=2, label=f'PR curve (AP = {avg_precision:.4f})')
        plt.xlim([0.0, 1.0])
        plt.ylim([0.0, 1.05])
        plt.xlabel('Recall')
        plt.ylabel('Precision')
        plt.title('Precision-Recall Curve')
        plt.legend(loc="lower left")
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(os.path.join(save_dir, 'precision_recall_curve.png'), dpi=150)
        plt.close()
    
    def visualize_examples(self, dataloader, errors, labels, predictions, threshold, save_dir, num_examples=20):
        """샘플 예시 시각화"""
        # Get some patches
        patches_list = []
        indices = np.random.choice(len(errors), min(num_examples, len(errors)), replace=False)
        
        dataset = dataloader.dataset
        for idx in indices:
            patch, label, _, _ = dataset[idx]
            patches_list.append({
                'patch': patch.numpy()[0],  # Remove channel dimension
                'label': label,
                'prediction': predictions[idx],
                'error': errors[idx],
            })
        
        # Plot
        fig, axes = plt.subplots(4, 5, figsize=(15, 12))
        axes = axes.flatten()
        
        for i, (ax, sample) in enumerate(zip(axes, patches_list)):
            if i >= num_examples:
                break
            
            ax.imshow(sample['patch'], cmap='gray')
            
            # Color border based on correctness
            color = 'green' if sample['label'] == sample['prediction'] else 'red'
            for spine in ax.spines.values():
                spine.set_edgecolor(color)
                spine.set_linewidth(3)
            
            title = f"GT: {'V' if sample['label'] == 1 else 'I'} | "
            title += f"Pred: {'V' if sample['prediction'] == 1 else 'I'}\n"
            title += f"Error: {sample['error']:.4f}"
            ax.set_title(title, fontsize=8)
            ax.axis('off')
        
        # Hide unused subplots
        for i in range(len(patches_list), len(axes)):
            axes[i].axis('off')
        
        plt.suptitle(f'Sample Predictions (Green=Correct, Red=Wrong)\nThreshold: {threshold:.4f}')
        plt.tight_layout()
        plt.savefig(os.path.join(save_dir, 'sample_predictions.png'), dpi=150)
        plt.close()
    
    def save_detailed_results(self, errors, labels, predictions, image_paths, point_indices, threshold, save_dir):
        """상세 결과 저장"""
        results = {
            'threshold': float(threshold),
            'total_samples': len(errors),
            'valid_samples': int(np.sum(labels == 1)),
            'invalid_samples': int(np.sum(labels == 0)),
            'correct_predictions': int(np.sum(labels == predictions)),
            'accuracy': float(np.mean(labels == predictions)),
            'samples': []
        }
        
        # Save per-sample results
        for i in range(len(errors)):
            results['samples'].append({
                'image_path': image_paths[i],
                'point_index': int(point_indices[i]),
                'ground_truth': int(labels[i]),
                'prediction': int(predictions[i]),
                'reconstruction_error': float(errors[i]),
                'correct': bool(labels[i] == predictions[i])
            })
        
        # Save to JSON
        with open(os.path.join(save_dir, 'detailed_results.json'), 'w') as f:
            json.dump(results, f, indent=2)
        
        # Save threshold for later use
        with open(os.path.join(save_dir, 'threshold.txt'), 'w') as f:
            f.write(f"{threshold}\n")


def main():
    """메인 테스트 함수"""
    # Configuration
    CONFIG = {
        'label_dir': r'C:\Pycode\camera_test\dot_detection_system\labeling_data',
        'checkpoint_path': './checkpoints/best_model.pth',  # 학습된 모델 경로
        'model_type': 'improved',  # 'basic' or 'improved'
        'patch_size': 32,
        'latent_dim': 128,
        'batch_size': 64,
        'threshold': None,  # None이면 자동 계산
        'threshold_method': 'f1',  # 'f1' or 'youden'
        'device': 'cuda' if torch.cuda.is_available() else 'cpu',
        'num_workers': 0,
        'save_dir': './test_results'
    }
    
    print("=" * 60)
    print("Autoencoder Testing for Dot Filtering")
    print("=" * 60)
    print("\nConfiguration:")
    for key, value in CONFIG.items():
        print(f"  {key}: {value}")
    print()
    
    # Check if checkpoint exists
    if not os.path.exists(CONFIG['checkpoint_path']):
        print(f"Error: Checkpoint not found at {CONFIG['checkpoint_path']}")
        print("Please train the model first using train.py")
        return
    
    # Create test dataloader
    print("Loading test dataset...")
    test_loader = create_test_dataloader(
        label_dir=CONFIG['label_dir'],
        batch_size=CONFIG['batch_size'],
        patch_size=CONFIG['patch_size'],
        num_workers=CONFIG['num_workers']
    )
    
    # Create model
    print(f"Creating {CONFIG['model_type']} model...")
    model = create_model(
        model_type=CONFIG['model_type'],
        patch_size=CONFIG['patch_size'],
        latent_dim=CONFIG['latent_dim']
    )
    
    # Create tester
    tester = AutoencoderTester(
        model=model,
        checkpoint_path=CONFIG['checkpoint_path'],
        device=CONFIG['device']
    )
    
    # Evaluate
    threshold, predictions, errors = tester.evaluate(
        dataloader=test_loader,
        threshold=CONFIG['threshold'],
        threshold_method=CONFIG['threshold_method'],
        save_dir=CONFIG['save_dir']
    )


if __name__ == "__main__":
    main()

