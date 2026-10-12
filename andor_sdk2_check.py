#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Andor SDK2 점검용 스크립트 (통신 + 1회 read).

pylablib `Andor`만 사용. CAtImaPy UI 없이 DLL·카메라 응답 확인용.

프로젝트 최상위에서:

  python andor_sdk2_check.py
  python andor_sdk2_check.py --idx 0
"""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--idx", type=int, default=0, help="카메라 인덱스 (SDK2)")
    p.add_argument(
        "--exposure",
        type=float,
        default=0.05,
        help="테스트 노출 시간 (초)",
    )
    args = p.parse_args(argv)

    try:
        from pylablib.devices import Andor
    except ImportError as e:
        print("pylablib 없음:", e)
        return 1

    # --- 통신: SDK / 장치 개수 ---
    try:
        n = Andor.get_cameras_number_SDK2()
        ver = Andor.get_SDK2_version()
    except Exception as e:
        print("SDK2 초기화/조회 실패:", e)
        return 1

    print("[통신] get_cameras_number_SDK2 =", n)
    print("[통신] get_SDK2_version =", ver)

    if n <= 0:
        print("연결된 카메라 없음 — 점검 종료.")
        return 0

    if args.idx < 0 or args.idx >= n:
        print(f"idx={args.idx} 는 범위 밖 (0..{n - 1})")
        return 1

    cam = None
    try:
        cam = Andor.AndorSDK2Camera(idx=args.idx, fan_mode="full", temperature=-70)
        if not cam.is_opened():
            print("[통신] 카메라 open 실패")
            return 1

        info = cam.get_device_info()
        print("[통신] device_info =", info)

        # --- read: 짧은 노출로 1프레임 (grab/snap이 내부에서 acquisition 설정) ---
        cam.set_trigger_mode("software")
        cam.set_exposure(args.exposure)
        img = cam.snap(timeout=15.0)
        print(
            "[read] shape =",
            getattr(img, "shape", None),
            "dtype =",
            getattr(img, "dtype", None),
            "min/max =",
            float(img.min()),
            float(img.max()),
        )
    except Exception as e:
        print("오류:", type(e).__name__, e)
        return 1
    finally:
        if cam is not None and cam.is_opened():
            try:
                cam.stop_acquisition()
            except Exception:
                pass
            cam.close()
        print("[통신] close 완료")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
