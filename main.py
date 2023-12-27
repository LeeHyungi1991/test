import ctypes
import multiprocessing
import os
import re
import sys
import time
import uuid
import winreg
from datetime import datetime
import socket
from sqlite3 import OperationalError
from threading import Thread

import pyWinhook
import pythoncom

import comtypes
import requests
from _ctypes import COMError

import db_connect

comtypes._check_version = lambda a, b: None

import uiautomation as auto
from comtypes.gen._944DE083_8FB8_45CF_BCB7_C477ACB2F897_0_1_0 import IUIAutomationElement
from uiautomation import GetFocusedControl, Control

import pyautogui
import psutil
import webbrowser


def extract_origin_from_url(url: str):
    """
    Extract origin from url
    :param url: url
    :return: origin
    """
    pattern = re.compile(r'^(?:https?:\/\/)([^:\/?\n]+)')
    searched = pattern.search(url)
    if searched is None:
        return ''
    return searched.group(1)


def get_browser_tab_addr_bar(browser: str, top_window: Control):
    """
    Get browser tab url, browser must already open
    :param browser: Support 'Edge' 'Google Chrome' and other Chromium engine browsers
    :param top_window: Browser top window
    :return: Current tab url
    """
    try:
        http_or_https = "http://"
        if browser.lower() == 'msedge':
            addr_bar = top_window.EditControl(AutomationId='view_1020')
            http_or_https = ""
        else:
            ssl_button_path = [4, 1]
            pane = top_window
            if not pane.Exists():
                return ''
            toolbar_path = [len(pane.GetChildren()), 1, 2]
            for i in toolbar_path:
                pane = pane.GetChildren()[i - 1]
            pane = pane.ToolBarControl()
            addr_bar = pane.EditControl()
            # for i in ssl_button_path:
            #     pane = pane.GetChildren()[i - 1]
            # ssl_menu_item = pane
            # if ssl_menu_item.Name == 'Chrome':
            #     http_or_https = ""
            # else:
            #     rect = ssl_menu_item.BoundingRectangle
            #     width = rect.right - rect.left
            #     if width == 32:
            #         http_or_https = "https://"
        # if (not addr_bar) or (not addr_bar.IsEnabled):
        #     return ''
        return f'{http_or_https}{addr_bar.GetValuePattern().Value}'
    except LookupError as l:
        return ''


def get_script_folder():
    # path of main .py or .exe when converted with pyinstaller
    if getattr(sys, 'frozen', False):
        script_path = os.path.dirname(sys.executable)
    else:
        script_path = os.path.dirname(
            os.path.abspath(sys.modules['__main__'].__file__)
        )
    return script_path


class Result(ctypes.Structure):
    _fields_ = [
        ('password_exists', ctypes.c_bool),
        ('email_input_detected', ctypes.c_bool),
        ('edit_element_detected', ctypes.c_int),
        ('count', ctypes.c_int),
        ('result_code', ctypes.c_int),
    ]

    def __repr__(self):
        return f'Count: {self.count}, Password_exists: {self.password_exists}, Email_input_detected: {self.email_input_detected}, Edit_element_detected: {self.edit_element_detected}, Result_code: {self.result_code}'


class BitFlag:
    def __init__(self, value: int):
        self.value = value

    def __repr__(self):
        return f'0b{self.value:08b}'

    def get(self, index: int):
        return (self.value >> 7 - index) & 1

    def set(self, index: int):
        self.value |= (1 << 7 - index)

    def remove(self, index: int):
        self.value &= ~(1 << 7 - index)

    def __eq__(self, other):
        return self.value == other.value


def name_list_when_DB_connect():
    db_connect.sync_from_mainDB_to_localDB("1.3.2")
    db_connect.initialize_to_local_db_server()

    conn_loc = db_connect.get_local_connection()
    cur_loc = db_connect.get_cursor(conn_loc)
    ret = load_name_list(cur_loc)
    db_connect.close_db_server(conn_loc)
    return ret


