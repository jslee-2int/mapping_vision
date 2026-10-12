"""
시각화 유틸리티
예측 결과와 모델 성능을 시각화
"""

import os
import cv2
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
import json


def visualize_predictions(image_path, 
                         points, 
                         predictions=None,
                         labels=None,
                         errors=None,
                         confidences=None,
                         threshold=None,
                         save_path=None,
                         show_confidence=True,
                         show_error=False):
    """
    예측 결과 시각화
    
    Args:
        image_path: 이미지 파일 경로
        points: 점들의 리스트 [(x1, y1), (x2, y2), ...]
        predictions: 예측 결과 [0 or 1, ...] (optional)
        labels: Ground truth labels [0 or 1, ...] (optional)
        errors: Reconstruction errors (optional)
        confidences: 신뢰도 [0-1, ...] (optional)
        threshold: Threshold value (optional)
        save_path: 저장 경로 (None이면 화면에 표시)
        show_confidence: 신뢰도 표시 여부
        show_error: Error 표시 여부
    """
    # Load image
    if isinstance(image_path, str):
        image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if image is None:
            raise ValueError(f"Failed to load image: {image_path}")
    else:
        image = image_path
    
    # Convert to RGB for visualization
    if len(image.shape) == 2:
        image_rgb = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
    else:
        image_rgb = image.copy()
    
    # Create figure
    fig, ax = plt.subplots(1, 1, figsize=(12, 10))
    ax.imshow(image_rgb, cmap='gray')
    
    # Plot points
    for i, (x, y) in enumerate(points):
        if predictions is not None:
            pred = predictions[i]
            color = 'green' if pred == 1 else 'red'
            marker = 'o' if pred == 1 else 'x'
            
            # Check if prediction is correct (if labels provided)
            if labels is not None:
                label = labels[i]
                if pred == label:
                    edgecolor = color
                    linewidth = 2
                else:
                    edgecolor = 'yellow'  # Wrong prediction
                    linewidth = 3
            else:
                edgecolor = color
                linewidth = 2
        else:
            color = 'blue'
            marker = 'o'
            edgecolor = color
            linewidth = 2
        
        # Plot point
        circle = Circle((x, y), radius=10, 
                       color=color, fill=False, 
                       edgecolor=edgecolor, linewidth=linewidth)
        ax.add_patch(circle)
        ax.plot(x, y, marker=marker, color=color, markersize=8)
        
        # Add text annotation
        text_parts = []
        
        if predictions is not None:
            text_parts.append(f"{'V' if predictions[i] == 1 else 'I'}")
        
        if labels is not None:
            text_parts.append(f"GT:{'V' if labels[i] == 1 else 'I'}")
        
        if show_error and errors is not None:
            text_parts.append(f"E:{errors[i]:.4f}")
        
        if show_confidence and confidences is not None:
            text_parts.append(f"C:{confidences[i]:.2f}")
        
        if text_parts:
            text = ' '.join(text_parts)
            ax.text(x + 15, y, text, 
                   fontsize=8, 
                   bbox=dict(boxstyle='round,pad=0.3', 
                            facecolor='white', 
                            alpha=0.7))
    
    # Title
    title_parts = ['Dot Prediction Results']
    if threshold is not None:
        title_parts.append(f'Threshold: {threshold:.4f}')
    if predictions is not None and labels is not None:
        accuracy = np.mean(np.array(predictions) == np.array(labels))
        title_parts.append(f'Accuracy: {accuracy:.2%}')
    
    ax.set_title(' | '.join(title_parts), fontsize=14, fontweight='bold')
    ax.axis('off')
    
    # Add legend
    if predictions is not None:
        from matplotlib.patches import Patch
        legend_elements = [
            Patch(facecolor='green', label='Valid'),
            Patch(facecolor='red', label='Invalid'),
        ]
        if labels is not None:
            legend_elements.append(Patch(facecolor='yellow', label='Wrong Prediction'))
        ax.legend(handles=legend_elements, loc='upper right')
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"Saved visualization to {save_path}")
        plt.close()
    else:
        plt.show()


