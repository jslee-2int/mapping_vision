import win32gui
import win32com.client
import win32process
import time
import win32con
import sif_parser
import pywintypes

# QTimer-based sleep (non-blocking for Qt UI)
try:
    from PyQt6.QtCore import QTimer, QEventLoop, QCoreApplication
    def _qt_sleep(seconds):
        """QTimer + QEventLoop로 대기 (UI 응답성 유지). QApplication 없으면 time.sleep"""
        if QCoreApplication.instance() is None:
            time.sleep(seconds)
            return
        loop = QEventLoop()
        QTimer.singleShot(int(seconds * 1000), loop.quit)
        loop.exec()
except ImportError:
    def _qt_sleep(seconds):
        """Qt 미사용 시 time.sleep 폴백"""
        time.sleep(seconds)


class Solis_win32:
    def escape_sendkeys_string(self, text):
        """
        shell.SendKeys에서 특수 문자를 이스케이프
        특수 문자: + ^ % ~ ( ) { } [ ]
        """
        # SendKeys 특수 문자를 {} 안에 넣어서 이스케이프
        special_chars = {
            '+': '{+}',
            '^': '{^}',
            '%': '{%}',
            '~': '{~}',
            '(': '{(}',
            ')': '{)}',
            '{': '{{}',
            '}': '{}}',
            '[': '{[}',
            ']': '{]}'
        }
        
        result = []
        for char in text:
            if char in special_chars:
                result.append(special_chars[char])
            else:
                result.append(char)
        
        return ''.join(result)
    
    def find_window_with_string(self, search_string):
        def window_enum_handler(hwnd, result):
            if win32gui.IsWindowVisible(hwnd):
                window_title = win32gui.GetWindowText(hwnd)
                if search_string in window_title:
                    result.append((hwnd, window_title))

        result = []
        win32gui.EnumWindows(window_enum_handler, result)
        return result

    def has_save_options_dialog(self, hwnd):
        """
        Save Options 대화상자 유무 판단.
        Save Options는 MDI Child가 아닌 별도 대화상자(최상위 또는 메인 자식)이므로
        - 최상위 창 2개(메인+Save Options) 또는
        - 메인 창의 자식 대화상자(EnumChildWindows, MDI 제외) 존재 시 True
        """
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            top_level_count = [0]
            dialog_child_found = [False]

            # 1) 최상위 창 개수 (EnumWindows - MDI Child는 여기 포함 안 됨)
            def enum_top(h, _):
                if win32gui.IsWindowVisible(h):
                    try:
                        _, wpid = win32process.GetWindowThreadProcessId(h)
                        if wpid == pid:
                            top_level_count[0] += 1
                    except Exception:
                        pass
                return True

            win32gui.EnumWindows(enum_top, None)

            if top_level_count[0] == 2:
                return True  # 메인 + Save Options (최상위)

            # 2) 메인 창의 자식 대화상자 검사 (Save Options가 child일 경우, MDI Child 제외)
            # MDI Child는 "#1"로 시작, 대화상자는 보통 class "#32770" + 제목 있음
            def enum_child(h, _):
                if win32gui.IsWindowVisible(h):
                    try:
                        title = win32gui.GetWindowText(h)
                        if title.startswith("#1"):
                            return True  # MDI Child 제외
                        try:
                            cls = win32gui.GetClassName(h)
                            # 표준 대화상자이며 제목이 있는 경우 (Save Options 등 모달)
                            if cls == "#32770" and title and len(title.strip()) > 0:
                                dialog_child_found[0] = True
                        except Exception:
                            pass
                    except Exception:
                        pass
                return True

            win32gui.EnumChildWindows(hwnd, enum_child, None)
            return dialog_child_found[0]
        except Exception as e:
            print(f"[has_save_options_dialog] Error: {e}")
            return False

    def find_save_options_window(self, hwnd):
        """
        Save Options 대화상자 창의 hwnd 반환. 없으면 None.
        1) 제목에 "Save Options" 등 포함된 창 검색
        2) 최상위 창 2개인 경우 메인이 아닌 창 반환 (제목 매칭 실패 시)
        """
        result = [None]
        other_top_level = [None]  # 메인 외 다른 최상위 창
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        keywords = ("Save Options", "저장 옵션", "Options")

        def enum_top(h, _):
            if win32gui.IsWindowVisible(h):
                try:
                    _, wpid = win32process.GetWindowThreadProcessId(h)
                    if wpid == pid:
                        title = win32gui.GetWindowText(h)
                        if any(kw in title for kw in keywords):
                            result[0] = h
                            return False
                        if h != hwnd:
                            other_top_level[0] = h  # 메인 외 창
                except Exception:
                    pass
            return True

        win32gui.EnumWindows(enum_top, None)
        if result[0]:
            return result[0]

        def enum_child(h, _):
            if win32gui.IsWindowVisible(h):
                try:
                    title = win32gui.GetWindowText(h)
                    if title.startswith("#1"):
                        return True
                    if any(kw in title for kw in keywords):
                        result[0] = h
                        return False
                except Exception:
                    pass
            return True

        win32gui.EnumChildWindows(hwnd, enum_child, None)
        if result[0]:
            return result[0]

        # 제목 매칭 실패 시: 최상위 창 2개면 다른 창이 Save Options일 가능성
        if other_top_level[0]:
            return other_top_level[0]
        return None

    def send_enter_to_save_options(self, hwnd):
        """
        Save Options 창에 Enter 전송. 창을 찾아 직접 메시지 전송.
        포커스와 무관하게 PostMessage/SendMessage로 해당 창에 직접 전송 (main.py로 포커스 이동 방지)
        """
        target = self.find_save_options_window(hwnd)
        if not target:
            print("[send_enter_to_save_options] Save Options window not found")
            return False
        try:
            # Save Options 창이 완전히 준비될 때까지 대기 (대기 부족 시 Enter 미전달)
            _qt_sleep(1.0)
            # PostMessage/SendMessage로 직접 전송 (포커스 무관, main.py로 돌아가도 전달됨)
            for _ in range(2):  # 재시도
                win32gui.PostMessage(target, win32con.WM_KEYDOWN, win32con.VK_RETURN, 0)
                win32gui.PostMessage(target, win32con.WM_KEYUP, win32con.VK_RETURN, 0)
                _qt_sleep(0.2)
                win32gui.SendMessage(target, win32con.WM_KEYDOWN, win32con.VK_RETURN, 0)
                win32gui.SendMessage(target, win32con.WM_KEYUP, win32con.VK_RETURN, 0)
                _qt_sleep(0.3)
            return True
        except Exception as e:
            print(f"[send_enter_to_save_options] Error: {e}")
            return False

    def bring_window_to_foreground(self, hwnd, max_retries=3, timeout_sec=5.0):
        """
        창을 포그라운드로 가져오는 함수 (재시도 메커니즘 포함, 포그라운드 동기 실행)
        """
        for attempt in range(max_retries):
            try:
                if win32gui.IsIconic(hwnd):
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

                shell = win32com.client.Dispatch("WScript.Shell")
                shell.SendKeys('%')
                _qt_sleep(0.1)

                try:
                    win32gui.SetForegroundWindow(hwnd)
                except pywintypes.error as e:
                    print(f"SetForegroundWindow attempt {attempt + 1} failed: {e}")
                    try:
                        import win32api
                        current_thread = win32api.GetCurrentThreadId()
                        target_thread = win32process.GetWindowThreadProcessId(hwnd)[0]
                        if current_thread != target_thread:
                            win32process.AttachThreadInput(current_thread, target_thread, True)
                            try:
                                win32gui.SetForegroundWindow(hwnd)
                            finally:
                                win32process.AttachThreadInput(current_thread, target_thread, False)
                        else:
                            win32gui.SetForegroundWindow(hwnd)
                    except Exception as e2:
                        print(f"AttachThreadInput method failed: {e2}")
                        try:
                            win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
                            win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0,
                                                win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)
                            win32gui.SetWindowPos(hwnd, win32con.HWND_NOTOPMOST, 0, 0, 0, 0,
                                                win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)
                        except Exception as e3:
                            print(f"ShowWindow/SetWindowPos method failed: {e3}")
                            continue

                _qt_sleep(0.2)
                if win32gui.GetForegroundWindow() == hwnd:
                    print(f"Window successfully brought to foreground on attempt {attempt + 1}")
                    return True
                else:
                    print(f"Window not in foreground after attempt {attempt + 1}")
            except Exception as e:
                print(f"Error in bring_window_to_foreground attempt {attempt + 1}: {e}")
                _qt_sleep(0.5)
        return False

    def send_ctrl_s(self, hwnd, file_path=None, max_retries=3):
        """
        Ctrl+S 명령을 보내는 함수 (포그라운드 전용)
        Args:
            hwnd: 윈도우 핸들
            file_path: 저장할 파일 경로 (폴더경로 + 파일이름.SIF)
            max_retries: 최대 재시도 횟수
        """
        if file_path is None:
            file_path = "py_test.SIF"

        shell = win32com.client.Dispatch("WScript.Shell")

        for attempt in range(max_retries):
            try:
                # 현재 활성 창 저장 (작업 후 복원용)
                current_foreground = win32gui.GetForegroundWindow()

                # 창을 포그라운드로 가져오기
                if not self.bring_window_to_foreground(hwnd):
                    print(f"Failed to bring window to foreground on attempt {attempt + 1}")
                    if attempt < max_retries - 1:
                        _qt_sleep(1)
                        continue
                    else:
                        print("Giving up on bringing window to foreground")
                        return False

                _qt_sleep(0.3)

                # 키 입력 시퀀스
                _qt_sleep(1.0)
                shell.SendKeys('{F5}')
                _qt_sleep(2.5)  # Acquisition이 완료될 때까지 충분히 대기
                shell.SendKeys('^s')
                _qt_sleep(1.0)  # 저장 대화상자가 완전히 열릴 때까지 충분한 대기
                
                # 파일명 필드에 확실히 포커스를 주기 위해 여러 방법 시도
                # 방법 1: Alt+N (파일명 필드로 이동, Windows 표준)
                shell.SendKeys('%n')
                _qt_sleep(0.2)
                
                # 방법 2: 파일명 필드를 선택하고 기존 내용 지우기
                shell.SendKeys('^a')  # 전체 선택
                _qt_sleep(0.2)
                shell.SendKeys('{DELETE}')  # 기존 내용 삭제
                _qt_sleep(0.3)
                
                # 파일 경로 입력 (확실히 입력되도록)
                print(f"Sending file path: {file_path}")
                # SendKeys 특수 문자 이스케이프 (괄호 등)
                escaped_path = self.escape_sendkeys_string(file_path)
                print(f"Escaped path: {escaped_path}")
                shell.SendKeys(escaped_path)  # 새 파일 경로 입력
                _qt_sleep(0.5)  # 입력이 완료될 때까지 대기
                
                # Enter로 바로 저장 (Tab 불필요)
                _qt_sleep(2.0)
                shell.SendKeys('{ENTER}')  # 파일명 입력 후 바로 저장
                # Save Options 확인: 감지 시 해당 창에 직접 Enter 전송
                _qt_sleep(3.0)  # 저장 완료 및 Save Options 표시 대기 (대기 부족 시 Enter 미전달)
                if self.has_save_options_dialog(hwnd):
                    print("Save Options detected, sending Enter...")
                    _qt_sleep(2.0)  # Save Options 창 준비 대기
                    if not self.send_enter_to_save_options(hwnd):
                        shell.SendKeys('{ENTER}')
                else:
                    print("Save Options not detected, skipping Enter")
                
                _qt_sleep(0.5)  # 안정화 대기

                # 원래 창으로 복원
                if current_foreground:
                    try:
                        self.bring_window_to_foreground(current_foreground)
                        print(f"Restored original window to foreground")
                    except Exception as e:
                        print(f"Failed to restore original window: {e}")
                
                print(f"Ctrl+S sequence completed successfully on attempt {attempt + 1} with file: {file_path}")
                return True
                
            except Exception as e:
                print(f"Error in send_ctrl_s attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    _qt_sleep(1)  # 재시도 전 대기
                else:
                    print("Failed to send Ctrl+S after all attempts")
                    return False
        
        return False

    def find_mdi_child_windows(self, mdi_hwnd):
        def window_enum_handler(hwnd, result):
            if win32gui.IsWindowVisible(hwnd):
                window_title = win32gui.GetWindowText(hwnd)
                if window_title.startswith("#1"):  # "#1"로 시작하는 창 찾기
                    result.append((hwnd, window_title))

        result = []
        win32gui.EnumChildWindows(mdi_hwnd, window_enum_handler, result)
        return result
    
    def wait_for_mdi_child_windows(self, mdi_hwnd, timeout=10, check_interval=0.5):
        """
        MDI child window가 생성될 때까지 대기
        
        Args:
            mdi_hwnd: MDI 부모 창 핸들
            timeout: 최대 대기 시간 (초)
            check_interval: 확인 간격 (초)
        
        Returns:
            list: 찾은 child window 목록
        """
        print(f"[MDI] Waiting for child windows (timeout: {timeout}s)...")
        start_time = time.time()
        attempt = 0
        while time.time() - start_time < timeout:
            attempt += 1
            child_windows = self.find_mdi_child_windows(mdi_hwnd)
            if child_windows:
                print(f"[MDI] ✓ Found {len(child_windows)} child window(s) after {attempt} attempts:")
                for hwnd, title in child_windows:
                    print(f"[MDI]   - {title} (hwnd: {hwnd})")
                return child_windows
            _qt_sleep(check_interval)
        
        print(f"[MDI] ✗ No child windows found after {timeout}s ({attempt} attempts)")
        return []
    
    def close_mdi_child_windows(self, mdi_hwnd, max_retries=3):
        """
        MDI child window를 안전하게 닫기
        
        Args:
            mdi_hwnd: MDI 부모 창 핸들
            max_retries: 최대 재시도 횟수
        
        Returns:
            bool: 성공 여부
        """
        print(f"[MDI] Starting close_mdi_child_windows (max_retries: {max_retries})...")
        
        # 창이 생성될 때까지 대기
        child_windows = self.wait_for_mdi_child_windows(mdi_hwnd, timeout=10)
        
        if not child_windows:
            print("[MDI] ✓ No child windows to close")
            return True
        
        # 각 child window를 닫기
        for idx, (child_hwnd, child_title) in enumerate(child_windows, 1):
            print(f"\n[MDI] Closing window {idx}/{len(child_windows)}: {child_title} (hwnd: {child_hwnd})")
            
            for attempt in range(max_retries):
                try:
                    print(f"[MDI]   Attempt {attempt + 1}/{max_retries}: Sending WM_CLOSE...")
                    # 방법 1: SendMessage로 동기적으로 WM_CLOSE 전송
                    result = win32gui.SendMessage(child_hwnd, win32con.WM_CLOSE, 0, 0)
                    print(f"[MDI]   SendMessage WM_CLOSE result: {result}")
                    _qt_sleep(0.5)
                    
                    # 창이 실제로 닫혔는지 확인
                    if not win32gui.IsWindow(child_hwnd):
                        print(f"[MDI]   ✓ Window closed successfully on attempt {attempt + 1}")
                        break
                    
                    # 창이 여전히 존재하면 다른 방법 시도
                    if attempt < max_retries - 1:
                        print(f"[MDI]   ⚠ Window still exists, trying DestroyWindow...")
                        try:
                            win32gui.DestroyWindow(child_hwnd)
                            _qt_sleep(0.3)
                            if not win32gui.IsWindow(child_hwnd):
                                print(f"[MDI]   ✓ Window destroyed successfully")
                                break
                        except Exception as e:
                            print(f"[MDI]   ✗ DestroyWindow failed: {e}")
                    
                except pywintypes.error as e:
                    if e.winerror == 1400:  # Invalid window handle
                        print(f"[MDI]   ✓ Window already closed")
                        break
                    else:
                        print(f"[MDI]   ✗ Error closing window on attempt {attempt + 1}: {e}")
                        if attempt < max_retries - 1:
                            _qt_sleep(0.5)
                except Exception as e:
                    print(f"[MDI]   ✗ Unexpected error on attempt {attempt + 1}: {e}")
                    if attempt < max_retries - 1:
                        _qt_sleep(0.5)
            
            # 최종 확인
            try:
                if win32gui.IsWindow(child_hwnd):
                    print(f"[MDI] ✗ Failed to close window {child_title} after all attempts")
                    return False
            except:
                # IsWindow 자체가 실패하면 창이 이미 닫힌 것으로 간주
                print(f"[MDI] ✓ Window handle invalid (already closed)")
        
        print("\n[MDI] ✓ All child windows closed successfully")
        return True

    def sif_file_read(self, path_to_file):
        data, info = sif_parser.np_open(str(path_to_file))
        wavelengths = sif_parser.utils.extract_calibration(info)
        return wavelengths, data, info


if __name__ == "__main__":
    print("\n" + "="*70)
    print("  Solis Win32 Control Test (Foreground Mode)")
    print("="*70 + "\n")

    SOLIS = Solis_win32()
    andor_windows = SOLIS.find_window_with_string("Andor SOLIS")

    if andor_windows:
        hwnd, title = andor_windows[0]
        print("="*70)
        print(f"✓ Andor SOLIS 창 발견")
        print(f"  - 핸들: {hwnd}")
        print(f"  - 제목: {title}")
        print("="*70)

        print("\n🚀 Starting Solis control sequence (foreground)...\n")
        success = SOLIS.send_ctrl_s(hwnd, "py_(1,1).SIF")

        print("\n" + "="*70)
        if success:
            print("✓✓✓ Ctrl+S 시퀀스 완료 ✓✓✓")
        else:
            print("✗✗✗ Ctrl+S 시퀀스 실패 ✗✗✗")
        print("="*70)

        print("\n" + "="*70)
        print("  MDI Child Window 닫기")
        print("="*70 + "\n")
        mdi_success = SOLIS.close_mdi_child_windows(hwnd)

        # 최종 결과 요약
        print("\n" + "="*70)
        print("  최종 결과")
        print("="*70)
        print(f"  Acquisition & Save: {'✓ 성공' if success else '✗ 실패'}")
        print(f"  MDI Window Close:   {'✓ 성공' if mdi_success else '✗ 실패'}")
        print(f"  Overall Status:     {'✓✓✓ 모든 작업 성공 ✓✓✓' if (success and mdi_success) else '✗ 일부 작업 실패'}")
        print("="*70 + "\n")
        
    else:
        print("\n" + "="*70)
        print("✗ 'Andor SOLIS'가 포함된 창을 찾을 수 없습니다.")
        print("  Solis 프로그램이 실행 중인지 확인해주세요.")
        print("="*70 + "\n")