class KMP:
    def __init__(self, pattern: str):
        self.pattern = pattern
        self.pattern_length = len(pattern)
        self.fail = [0] * self.pattern_length

        self.fail[0] = -1
        for i in range(1, self.pattern_length):
            j = self.fail[i - 1]
            while (self.pattern[i] != self.pattern[j + 1]) and (j >= 0):
                j = self.fail[j]
            if self.pattern[i] == self.pattern[j + 1]:
                self.fail[i] = j + 1
            else:
                self.fail[i] = -1

    def find(self, text: str):
        text_length = len(text)
        j = 0
        for i in range(text_length):
            while (text[i] != self.pattern[j]) and (j > 0):
                j = self.fail[j - 1]
            if text[i] == self.pattern[j]:
                if j == self.pattern_length - 1:
                    return True
                else:
                    j += 1
        return False


def load_name_list(cur):
    # 메일 페이지 판별용 String 배열들
    try:
        name_from = db_connect.get_label_from(cur)
        name_to = db_connect.get_label_to(cur)
        name_cc = db_connect.get_label_cc(cur)
        name_hidden_cc = db_connect.get_label_hidden_cc(cur)
        name_title = db_connect.get_label_title(cur)
        name_content = db_connect.get_label_content(cur)
        name_file = db_connect.get_label_file(cur)
        name_send = db_connect.get_label_send(cur)
        return [name_from, name_to, name_cc, name_hidden_cc, name_title, name_content, name_file, name_send]
    except OperationalError:
        print("DB 연결 실패")
        return None


keyword_value = ''


def on_keyboard_up(event: pyWinhook.KeyboardEvent):
    print(event.Key)
    global keyword_value
    keyword_value += event.Key + " "
    return True


def check_with_word2(all_text_set: set[str], name_list, result) -> bool:
    bit_flag = BitFlag(0b00000000)
    for i, db_label_list in enumerate(name_list):
        flag = False
        for db_label in db_label_list:
            db_label = db_label.strip().lower()
            kmp = KMP(db_label)
            for scrapped_text in all_text_set:
                scrapped_text = scrapped_text.strip().lower()
                if kmp.find(scrapped_text):
                    flag = True
                    break
            if flag:
                break
        if flag:
            bit_flag.set(i)

    print(f"감지된 단어 패턴: {bit_flag}")
    eid = result.email_input_detected
    pe = result.password_exists
    eed = result.edit_element_detected >= 1
    # patterns = [
    #     0b11000100,  # 보내는사람 + 받는사람 + 내용
    #     0b11001000,  # 보내는사람 + 받는사람 + 제목
    #     0b01101010,  # 받는사람 + 제목 + 참조 + 파일첨부
    #     0b11000010,  # 보내는사람 + 받는사람 + 파일첨부
    #     0b01001010,  # 받는사람 + 제목 + 파일첨부
    #     0b01101000,  # 받는사람 + 제목 + 참조
    #     0b01001100,  # 받는사람 + 제목 + 내용
    #     0b10001100,  # 보내는사람 + 제목 + 내용
    # # 위 패턴에서 보내기 버튼 추가한 패턴들
    #     0b11101011,  # 보내는사람 + 받는사람 + 제목 + 참조 + 파일첨부
    #     0b11001011,  # 보내는사람 + 받는사람 + 제목 + 파일첨부
    #     0b11001101,  # 보내는사람 + 받는사람 + 제목 + 내용
    #     0b11000101,  # 보내는사람 + 받는사람 + 내용
    #     0b11001001,  # 보내는사람 + 받는사람 + 제목
    #     0b01101011,  # 받는사람 + 제목 + 참조 + 파일첨부
    #     0b11000011,  # 보내는사람 + 받는사람 + 파일첨부
    #     0b01001011,  # 받는사람 + 제목 + 파일첨부 + 보내기
    #     0b01101001,  # 받는사람 + 제목 + 참조
    #     0b01001101,  # 받는사람 + 제목 + 내용
    #     0b10000101,  # 보내는사람 + 내용
    #     0b10001101,  # 보내는사람 + 제목 + 내용
    #     0b10001111,  # 보내는사람 + 제목 + 내용 + 첨부
    #     0b11001111,  # 보내는사람 + 받는사람 + 제목 + 내용 + 첨부
    #     0b11111111,  # 모든 항목
    #
    # # 특정 페이지별 패턴
    #     0b01001110,  # 받는사람 + 제목 + 내용 + 첨부 (moakt)
    #     0b01010011,  # 받는사람 + 숨은참조 + 첨부 + 보내기 (게릴라메일)
    #     0b01011011,  # 받는사람 + 제목 + 숨은참조 + 첨부 + 보내기 (게릴라메일)
    #     0b01111011,  # 받는사람 + 참조 + 숨은참조 + 제목 + 파일첨부 + 보내기 (Gmail)
    #     0b00001011,  # 제목 + 파일 첨부 + 보내기(Gmail)
    #     0b01010000,  # 받는사람 + 숨은참조(야후)
    #     0b01110000,  # 받는사람 + 참조 + 숨은참조 (야후)
    #     0b01010001,  # 받는사람 + 숨은참조 + 보내기 (야후)
    #     0b01110001,  # 받는사람 + 참조 + 숨은참조 + 보내기 (야후)
    #     0b01011111,  # 받는사람 + 숨은참조 + 제목 + 내용 + 첨부 + 보내기 (야후)
    #     0b01101111,  # 받는사람 + 제목 + 참조 + 첨부 + 내용 + 보내기 (네이버)
    #     0b11111011  # 보내는사람 + 받는사람 + 참조 + 숨은참조 + 제목 + 첨부 + 보내기 (다음, 카카오)
    # ]
    # patterns = [
    #     0b11000100,  # 보내는사람 + 받는사람 + 내용
    #     0b11001000,  # 보내는사람 + 받는사람 + 제목
    #     0b01101010,  # 받는사람 + 제목 + 참조 + 파일첨부
    #     0b11000010,  # 보내는사람 + 받는사람 + 파일첨부
    #     0b01001010,  # 받는사람 + 제목 + 파일첨부
    #     0b01101000,  # 받는사람 + 제목 + 참조
    #     0b01001100,  # 받는사람 + 제목 + 내용
    #     0b10001100,  # 보내는사람 + 제목 + 내용
    # ]
    if bit_flag.value & 0b11100001 == 0b11100001:
        return not pe
    elif bit_flag.value & 0b11110000 == 0b11110000:
        return eid and not pe
    elif (bit_flag.value & 0b00001001 == 0b00001001) or (bit_flag.value & 0b00001011 == 0b00001011):
        return eed and not pe
    return False


