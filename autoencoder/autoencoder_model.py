"""
Autoencoder 모델 정의
Valid/Invalid 점을 필터링하기 위한 Convolutional Autoencoder
"""

import torch
import torch.nn as nn
import torch.nn.functional as F


class DotAutoencoder(nn.Module):
    """
    점(dot) 패치를 분석하기 위한 Convolutional Autoencoder
    Valid 점들로만 학습되어, Invalid 점은 높은 reconstruction error를 생성
    """
    
    def __init__(self, patch_size=32, latent_dim=64):
        """
        Args:
            patch_size: 입력 패치의 크기 (기본값: 32x32)
            latent_dim: latent space의 차원
        """
        super(DotAutoencoder, self).__init__()
        self.patch_size = patch_size
        self.latent_dim = latent_dim
        
        # Calculate bottleneck spatial size (after 4 stride-2 convolutions)
        self.bottleneck_spatial_size = patch_size // 16
        self.bottleneck_features = 256 * self.bottleneck_spatial_size * self.bottleneck_spatial_size
        
        # Encoder
        self.encoder = nn.Sequential(
            # Input: 1 x patch_size x patch_size
            nn.Conv2d(1, 32, kernel_size=3, stride=2, padding=1),  # -> 32 x H/2 x W/2
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
            
            nn.Conv2d(32, 64, kernel_size=3, stride=2, padding=1),  # -> 64 x H/4 x W/4
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            
            nn.Conv2d(64, 128, kernel_size=3, stride=2, padding=1),  # -> 128 x H/8 x W/8
            nn.BatchNorm2d(128),
            nn.ReLU(inplace=True),
            
            nn.Conv2d(128, 256, kernel_size=3, stride=2, padding=1),  # -> 256 x H/16 x W/16
            nn.BatchNorm2d(256),
            nn.ReLU(inplace=True),
        )
        
        # Latent space (dynamically sized)
        self.flatten = nn.Flatten()
        self.fc_encode = nn.Linear(self.bottleneck_features, latent_dim)
        self.fc_decode = nn.Linear(latent_dim, self.bottleneck_features)
        
        # Decoder
        self.decoder = nn.Sequential(
            # Input: 256 x 2 x 2
            nn.ConvTranspose2d(256, 128, kernel_size=4, stride=2, padding=1),  # -> 128 x 4 x 4
            nn.BatchNorm2d(128),
            nn.ReLU(inplace=True),
            
            nn.ConvTranspose2d(128, 64, kernel_size=4, stride=2, padding=1),  # -> 64 x 8 x 8
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            
            nn.ConvTranspose2d(64, 32, kernel_size=4, stride=2, padding=1),  # -> 32 x 16 x 16
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
            
            nn.ConvTranspose2d(32, 1, kernel_size=4, stride=2, padding=1),  # -> 1 x 32 x 32
            nn.Sigmoid()  # 0-1 범위로 출력
        )
        
    def encode(self, x):
        """Encode input to latent space"""
        x = self.encoder(x)
        x = self.flatten(x)
        x = self.fc_encode(x)
        return x
    
    def decode(self, z):
        """Decode from latent space to reconstruction"""
        x = self.fc_decode(z)
        x = x.view(-1, 256, self.bottleneck_spatial_size, self.bottleneck_spatial_size)
        x = self.decoder(x)
        return x
    
    def forward(self, x):
        """Forward pass through autoencoder"""
        z = self.encode(x)
        reconstruction = self.decode(z)
        return reconstruction, z
    
    def get_reconstruction_error(self, x, reduction='mean'):
        """
        Calculate reconstruction error
        
        Args:
            x: 입력 이미지
            reduction: 'mean', 'sum', 'none'
        
        Returns:
            reconstruction error
        """
        with torch.no_grad():
            reconstruction, _ = self.forward(x)
            error = F.mse_loss(reconstruction, x, reduction=reduction)
        return error


