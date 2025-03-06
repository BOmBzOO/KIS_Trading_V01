import os
import re
import json
import math
import time
import logging
import datetime
import pandas as pd
from pprint import pprint
from selenium import webdriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
# from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from tr_functions import get_access_TOKEN, get_approval, inquire_balance, inquire_psbl_order, inquire_price, inquire_daily_price, inquire_daily_itemchartprice
from utility_asycio import import_CONFIG, read_JSON, write_JSON, Send_message, create_Folder, delete_Folder

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

        self._info['ACCESS_TOKEN'] = get_access_TOKEN(**self._info) # API 토큰 발급
        self._info['APPROVAL_KEY'] = get_approval(**self._info) # 웹소켓 키 발급
        write_JSON(self._info, f'{self._directory}/info.json')
   
    def _get_stockinfo_ACCOUNT(self):
        self._stocks_account = inquire_balance(**self._info).json()['output1']
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
                    data_account[code]['pvt_scnd_dmrs_prc'] = inquire_price(**self._info, code=code).json()['output']['pvt_scnd_dmrs_prc']
                    data_account[code]['sell_price_cal'] = math.trunc(float(self._stocks_account[idx]['pchs_avg_pric'])*(1 + float(self._sell_target_percent)))
                    data_account[code]['sell_price_modi'] = str(min([int(data_account[code]['pvt_scnd_dmrs_prc']), data_account[code]['sell_price_cal']]))
                    data_account[code]['time_liquidation'] = str(self._t_liquidation)
            else: pass
                
        write_JSON(data_account, f'{self._directory}/stockinfo_ACCOUNT.json')
        return data_account

    def _get_stockinfo_GENPORT(self, genport_1to50_selected, num_tobuy):
        # self._stocks_1to50 = pd.read_csv('./NEWSYSTOCK/stockinfo_GENPORT_1to50.csv', dtype=str)

        t_now = datetime.datetime.now()
        t_market_open = t_now.replace(hour=9, minute=00, second=00, microsecond=00)
        t_15_20 = t_now.replace(hour=15, minute=20, second=00, microsecond=00)
        t_15_30 = t_now.replace(hour=15, minute=30, second=00, microsecond=00)
        t_00_01 = t_now.replace(hour=00, minute=00, second=1, microsecond=00)
        t_market_closed = t_now.replace(hour=15, minute=40, second=00, microsecond=00)
    
        self._total_balance = inquire_balance(**self._info).json()['output2'][0]['tot_evlu_amt'] 
        self._buy_amount = math.trunc(int(self._total_balance)/10.5)

        today = f"[{t_now.strftime('%H%M%S')}]"
        stock_info = {}
        # for name, code, priority in genport_1to50_selected:           
        #     stock = inquire_daily_itemchartprice(**self._info, code=code, start=today, end=today, D_W_M="D", adj="0").json()['output']

        #     # # 전일종가 값을 가져옴
        #     # if t_now < t_market_open < t_market_closed:
        #     #     전일종가 = stock[0]['stck_clpr'] # market 시작전
        #     # else:
        #     #     전일종가 = stock[1]['stck_clpr'] # market 시작후


        for name, code, priority in genport_1to50_selected:           
            stock = inquire_daily_itemchartprice(**self._info, code=code, start=today, end=today, D_W_M="D", adj="0").json()

            # 전일종가 값을 가져옴
            if t_now <= t_market_open:
                전일종가 = stock['output2']['stck_clpr'] # am00-am09
            else:
                전일종가 = stock['output1']['stck_prdy_clpr'] # am09-pm24

            # # 전일종가 값을 가져옴
            # if t_now <= t_market_open:
            #     전일종가 = stock[0]['stck_clpr'] # am00-am09
            # else:
            #     전일종가 = stock[1]['stck_clpr'] # am09-pm24
            
            buy_price_ori = str(math.trunc(float(전일종가)*(1 + float(self._buy_target_percent))))
            buy_qty_ori = str(math.trunc(float(self._buy_amount)/float(buy_price_ori)))
            sell_price_ori = str(math.trunc(float(buy_price_ori)*(1 + float(self._sell_target_percent))))
            
            if int(buy_qty_ori) >= 1 and len(stock_info.keys()) < num_tobuy:
                stock_info[code] = {}
                stock_info[code]['name'] = name
                stock_info[code]['code'] = code
                stock_info[code]['priority'] = priority
                stock_info[code]['buy_amount'] = str(self._buy_amount)
                stock_info[code]['buy_price_ori'] = buy_price_ori
                stock_info[code]['buy_price_modi'] = "0"
                stock_info[code]['buy_qty_ori'] = buy_qty_ori
                stock_info[code]['buy_qty_modi'] = "0"
                stock_info[code]['buy_qty_submitted'] = "0"
                stock_info[code]['sell_price_ori'] = sell_price_ori
                stock_info[code]['sell_price_modi'] = "0"
                stock_info[code]['bought_price_ave'] = "None"
                stock_info[code]['bought_day'] = "None"
                stock_info[code]['sell_target_percent'] = self._sell_target_percent           
                stock_info[code]['timepoint_trading_start'] = str(self._t_buy_start)
                stock_info[code]['timepoint_trading_end'] = str(self._t_trading_end)
                stock_info[code]['time_liquidation'] = "None"
                stock_info[code]['order_type'] = self._order_type

                stock_info[code]['state'] = "TO_BUY"
                MESSAGE = f' %s, %s (%s)' % (priority, name, code)
                # print(MESSAGE)
                Send_message(**self._info, msg=MESSAGE, timestamp='False')
                time.sleep(0.25)     
            else: break
        write_JSON(stock_info, f'{self._directory}/stockinfo_GENPORT.json', sort_key=False)
        return stock_info

    def _generation_stockinfo(self):
        self._stockinfo_tosell = self._get_stockinfo_ACCOUNT()
        num_tobuy = 10 - len(self._stockinfo_tosell.keys())

        genport_1to50 = pd.read_csv(f'./NEWSYSTOCK/stockinfo_GENPORT_1to50.csv', dtype=str)

        genport_1to50_selected = []
        for idx in range(len(genport_1to50)):
            # print(genport_1to50.loc[idx]['code'])
            if genport_1to50.loc[idx]['code'] not in self._stockinfo_tosell.keys():
                genport_1to50_selected.append([genport_1to50.loc[idx]['name'], genport_1to50.loc[idx]['code'], genport_1to50.loc[idx]['priority']])
            else: pass

        self._stockinfo_tobuy = self._get_stockinfo_GENPORT(genport_1to50_selected, num_tobuy)
        self._stockinfo_tobuy.update(self._stockinfo_tosell)
        write_JSON(self._stockinfo_tobuy, f'{self._directory}/stocksinfo_TOTAL.json')
        MESSAGE = f'[StockInfo Generated] %s' % (self._info['NAME'])
        Send_message(**self._info, msg=MESSAGE)