def mailpage_judge_logic2(top_window: auto.Control, browser: str, name_list, get_result_func, main_to_keyboard_queue):
    ret = False
    if browser == 'chrome':
        top_window = top_window.DocumentControl(ClassName='Chrome_RenderWidgetHostHWND')
    elif browser == 'msedge':
        top_window = top_window.PaneControl(ClassName='Chrome_RenderWidgetHostHWND')
    main_to_keyboard_queue.put("start")
    result: Result = get_result_func(top_window.Element)
    main_to_keyboard_queue.put("end")
    while keyboard_to_main_queue.empty():
        pass
    result.edit_element_detected = result.edit_element_detected or keyboard_to_main_queue.get()
    if result.result_code != 0:
        raise Exception("dll단에서 오류가 발생하였습니다. 해당 오류 코드를 검색하여 원인을 찾아내주세요. Error Code: " + str(result.result_code))
    f = open("./found_words.dat", 'r', encoding='UTF8')
    buffer = ""
    while True:
        line = f.readline()
        buffer += line
        if not line:
            break
    f.close()
    words = buffer.split("___")
    all_text_set = set()
    replace_list = ["\x00", "\u202c", "\u202a", "(", ")", ":", "!", "?", ",", ".", " ", "\n", "\r", "\t"]
    for i in range(len(words)):
        for replace in replace_list:
            words[i] = words[i].replace(replace, "")
        if words[i].strip() != "":
            all_text_set.add(words[i].strip())
    return check_with_word2(all_text_set, name_list, result)