def visualize_patches(patches, 
                     predictions=None, 
                     labels=None,
                     errors=None,
                     save_path=None,
                     num_cols=5):
    """
    패치들을 그리드로 시각화
    
    Args:
        patches: 패치 리스트 (numpy arrays)
        predictions: 예측 결과 (optional)
        labels: Ground truth labels (optional)
        errors: Reconstruction errors (optional)
        save_path: 저장 경로
        num_cols: 그리드 열 개수
    """
    num_patches = len(patches)
    num_rows = (num_patches + num_cols - 1) // num_cols
    
    fig, axes = plt.subplots(num_rows, num_cols, figsize=(num_cols * 2, num_rows * 2))
    if num_rows == 1:
        axes = axes.reshape(1, -1)
    
    for idx in range(num_rows * num_cols):
        row = idx // num_cols
        col = idx % num_cols
        ax = axes[row, col]
        
        if idx < num_patches:
            # Plot patch
            patch = patches[idx]
            if len(patch.shape) == 3 and patch.shape[0] == 1:
                patch = patch[0]  # Remove channel dimension
            
            ax.imshow(patch, cmap='gray')
            
            # Title
            title_parts = []
            if predictions is not None:
                pred = predictions[idx]
                title_parts.append(f"Pred: {'V' if pred == 1 else 'I'}")
            if labels is not None:
                label = labels[idx]
                title_parts.append(f"GT: {'V' if label == 1 else 'I'}")
            if errors is not None:
                title_parts.append(f"Error: {errors[idx]:.4f}")
            
            if title_parts:
                ax.set_title(' | '.join(title_parts), fontsize=8)
            
            # Color border
            if predictions is not None and labels is not None:
                if predictions[idx] == labels[idx]:
                    color = 'green'
                else:
                    color = 'red'
            elif predictions is not None:
                color = 'green' if predictions[idx] == 1 else 'red'
            else:
                color = 'gray'
            
            for spine in ax.spines.values():
                spine.set_edgecolor(color)
                spine.set_linewidth(2)
        
        ax.axis('off')
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"Saved patch visualization to {save_path}")
        plt.close()
    else:
        plt.show()


def visualize_reconstruction(original_patches, 
                            reconstructed_patches,
                            errors=None,
                            save_path=None,
                            num_examples=10):
    """
    원본과 재구성된 패치 비교 시각화
    
    Args:
        original_patches: 원본 패치 리스트
        reconstructed_patches: 재구성된 패치 리스트
        errors: Reconstruction errors (optional)
        save_path: 저장 경로
        num_examples: 표시할 예제 개수
    """
    num_examples = min(num_examples, len(original_patches))
    
    fig, axes = plt.subplots(num_examples, 3, figsize=(9, 3 * num_examples))
    if num_examples == 1:
        axes = axes.reshape(1, -1)
    
    for i in range(num_examples):
        orig = original_patches[i]
        recon = reconstructed_patches[i]
        
        # Remove channel dimension if present
        if len(orig.shape) == 3 and orig.shape[0] == 1:
            orig = orig[0]
        if len(recon.shape) == 3 and recon.shape[0] == 1:
            recon = recon[0]
        
        # Original
        axes[i, 0].imshow(orig, cmap='gray')
        axes[i, 0].set_title('Original', fontsize=10)
        axes[i, 0].axis('off')
        
        # Reconstructed
        axes[i, 1].imshow(recon, cmap='gray')
        axes[i, 1].set_title('Reconstructed', fontsize=10)
        axes[i, 1].axis('off')
        
        # Difference
        diff = np.abs(orig - recon)
        axes[i, 2].imshow(diff, cmap='hot')
        if errors is not None:
            axes[i, 2].set_title(f'Difference (Error: {errors[i]:.4f})', fontsize=10)
        else:
            axes[i, 2].set_title('Difference', fontsize=10)
        axes[i, 2].axis('off')
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"Saved reconstruction comparison to {save_path}")
        plt.close()
    else:
        plt.show()


