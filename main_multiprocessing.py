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

# 로깅 추가
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
    Trading_Algo = {}
    for code in stock_infos.keys():
        algo = STRATEGY(info, code=code)
        Trading_Algo[code] = algo
    return Trading_Algo

class OuterWorker:
    def __init__(self, info):
        self._info = info
        self._info_path = self._info['INFO_PATH'] = os.path.join(os.getcwd(), "ID_ACCOUNT", self._info['NAME'])
        self._stock_dir_path = self._info['STOCKS_DIR_PATH'] = os.path.join(self._info['INFO_PATH'], "stocks")
        self._stock_list = read_JSON(f'{self._info_path}/stocksinfo_TOTAL.json')

        delete_Folder(self._info['STOCKS_DIR_PATH'])
        create_Folder(self._info['STOCKS_DIR_PATH'])
        for stock in self._stock_list.keys():
            write_JSON(self._stock_list[stock], f'{self._stock_dir_path}/{stock}.json')

        self._Stock_Algo = Assign_Trading_Algorithm_To_Stock(self._info, self._stock_list) # 각각의 주식 종목당 정해진 트레이딩 알고리즘 배정
  
    def do_work(self):

        Account_detail(**self._info)
        self._ws, self._aes_key, self._aes_iv = Web_socket_connect(self._info, self._stock_list)

        while True:
            # try:
                t_now = datetime.datetime.now()
                t_market_open = t_now.replace(hour=9, minute=0, second=0)
                t_liquidation = t_now.replace(hour=15, minute=21, second=00)
                t_15_20 = t_now.replace(hour=15, minute=20, second=0)
                t_15_30 = t_now.replace(hour=15, minute=30, second=0)
                t_market_closed = t_now.replace(hour=15, minute=40, second=0)
                t_exit = t_now.replace(hour=15, minute=40, second=0)

                if (t_now.hour == t_liquidation.hour) and (t_now.minute == t_liquidation.minute) and (t_now.second < 2):
                    Liquidation(**self._info)
                else: pass

                if t_market_open < t_now < t_market_closed:
                    if (t_now.minute % 10) == 0 and (t_now.second < 1):
                        Account_detail(**self._info)
                    else: pass
                else: pass

                data = self._ws.recv()

                if data[0] in ['0', '1']:
                    if data[0] == '0':
                        recvstr = data.split('|')
                        trid0 = recvstr[1]
                        body_data = recvstr[3].split('^')
                        code = body_data[0]
                        # STRATEGY(self._info, code=code)._On_Realtime_Stock_Monitor(recvstr)
                        self._Stock_Algo[code]._On_Realtime_Stock_Monitor(recvstr)
                    elif data[0] == '1':
                        recvstr = data.split('|')
                        trid0 = recvstr[1]
                        if trid0 in ["K0STCNI0", "K0STCNI9", "H0STCNI0", "H0STCNI9"]:
                            aes_dec_str = aes_cbc_base64_dec(self._aes_key, self._aes_iv, recvstr[3]).split('^')
                            code = aes_dec_str[8]
                            # STRATEGY(self._info, code=code)._Stock_Signal_Notice(aes_dec_str)
                            self._Stock_Algo[code]._Stock_Signal_Notice(aes_dec_str)
                else:
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
            # except Exception as e:
            #     print(f"Exception in do_work: {e}")

def run_outer_worker(outer_worker):
    try:
        outer_worker.do_work()
    except Exception as e:
        logging.error(f"Worker error: {e}")
        # 프로세스 재시작 로직 추가
        time.sleep(5)
        run_outer_worker(outer_worker)

if __name__ == '__main__':

    stockinfo_generation_on_trading()

    CONFIG_FILES_PATH = os.path.join(os.getcwd(), "CONFIG_FILES")
    CONFIG_FILES = os.listdir(CONFIG_FILES_PATH)

    ACCOUNTS_INFO = {}
    for config_file in CONFIG_FILES:
        ACCOUNT = read_JSON(f'{CONFIG_FILES_PATH}/{config_file}')
        ACCOUNTS_INFO[ACCOUNT['NAME']] = ACCOUNT

    # print(ACCOUNTS_INFO)

    outer_workers = [OuterWorker(info=ACCOUNTS_INFO[ACCOUNT]) for ACCOUNT in ACCOUNTS_INFO.keys()]

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