class ImprovedDotAutoencoder(nn.Module):
    """
    개선된 Autoencoder with skip connections (U-Net style)
    더 정교한 reconstruction을 위해 skip connection 추가
    """
    
    def __init__(self, patch_size=32, latent_dim=128):
        super(ImprovedDotAutoencoder, self).__init__()
        self.patch_size = patch_size
        self.latent_dim = latent_dim
        
        # Calculate bottleneck spatial size (after 4 stride-2 convolutions)
        # patch_size -> patch_size/2 -> patch_size/4 -> patch_size/8 -> patch_size/16
        self.bottleneck_spatial_size = patch_size // 16
        self.bottleneck_features = 256 * self.bottleneck_spatial_size * self.bottleneck_spatial_size
        
        # Encoder with skip connections
        self.enc1 = self._encoder_block(1, 32)      # -> 32 x H/2 x W/2
        self.enc2 = self._encoder_block(32, 64)     # -> 64 x H/4 x W/4
        self.enc3 = self._encoder_block(64, 128)    # -> 128 x H/8 x W/8
        self.enc4 = self._encoder_block(128, 256)   # -> 256 x H/16 x W/16
        
        # Bottleneck (dynamically sized)
        self.flatten = nn.Flatten()
        self.fc_encode = nn.Linear(self.bottleneck_features, latent_dim)
        self.fc_decode = nn.Linear(latent_dim, self.bottleneck_features)
        
        # Decoder with skip connections
        self.dec4 = self._decoder_block(256, 128)       # -> 128 x 4 x 4
        self.dec3 = self._decoder_block(128 * 2, 64)    # -> 64 x 8 x 8 (128*2 due to concat)
        self.dec2 = self._decoder_block(64 * 2, 32)     # -> 32 x 16 x 16
        self.dec1 = self._decoder_block(32 * 2, 16)     # -> 16 x 32 x 32
        
        # Final output layer
        self.final = nn.Sequential(
            nn.Conv2d(16, 1, kernel_size=1),
            nn.Sigmoid()
        )
        
    def _encoder_block(self, in_channels, out_channels):
        return nn.Sequential(
            nn.Conv2d(in_channels, out_channels, kernel_size=3, stride=2, padding=1),
            nn.BatchNorm2d(out_channels),
            nn.LeakyReLU(0.2, inplace=True),
            nn.Conv2d(out_channels, out_channels, kernel_size=3, padding=1),
            nn.BatchNorm2d(out_channels),
            nn.LeakyReLU(0.2, inplace=True)
        )
    
    def _decoder_block(self, in_channels, out_channels):
        return nn.Sequential(
            nn.ConvTranspose2d(in_channels, out_channels, kernel_size=4, stride=2, padding=1),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_channels, out_channels, kernel_size=3, padding=1),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True)
        )
    
    def forward(self, x):
        # Encoder with stored features for skip connections
        e1 = self.enc1(x)           # 32 x H/2 x W/2
        e2 = self.enc2(e1)          # 64 x H/4 x W/4
        e3 = self.enc3(e2)          # 128 x H/8 x W/8
        e4 = self.enc4(e3)          # 256 x H/16 x W/16
        
        # Bottleneck
        flat = self.flatten(e4)
        z = self.fc_encode(flat)
        decoded = self.fc_decode(z)
        d4 = decoded.view(-1, 256, self.bottleneck_spatial_size, self.bottleneck_spatial_size)
        
        # Decoder with skip connections
        d4 = self.dec4(d4)                      # 128 x 4 x 4
        d3 = self.dec3(torch.cat([d4, e3], 1))  # concat -> 64 x 8 x 8
        d2 = self.dec2(torch.cat([d3, e2], 1))  # concat -> 32 x 16 x 16
        d1 = self.dec1(torch.cat([d2, e1], 1))  # concat -> 16 x H x W
        
        output = self.final(d1)                 # 1 x H x W
        
        return output, z
    
    def get_reconstruction_error(self, x, reduction='mean'):
        """Calculate reconstruction error"""
        with torch.no_grad():
            reconstruction, _ = self.forward(x)
            error = F.mse_loss(reconstruction, x, reduction=reduction)
        return error


def create_model(model_type='basic', patch_size=32, latent_dim=64):
    """
    모델 생성 헬퍼 함수
    
    Args:
        model_type: 'basic' 또는 'improved'
        patch_size: 패치 크기
        latent_dim: latent dimension
    
    Returns:
        모델 인스턴스
    """
    if model_type == 'basic':
        return DotAutoencoder(patch_size=patch_size, latent_dim=latent_dim)
    elif model_type == 'improved':
        return ImprovedDotAutoencoder(patch_size=patch_size, latent_dim=latent_dim)
    else:
        raise ValueError(f"Unknown model_type: {model_type}")


if __name__ == "__main__":
    # 모델 테스트
    print("Testing DotAutoencoder...")
    model = DotAutoencoder(patch_size=32, latent_dim=64)
    x = torch.randn(4, 1, 32, 32)
    reconstruction, latent = model(x)
    print(f"Input shape: {x.shape}")
    print(f"Latent shape: {latent.shape}")
    print(f"Reconstruction shape: {reconstruction.shape}")
    print(f"Reconstruction error: {model.get_reconstruction_error(x):.4f}")
    
    print("\nTesting ImprovedDotAutoencoder...")
    model2 = ImprovedDotAutoencoder(patch_size=32, latent_dim=128)
    reconstruction2, latent2 = model2(x)
    print(f"Input shape: {x.shape}")
    print(f"Latent shape: {latent2.shape}")
    print(f"Reconstruction shape: {reconstruction2.shape}")
    print(f"Reconstruction error: {model2.get_reconstruction_error(x):.4f}")
    
    # 파라미터 수 계산
    total_params = sum(p.numel() for p in model.parameters())
    total_params2 = sum(p.numel() for p in model2.parameters())
    print(f"\nBasic model parameters: {total_params:,}")
    print(f"Improved model parameters: {total_params2:,}")