def visualize_from_json(image_path, json_path, save_path=None):
    """
    라벨링 JSON 파일에서 데이터를 읽어 시각화
    
    Args:
        image_path: 이미지 파일 경로
        json_path: 라벨링 JSON 파일 경로
        save_path: 저장 경로
    """
    # Load JSON
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Extract points and labels
    points = [(p['x'], p['y']) for p in data['points']]
    labels = [p['label'] for p in data['points']]
    
    # Visualize
    visualize_predictions(
        image_path=image_path,
        points=points,
        labels=labels,
        save_path=save_path
    )


def create_comparison_plot(valid_errors, invalid_errors, threshold, save_path=None):
    """
    Valid와 Invalid 점들의 error 분포 비교 시각화
    
    Args:
        valid_errors: Valid 점들의 errors
        invalid_errors: Invalid 점들의 errors
        threshold: Threshold value
        save_path: 저장 경로
    """
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    
    # Histogram
    ax = axes[0, 0]
    ax.hist(valid_errors, bins=50, alpha=0.7, label='Valid', color='green', density=True)
    ax.hist(invalid_errors, bins=50, alpha=0.7, label='Invalid', color='red', density=True)
    ax.axvline(threshold, color='black', linestyle='--', linewidth=2, label=f'Threshold: {threshold:.4f}')
    ax.set_xlabel('Reconstruction Error')
    ax.set_ylabel('Density')
    ax.set_title('Error Distribution (Normalized)')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # Box plot
    ax = axes[0, 1]
    ax.boxplot([valid_errors, invalid_errors], labels=['Valid', 'Invalid'])
    ax.axhline(threshold, color='red', linestyle='--', linewidth=2, label=f'Threshold: {threshold:.4f}')
    ax.set_ylabel('Reconstruction Error')
    ax.set_title('Error Distribution (Box Plot)')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # Violin plot
    ax = axes[1, 0]
    parts = ax.violinplot([valid_errors, invalid_errors], positions=[1, 2], showmeans=True)
    ax.axhline(threshold, color='red', linestyle='--', linewidth=2, label=f'Threshold: {threshold:.4f}')
    ax.set_xticks([1, 2])
    ax.set_xticklabels(['Valid', 'Invalid'])
    ax.set_ylabel('Reconstruction Error')
    ax.set_title('Error Distribution (Violin Plot)')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # Cumulative distribution
    ax = axes[1, 1]
    valid_sorted = np.sort(valid_errors)
    invalid_sorted = np.sort(invalid_errors)
    ax.plot(valid_sorted, np.arange(1, len(valid_sorted) + 1) / len(valid_sorted), 
           label='Valid', color='green', linewidth=2)
    ax.plot(invalid_sorted, np.arange(1, len(invalid_sorted) + 1) / len(invalid_sorted),
           label='Invalid', color='red', linewidth=2)
    ax.axvline(threshold, color='black', linestyle='--', linewidth=2, label=f'Threshold: {threshold:.4f}')
    ax.set_xlabel('Reconstruction Error')
    ax.set_ylabel('Cumulative Probability')
    ax.set_title('Cumulative Distribution')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"Saved comparison plot to {save_path}")
        plt.close()
    else:
        plt.show()


if __name__ == "__main__":
    # Demo
    print("Visualization utilities loaded successfully!")
    print("\nAvailable functions:")
    print("  - visualize_predictions(): 예측 결과 시각화")
    print("  - visualize_patches(): 패치 그리드 시각화")
    print("  - visualize_reconstruction(): 재구성 비교 시각화")
    print("  - visualize_from_json(): JSON 파일에서 시각화")
    print("  - create_comparison_plot(): Error 분포 비교")

