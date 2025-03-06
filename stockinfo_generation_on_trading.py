import os
import re
import json
import math
import time
import logging
import datetime
import pandas as pd
from pprint import pprint
# from selenium import webdriver
# from selenium.webdriver.support import expected_conditions as EC
# from selenium.webdriver.common.by import By
# from selenium.webdriver.support.ui import WebDriverWait
# from selenium.webdriver.chrome.service import Service as ChromeService
# from webdriver_manager.chrome import ChromeDriverManager
from tr_functions import get_access_TOKEN, get_approval, inquire_balance, inquire_psbl_order, inquire_price, inquire_daily_price, inquire_daily_itemchartprice
from utility_multiprocessing import import_CONFIG, read_JSON, write_JSON, Send_message, create_Folder, delete_Folder

logger = logging.getLogger()

class StockInfo_to_Trade:
    def __init__(self, info):
        self._info = info
        self._PATH = os.getcwd()
        self._l = logger.getChild(self._info['CANO'])
        self._directory = os.path.join(self._PATH, "ID_ACCOUNT", self._info['NAME'])
        create_Folder(self._directory)

        self._order_type = "market"
        self._buy_target_percent = "-0.02"
        self._sell_target_percent = "0.08"
        self._t_buy_start = datetime.datetime.now().replace(hour=9, minute=5, second=0).strftime("%Y-%m-%d %H:%M:%S")
        self._t_trading_end = datetime.datetime.now().replace(hour=15, minute=41, second=0).strftime("%Y-%m-%d %H:%M:%S")
        self._t_liquidation = datetime.datetime.now().replace(hour=15, minute=25, second=0).strftime("%Y-%m-%d %H:%M:%S")

        if not self._info.get('ACCESS_TOKEN') or self._is_token_expired():
            self._info['ACCESS_TOKEN'], self._info['ACCESS_TOKEN_TOKEN_EXPIRED'] = get_access_TOKEN(**self._info)  
            self._info['APPROVAL_KEY'] = get_approval(**self._info) 
            config_files_path = self._info.get('CONFIG_FILES_PATH')
            config_file = self._info.get('CONFIG_FILE')
            write_JSON(info, f'{config_files_path}/{config_file}')
        else:
            print("✅ 기존 토큰을 유지합니다.")

        print(self._info)

    def _get_stockinfo_ACCOUNT(self):
        try:
            balance_response = inquire_balance(**self._info).json()
            
            # 모의투자와 실전투자 구분
            if self._info['ACNT_TYPE'] == 'paper':
                if 'output1' in balance_response:
                    self._stocks_account = balance_response['output1']
                else:
                    self._stocks_account = balance_response.get('output', [])
            else:
                self._stocks_account = balance_response['output1']
                
            print(self._stocks_account)
            data_account = {}
                
            for idx in range(len(self._stocks_account)):
                if int(self._stocks_account[idx]['hldg_qty']) > 0:
                    code = self._stocks_account[idx]['pdno']
                    data_account[code] = {}
                    data_account[code]['name'] = self._stocks_account[idx]['prdt_name']
                    data_account[code]['code'] = self._stocks_account[idx]['pdno']
                    data_account[code]['priority'] = "None"
                    data_account[code]['buy_amount'] = "None"
                    data_account[code]['buy_price_ori'] = "0"
                    data_account[code]['buy_qty_ori'] = "0"
                    data_account[code]['buy_price_modi'] = "0"
                    data_account[code]['buy_qty_modi'] = "0"
                    data_account[code]['buy_qty_submitted'] = "0"
                    data_account[code]['sell_price_ori'] = "0"
                    data_account[code]['bought_price_ave'] = self._stocks_account[idx]['pchs_avg_pric']
                    data_account[code]['state'] = "TO_SELL"
                    data_account[code]['sell_target_percent'] = self._sell_target_percent
                    data_account[code]['positions'] = self._stocks_account[idx]['hldg_qty']
                    data_account[code]['timepoint_trading_start'] = str(self._t_buy_start)
                    data_account[code]['timepoint_trading_end'] = str(self._t_trading_end)
                    data_account[code]['order_type'] = self._order_type
                    if int(self._stocks_account[idx]['thdt_buyqty']) >= 1: # 금일 매수한 경우
                        data_account[code]['bought_day'] = "TODAY"
                        data_account[code]['sell_price_cal'] = math.trunc(float(self._stocks_account[idx]['pchs_avg_pric'])*(1 + float(self._sell_target_percent)))
                        data_account[code]['sell_price_modi'] = data_account[code]['sell_price_cal']
                        data_account[code]['time_liquidation'] = "None"
                    else: # 전일 매수한 경우
                        data_account[code]['bought_day'] = "YESTERDAY"
                        try:
                            price_response = inquire_price(**self._info, code=code).json()
                            if self._info['ACNT_TYPE'] == 'paper':
                                data_account[code]['pvt_scnd_dmrs_prc'] = price_response.get('output', {}).get('pvt_scnd_dmrs_prc', 0)
                            else:
                                data_account[code]['pvt_scnd_dmrs_prc'] = price_response['output']['pvt_scnd_dmrs_prc']
                        except Exception as e:
                            self._l.error(f"호가 정보 조회 중 오류 발생 ({code}): {e}")
                            data_account[code]['pvt_scnd_dmrs_prc'] = 0
                            
                        data_account[code]['sell_price_cal'] = math.trunc(float(self._stocks_account[idx]['pchs_avg_pric'])*(1 + float(self._sell_target_percent)))
                        data_account[code]['sell_price_modi'] = str(min([int(data_account[code]['pvt_scnd_dmrs_prc']), data_account[code]['sell_price_cal']]))
                        data_account[code]['time_liquidation'] = str(self._t_liquidation)
                else: pass
                    
            write_JSON(data_account, f'{self._directory}/stockinfo_ACCOUNT.json')
            return data_account
            
        except Exception as e:
            self._l.error(f"계좌 정보 조회 중 오류 발생: {e}")
            return {}

    def _get_stockinfo_GENPORT(self, genport_1to50_selected, num_tobuy):
        try:
            balance_response = inquire_balance(**self._info).json()
            
            # 모의투자와 실전투자 구분
            if self._info['ACNT_TYPE'] == 'paper':
                if 'output2' in balance_response:
                    self._total_balance = balance_response['output2'][0]['tot_evlu_amt']
                else:
                    self._total_balance = balance_response.get('output', [{}])[0].get('tot_evlu_amt', 0)
            else:
                self._total_balance = balance_response['output2'][0]['tot_evlu_amt']
                
            self._buy_amount = math.trunc(int(self._total_balance)/10.2)
            
            t_now = datetime.datetime.now()
            t_market_open = t_now.replace(hour=9, minute=00, second=00, microsecond=00)
            t_15_20 = t_now.replace(hour=15, minute=20, second=00, microsecond=00)
            t_15_30 = t_now.replace(hour=15, minute=30, second=00, microsecond=00)
            t_market_closed = t_now.replace(hour=15, minute=40, second=00, microsecond=00)

            today = f"[{t_now.strftime('%H%M%S')}]"
            stock_info = {}
            for name, code, priority in genport_1to50_selected:         
                try:
                    stock = inquire_daily_itemchartprice(**self._info, code=code, start=today, end=today, D_W_M="D", adj="0").json()
                    
                    # 전일종가 값을 가져옴
                    if t_now <= t_market_open:
                        if self._info['ACNT_TYPE'] == 'paper':
                            전일종가 = stock.get('output', {}).get('stck_clpr', 0)  # 모의투자
                        else:
                            전일종가 = stock['output2']['stck_clpr']  # 실전투자
                    else:
                        if self._info['ACNT_TYPE'] == 'paper':
                            전일종가 = stock.get('output', {}).get('stck_prdy_clpr', 0)  # 모의투자
                        else:
                            전일종가 = stock['output1']['stck_prdy_clpr']  # 실전투자
                    
                    if 전일종가 == 0:
                        self._l.warning(f"전일종가를 가져올 수 없음: {code}")
                        continue
                        
                    buy_price_ori = str(math.trunc(float(전일종가) * (1 + float(self._buy_target_percent))))
                    buy_qty_ori = str(math.trunc(float(self._buy_amount) / float(buy_price_ori)))
                    sell_price_ori = str(math.trunc(float(buy_price_ori) * (1 + float(self._sell_target_percent))))
                    
                    if int(buy_qty_ori) >= 1 and len(stock_info.keys()) < num_tobuy:
                        stock_info[code] = {
                            'name': name,
                            'code': code,
                            'priority': priority,
                            'buy_amount': str(self._buy_amount),
                            'buy_price_ori': buy_price_ori,
                            'buy_price_modi': "0",
                            'buy_qty_ori': buy_qty_ori,
                            'buy_qty_modi': "0",
                            'buy_qty_submitted': "0",
                            'sell_price_ori': sell_price_ori,
                            'sell_price_modi': "0",
                            'bought_price_ave': "None",
                            'bought_day': "None",
                            'sell_target_percent': self._sell_target_percent,           
                            'timepoint_trading_start': str(self._t_buy_start),
                            'timepoint_trading_end': str(self._t_trading_end),
                            'time_liquidation': "None",
                            'order_type': self._order_type,
                            'state': "TO_BUY"
                        }
                        Send_message(**self._info, msg=f'{priority}, {name} ({code}) 선택됨', timestamp='False')
                        time.sleep(1)
                    else:
                        break
                except Exception as e:
                    self._l.error(f"종목 정보 조회 중 오류 발생 ({code}): {e}")
                    continue
            
            write_JSON(stock_info, f'{self._directory}/stockinfo_GENPORT.json', sort_key=False)
            return stock_info
            
        except Exception as e:
            self._l.error(f"GENPORT 정보 생성 중 오류 발생: {e}")
            return {}

    def _generation_stockinfo(self):
        self._stockinfo_tosell = self._get_stockinfo_ACCOUNT()
        num_tobuy = 3 - len(self._stockinfo_tosell.keys())

        genport_1to50 = pd.read_csv(f'./NEWSYSTOCK/stockinfo_GENPORT_1to50.csv', dtype=str)

        genport_1to50_selected = []
        for idx in range(len(genport_1to50)):
            if genport_1to50.loc[idx]['code'] not in self._stockinfo_tosell.keys():
                genport_1to50_selected.append([genport_1to50.loc[idx]['name'], genport_1to50.loc[idx]['code'], genport_1to50.loc[idx]['priority']])
            else: pass

        self._stockinfo_tobuy = self._get_stockinfo_GENPORT(genport_1to50_selected, num_tobuy)
        self._stockinfo_tobuy.update(self._stockinfo_tosell)
        write_JSON(self._stockinfo_tobuy, f'{self._directory}/stocksinfo_TOTAL.json')
        MESSAGE = f'[Program Start] StockInfo regenerated(%s)' % (self._info['NAME'])
        Send_message(**self._info, msg=MESSAGE)
        
    def _is_token_expired(self):
        try:
            token_expiry = self._info.get('ACCESS_TOKEN_TOKEN_EXPIRED')
            if not token_expiry:
                return True
            if isinstance(token_expiry, str):
                token_expiry = datetime.datetime.strptime(token_expiry, "%Y-%m-%d %H:%M:%S")
            return token_expiry < datetime.datetime.now()
        except Exception as e:
            print(f"[Error] 토큰 만료 시간 확인 실패: {e}")
            return True  # 예외 발생 시 새 토큰 요청

def stockinfo_generation_on_trading():
    CONFIG_FILES_PATH = os.path.join(os.getcwd(), "CONFIG_FILES")

    if not os.path.exists(CONFIG_FILES_PATH):
        print(f"❌ 경로 없음: {CONFIG_FILES_PATH}")
        return   
    config_files = os.listdir(CONFIG_FILES_PATH)
    if not config_files:
        print(f"📂 {CONFIG_FILES_PATH} 폴더에 JSON 파일이 없습니다.")
        return
    for config_file in config_files:
        if not config_file.endswith(".json"):
            print(f"⚠️ 스킵됨 (JSON 아님): {config_file}")
            continue
        try:
            info = read_JSON(f'{CONFIG_FILES_PATH}/{config_file}')
            info['CONFIG_FILES_PATH'] = CONFIG_FILES_PATH
            info['CONFIG_FILE'] = config_file
        except Exception as e:
            print(f"❌ 오류 발생 ({config_file}): {e}")
        MESSAGE = f'[%s]' % (info['NAME'])
        Send_message(**info, msg=MESSAGE)
        StockInfo_to_Trade(info)._generation_stockinfo()

if __name__ == '__main__':
    stockinfo_generation_on_trading()
