"""
주식 자동매매 프로그램의 메인 실행 모듈
다중 프로세스를 사용하여 여러 계좌의 동시 거래를 관리

주요 기능:
1. 종목 정보 초기화
2. 다중 프로세스 기반 거래 실행
3. 실시간 데이터 처리
4. 계좌별 거래 전략 실행
"""

import os
import time
import json
import datetime
import multiprocessing
import logging
from utility_multiprocessing import  Account_detail, Web_socket_connect, Market_open, Send_message, Liquidation, read_JSON, write_JSON, create_Folder, delete_Folder
from tr_functions import get_access_TOKEN, get_approval, aes_cbc_base64_dec
from stockinfo_generation_on_trading import stockinfo_generation_on_trading

from ALGORITHM import STRATEGY

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('trading.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def Assign_Trading_Algorithm_To_Stock(info, stock_infos):
    """
    각 종목별로 거래 전략 객체를 할당
    
    Args:
        info (dict): API 접속 정보
        stock_infos (dict): 종목 정보
        
    Returns:
        dict: 종목별 거래 전략 객체 딕셔너리
    """
    Trading_Algo = {}
    for code in stock_infos.keys():
        algo = STRATEGY(info, code=code)
        Trading_Algo[code] = algo
    return Trading_Algo

class OuterWorker:
    """
    개별 계좌의 거래를 처리하는 워커 클래스
    
    Attributes:
        _info (dict): API 접속 정보 및 계좌 정보
        _info_path (str): 계좌 정보 저장 경로
        _stock_dir_path (str): 종목 정보 저장 경로
        _stock_list (dict): 전체 종목 정보
        _Stock_Algo (dict): 종목별 거래 전략 객체
        _ws (WebSocket): 웹소켓 연결 객체
        _aes_key (str): AES 암호화 키
        _aes_iv (str): AES 초기화 벡터
    """
    def __init__(self, info):
        self._info = info
        self._info_path = self._info['INFO_PATH'] = os.path.join(os.getcwd(), "ID_ACCOUNT", self._info['NAME'])
        self._stock_dir_path = self._info['STOCKS_DIR_PATH'] = os.path.join(self._info['INFO_PATH'], "stocks")
        self._stock_list = read_JSON(f'{self._info_path}/stocksinfo_TOTAL.json')

        # 종목 정보 디렉토리 초기화
        delete_Folder(self._info['STOCKS_DIR_PATH'])
        create_Folder(self._info['STOCKS_DIR_PATH'])
        for stock in self._stock_list.keys():
            write_JSON(self._stock_list[stock], f'{self._stock_dir_path}/{stock}.json')

        # 종목별 거래 전략 할당
        self._Stock_Algo = Assign_Trading_Algorithm_To_Stock(self._info, self._stock_list)
  
    def do_work(self):
        """
        워커의 주요 작업 실행
        - 계좌 정보 조회
        - 웹소켓 연결 및 실시간 데이터 구독
        - 실시간 데이터 처리 및 거래 전략 실행
        """
        Account_detail(**self._info)
        self._ws, self._aes_key, self._aes_iv = Web_socket_connect(self._info, self._stock_list)

        while True:
            t_now = datetime.datetime.now()
            t_market_open = t_now.replace(hour=9, minute=0, second=0)
            t_liquidation = t_now.replace(hour=15, minute=21, second=00)
            t_15_20 = t_now.replace(hour=15, minute=20, second=0)
            t_15_30 = t_now.replace(hour=15, minute=30, second=0)
            t_market_closed = t_now.replace(hour=15, minute=40, second=0)
            t_exit = t_now.replace(hour=15, minute=40, second=0)

            # 청산 시간 체크
            if (t_now.hour == t_liquidation.hour) and (t_now.minute == t_liquidation.minute) and (t_now.second < 2):
                Liquidation(**self._info)
            else: pass

            # 계좌 정보 주기적 업데이트
            if t_market_open < t_now < t_market_closed:
                if (t_now.minute % 10) == 0 and (t_now.second < 1):
                    Account_detail(**self._info)
                else: pass
            else: pass

            # 실시간 데이터 처리
            data = self._ws.recv()

            if data[0] in ['0', '1']:
                if data[0] == '0':  # 실시간 호가/체결 데이터
                    recvstr = data.split('|')
                    trid0 = recvstr[1]
                    body_data = recvstr[3].split('^')
                    code = body_data[0]
                    self._Stock_Algo[code]._On_Realtime_Stock_Monitor(recvstr)
                elif data[0] == '1':  # 실시간 VI 데이터
                    recvstr = data.split('|')
                    trid0 = recvstr[1]
                    if trid0 in ["K0STCNI0", "K0STCNI9", "H0STCNI0", "H0STCNI9"]:
                        aes_dec_str = aes_cbc_base64_dec(self._aes_key, self._aes_iv, recvstr[3]).split('^')
                        code = aes_dec_str[8]
                        self._Stock_Algo[code]._Stock_Signal_Notice(aes_dec_str)
            else:
                # 웹소켓 연결 관련 응답 처리
                jsonObject = json.loads(data)
                trid = jsonObject["header"]["tr_id"]
                if trid != "PINGPONG":
                    rt_cd = jsonObject["body"]["rt_cd"]
                    if rt_cd == '1':
                        print("[%s] ERROR RETURN CODE [%s] MSG [%s]" % (self._info['NAME'], rt_cd, jsonObject["body"]["msg1"]))
                    elif rt_cd == '0':
                        print("[%s] RETURN CODE [%s] MSG [%s]" % (self._info['NAME'], rt_cd, jsonObject["body"]["msg1"]))
                        if trid == "K0STCNI0" or trid == "K0STCNI9" or trid == "H0STCNI0" or trid == "H0STCNI9":
                            self._aes_key = jsonObject["body"]["output"]["key"]
                            self._aes_iv = jsonObject["body"]["output"]["iv"]
                            print("[%s] TRID [%s] KEY[%s] IV[%s]" % (self._info['NAME'], trid, self._aes_key, self._aes_iv))
                elif trid == "PINGPONG":
                    print("[%s] RECV [%s]" % (self._info['NAME'], trid))
                    print("[%s] SEND [%s]" % (self._info['NAME'], trid))

def run_outer_worker(outer_worker):
    """
    워커 실행 및 예외 처리
    
    Args:
        outer_worker (OuterWorker): 실행할 워커 객체
    """
    try:
        outer_worker.do_work()
    except Exception as e:
        logging.error(f"Worker error: {e}")
        # 프로세스 재시작 로직
        time.sleep(5)
        run_outer_worker(outer_worker)

if __name__ == '__main__':
    # 종목 정보 초기화
    stockinfo_generation_on_trading()

    # 설정 파일 로드
    CONFIG_FILES_PATH = os.path.join(os.getcwd(), "CONFIG_FILES")
    CONFIG_FILES = os.listdir(CONFIG_FILES_PATH)

    # 계좌 정보 로드
    ACCOUNTS_INFO = {}
    for config_file in CONFIG_FILES:
        ACCOUNT = read_JSON(f'{CONFIG_FILES_PATH}/{config_file}')
        ACCOUNTS_INFO[ACCOUNT['NAME']] = ACCOUNT

    # print(ACCOUNTS_INFO)

    outer_workers = [OuterWorker(info=ACCOUNTS_INFO[ACCOUNT]) for ACCOUNT in ACCOUNTS_INFO.keys()]

    # 프로세스 실행
    processes = []
    try:
        for outer_worker in outer_workers:
            process = multiprocessing.Process(target=run_outer_worker, args=(outer_worker,))
            processes.append(process)
            process.start()
        for process in processes:
            process.join()

    except KeyboardInterrupt:
        for process in processes:
            process.close()
            process.join()