def solution(main_to_keyboard_queue: multiprocessing.Queue, keyboard_to_main_queue: multiprocessing.Queue):
    # print(get_mac_address().upper())
    # print("IP Address(Internal) : ", socket.gethostbyname(socket.gethostname()))
    # req = requests.get('http://ipconfig.kr')
    # print(re.search(r'IP Address : (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', req.text).group(1))
    # print("IP Address(External) : ", socket.gethostbyname(socket.getfqdn()))
    tab_name = ''
    url = ''
    chrome_reg_path = r"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths\\chrome.exe"
    edge_reg_path = r"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths\\msedge.exe"
    keypath_chrome = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, chrome_reg_path, 0, winreg.KEY_READ)
    keypath_msedge = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, edge_reg_path, 0, winreg.KEY_READ)
    chrome_path = f'{winreg.QueryValueEx(keypath_chrome, "Path")[0]}\\chrome.exe'
    msedge_path = f'{winreg.QueryValueEx(keypath_msedge, "Path")[0]}\\msedge.exe'
    webbrowser.register('chrome', None, webbrowser.BackgroundBrowser(chrome_path))
    webbrowser.register('msedge', None, webbrowser.BackgroundBrowser(msedge_path))
    auto.SetGlobalSearchTimeout(2)
    # 순서: [ 보내는사람 - 받는사람 - 참조 - 숨은참조 - 제목 - 내용 - 첨부 - 보내기 ]
    name_list = name_list_when_DB_connect()

    browser_dict = {"msedge.exe": "msedge", "chrome.exe": "chrome"}

    auto_dll = ctypes.windll.LoadLibrary('./detector.dll')
    get_result_func = auto_dll['GetResult']
    get_result_func.argtypes = [comtypes.POINTER(IUIAutomationElement)]
    get_result_func.restype = Result

    while True:
        try:
            start = datetime.now()
            top_window = GetFocusedControl()
            if not top_window:
                continue
            process = psutil.Process(top_window.ProcessId)
            process_name = process.name()
            if process_name not in browser_dict:
                continue
            top_window = top_window.GetAncestorControl(
                condition=lambda control, depth: control.GetParentControl().ClassName == '#32769')
            if top_window.Name != tab_name:
                tab_name = top_window.Name
                url = extract_origin_from_url(
                    get_browser_tab_addr_bar(browser_dict[process_name], top_window))
            if not url:
                continue
            chk_combination_match = mailpage_judge_logic2(top_window, browser_dict[process_name], name_list,
                                                          get_result_func, main_to_keyboard_queue)
            print(datetime.now() - start)
            if chk_combination_match:
                print(f"Domain: {url}, Speed: {datetime.now() - start}")
                top_window.SendKeys('{Ctrl}{W}')
                time.sleep(0.2)
                pyautogui.hotkey('ctrl', 'space')
                webbrowser.get(browser_dict[process_name]).open_new_tab(
                    url="https://dev.remote.diffspec.net/block_rdr")
            else:
                time.sleep(0.1)
        except (LookupError, OSError, COMError, AttributeError, IndexError) as e:
            time.sleep(1)
            pass
        except Exception as e:
            raise


def keyboard_listener_thread(args):
    hm: pyWinhook.HookManager = args
    hm.HookKeyboard()
    pythoncom.PumpMessages()


def keyboard_listener(arr, main_to_keyboard_queue: multiprocessing.Queue,
                      keyboard_to_main_queue: multiprocessing.Queue):
    hm = pyWinhook.HookManager()
    hm.SubscribeKeyUp(on_keyboard_up)
    t = Thread(target=keyboard_listener_thread, args=([hm]))
    t.start()
    global keyword_value
    while True:
        if main_to_keyboard_queue.empty():
            continue
        pop_key = main_to_keyboard_queue.get()
        if pop_key == "start":
            print("start")
            keyword_value = ''
        elif pop_key == "end":
            print("end")
            # hm.UnhookKeyboard()
            keyboard_to_main_queue.put('Lcontrol V' in keyword_value)


if __name__ == '__main__':
    main_to_keyboard_queue = multiprocessing.Queue()
    keyboard_to_main_queue = multiprocessing.Queue()
    multiprocessing.Process(target=keyboard_listener, args=([], main_to_keyboard_queue, keyboard_to_main_queue)).start()
    time.sleep(1)
    solution(main_to_keyboard_queue, keyboard_to_main_queue)
