import sif_parser
import numpy as np
import matplotlib.pyplot as plt

class SIF:
    def __init__(self, file_path):
        """
        .sif 파일을 읽고 파장(wavelength)과 인텐시티(intensity)를 초기화합니다.

        Parameters:
            file_path (str): .sif 파일 경로
        """
        # .sif 파일 읽기
        self.data, self.info = sif_parser.np_open(file_path)

        # 파장 정보 추출
        self.wavelength = sif_parser.utils.extract_calibration(self.info)

        # 인텐시티 정보 추출 (첫 번째 프레임의 데이터를 사용)
        self.intensity = self.data[0].flatten()  # data는 3D 배열 (프레임, 높이, 너비)

    def read(self):
        """
        파장과 인텐시티를 반환합니다.

        Returns:
            wavelength (np.ndarray): 파장 정보 (1D 배열)
            intensity (np.ndarray): 인텐시티 정보 (1D 배열)
        """
        return self.wavelength, self.intensity
