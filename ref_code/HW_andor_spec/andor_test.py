"""
Andor Shamrock 스펙트로미터 점검용 CLI.

`andor_spec_dev.AndorShamrockSpec` 래퍼를 열어 상태를 읽거나(기본) 파장·그레이팅을 설정합니다.
SDK DLL 경로는 `andor_spec_dev.py`에 정의되어 있습니다.
"""

from __future__ import annotations

import argparse
import sys

try:
    from ref_code.HW_andor_spec.andor_spec_dev import AndorShamrockSpec
except ModuleNotFoundError:
    from andor_spec_dev import AndorShamrockSpec


def print_summary(s: AndorShamrockSpec) -> None:
    print("serial_number     ", s.serial_number)
    print("focal_length (mm) ", s.focal_length)
    print("angular_deviation ", s.angular_deviation)
    print("focal_tilt        ", s.focal_tilt)
    print("num_gratings      ", s.num_gratings)
    print("gratings dict     ", s.gratings)
    print("turret            ", s.get_turret())
    print("grating (active)  ", s.get_grating(), "|", s.gratings.get(s.get_grating(), "?"))
    print("wavelength (nm)   ", s.get_wavelength())
    print("focus_mirror pos  ", s.get_focus_mirror_position(), "/", s.focus_mirror_max_steps)
    print("slit_present      ", s.slit_present)
    print("flipper_present   ", s.flipper_mirror_present)
    if s.flipper_mirror_present.get("input"):
        print("  flipper input   ", s.get_flipper_mirror("input"))
    if s.flipper_mirror_present.get("output"):
        print("  flipper output  ", s.get_flipper_mirror("output"))

    for gi in range(1, s.num_gratings + 1):
        info = s.get_grating_info(gi)
        off = s.get_grating_offset(gi)
        print(f"  grating {gi}: lines={info[0]:.1f} blaze={info[1]!r} home={info[2]} offset={info[3]} | cal_offset={off}")

    for ent in ("direct", "side"):
        for ex in ("direct", "side"):
            print(f"  detector_offset {ent}/{ex}: {s.get_detector_offset(ent, ex)}")

    for name, present in s.slit_present.items():
        if not present:
            continue
        try:
            w = s.get_slit_width(name)
            print(f"  slit width {name}: {w} µm")
        except OSError as e:
            print(f"  slit width {name}: (read failed) {e}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dev-id", type=int, default=0, help="Shamrock 장치 인덱스")
    p.add_argument(
        "--set-wavelength",
        type=float,
        metavar="NM",
        default=None,
        help="중심 파장 설정 후 다시 읽어 출력",
    )
    p.add_argument(
        "--set-grating",
        type=int,
        metavar="N",
        default=None,
        help="활성 그레이팅 번호 설정 (1..num_gratings)",
    )
    p.add_argument(
        "--no-summary",
        action="store_true",
        help="요약 출력 생략 (--set-* 만 쓸 때)",
    )
    args = p.parse_args(argv)

    try:
        spec = AndorShamrockSpec(dev_id=args.dev_id)
    except Exception as e:
        print("열기 실패: {}: {}".format(type(e).__name__, e), file=sys.stderr)
        return 1

    try:
        if args.set_grating is not None:
            spec.set_grating(args.set_grating)
            print("set_grating ->", args.set_grating, "| now", spec.get_grating())
        if args.set_wavelength is not None:
            spec.set_wavelength(args.set_wavelength)
            print("set_wavelength ->", args.set_wavelength, "nm | now", spec.get_wavelength())
        if not args.no_summary:
            print("--- summary ---")
            print_summary(spec)
    finally:
        spec.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