def divider(l, n):
    for i in range(0, len(l), n):
        yield(l[i:i+n])

def crowling_stockinfo_GENPORT_1to50():
    # # 옵션 생성
    # options = webdriver.ChromeOptions()
    # # 창 숨기는 옵션 추가
    # options.add_argument("headless")

    info_newsy = read_JSON("./NEWSYSTOCK/info_newsy.json")
    # driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()))
    service = Service()
    options = webdriver.ChromeOptions()
    driver = webdriver.Chrome(service=service, options=options)
    
    driver.implicitly_wait(3)
    driver.get(info_newsy['NEWSY_LOGIN_PATH'])
    driver.find_element(By.NAME, 'ctl00$ContentPlaceHolder1$loginID').send_keys('%s' % info_newsy['NEWSY_ID'])
    time.sleep(1)
    driver.find_element(By.NAME, 'ctl00$ContentPlaceHolder1$loginPWD').send_keys('%s' % info_newsy['NEWSY_PWD'])
    driver.find_element(By.XPATH, '//*[@id="ContentPlaceHolder1_btnLogin"]').click()
    time.sleep(3)
    driver.get(info_newsy['NEWSY_PORT_PATH'])
    driver.find_element(By.XPATH, '//*[@id="listAT4081978"]').click()
    time.sleep(10)
    element = driver.find_element(By.XPATH, '//*[@id="tabMenu4"]')
    print(element)
    driver.execute_script("arguments[0].click()", element)
    time.sleep(3)
    # elements = WebDriverWait(driver, 30).until(EC.presence_of_all_elements_located((By.XPATH, '//*[@id="PortManageSection4"]/div[3]/ul/table')))
    elements = WebDriverWait(driver, 40).until(EC.presence_of_all_elements_located((By.XPATH, '//*[@id="PortManageSection4"]/div[1]/ul/table')))

    temp = str('')
    for element in elements:
        string = element.text.replace(",","")
        temp += string  
    temp = temp.split()
    trade_list = list(divider(temp, 2))

    df = pd.DataFrame(trade_list, columns=['priority', 'Acode'])
    df[['priority', 'name']] = df['priority'].str.extract(r'(\d+)(\D+)')
    df['code'] = df['Acode'].str.extract(r'A(\d+)')
    df = df[['priority', 'name', 'code']]
    df.to_csv('./NEWSYSTOCK/stockinfo_GENPORT_1to50.csv')

def stockinfo_run():
    # crowling_stockinfo_GENPORT_1to50()
    ID_ACCOUNT_PATH = os.path.join(os.getcwd(), "ID_ACCOUNT")
    delete_Folder(ID_ACCOUNT_PATH)
    CONFIG_PATH = os.path.join(os.getcwd(), "CONFIG_FILES")
    config_files = os.listdir(CONFIG_PATH)
    # print(config_files)
    # print()
    for idx, config in enumerate(config_files):
        # print(idx, config_files[idx])
        info = import_CONFIG(f'{CONFIG_PATH}/{config}')
        MESSAGE = f'[%s]' % (info['NAME'])
        # print(MESSAGE)
        Send_message(**info, msg=MESSAGE)
        StockInfo_to_Trade(info)._generation_stockinfo()
        print()

if __name__ == '__main__':
    
    stockinfo_run()






