import websocket
import shutil
import json
import requests
import time
import Crypto
import sys
import asyncio
sys.modules['Crypto'] = Crypto
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from base64 import b64decode
import requests
import json
import datetime
import time
from pprint import pprint
import yaml
import logging
from tr_functions import *

logger = logging.getLogger()

def import_CONFIG(filename):
    info = {}
    with open(filename, encoding='UTF-8') as f:
        _cfg = yaml.load(f, Loader=yaml.FullLoader)
        info['NAME'] = _cfg['NAME']
        info['APP_KEY'] = _cfg['APP_KEY']
        info['APP_SECRET'] = _cfg['APP_SECRET']
        info['ACCESS_TOKEN'] = None
        info['APPROVAL_KEY'] = None
        info['CANO'] = _cfg['CANO']
        info['ACNT_PRDT_CD'] = _cfg['ACNT_PRDT_CD']
        info['DISCORD_WEBHOOK_URL'] = _cfg['DISCORD_WEBHOOK_URL']
        info['URL_BASE'] = _cfg['URL_BASE']
        info['SOCKET_URL'] = _cfg['SOCKET_URL']
        info['HTS_ID'] = _cfg['HTS_ID']
    return info

def Account_detail(NAME, URL_BASE, APP_KEY, APP_SECRET, ACCESS_TOKEN, CANO, ACNT_PRDT_CD, DISCORD_WEBHOOK_URL, **arg):
    now = datetime.datetime.now()
    time = f"[{now.strftime('%H:%M:%S')}]"
    name = f"@ {NAME}"
    
    res = inquire_psbl_order(URL_BASE, APP_KEY, APP_SECRET, ACCESS_TOKEN, CANO, ACNT_PRDT_CD)
    cash = res.json()['output']['ord_psbl_cash']
    available_cash = '{0:<18} {1:>20,}'.format('Available Balance:', int(cash))
    
    res = inquire_balance(URL_BASE, APP_KEY, APP_SECRET, ACCESS_TOKEN, CANO, ACNT_PRDT_CD)
    stock_list = res.json()['output1']
    evaluation = res.json()['output2'] 

    double_line = "=" * (40)
    single_line = "-" * (40)

    stocks_balance = ''
    for stock in stock_list:
        if int(stock['hldg_qty']) > 0:
            stock_balance = '{}{}({}):  {}주  {}%'.format('+ ',stock['prdt_name'], stock['pdno'], stock['hldg_qty'], stock['evlu_pfls_rt'])
            stocks_balance = stocks_balance + '\n' + stock_balance
    
    evaluation_amount = '{0:<18} {1:>20,}'.format('Evaluation Amount:', int(evaluation[0]['scts_evlu_amt']))
    profits = '{0:<18} {1:>20,}'.format('Profits:', int(evaluation[0]['evlu_pfls_smtl_amt']))
    total_balance = '{0:<18} {1:>20,}'.format('Total Balance: ', int(evaluation[0]['tot_evlu_amt']))
    
    MESSAGE ='\n'+time+'\n'+name+'\n'+double_line+'\n'+available_cash+stocks_balance+'\n'+single_line+'\n'+evaluation_amount+'\n'+profits+'\n'+total_balance+'\n'+double_line
    Send_message(DISCORD_WEBHOOK_URL, msg=MESSAGE, timestamp='False')


def Get_balance(NAME, URL_BASE, APP_KEY, APP_SECRET, ACCESS_TOKEN, CANO, ACNT_PRDT_CD, DISCORD_WEBHOOK_URL, **arg):
    res = inquire_psbl_order(URL_BASE, APP_KEY, APP_SECRET, ACCESS_TOKEN, CANO, ACNT_PRDT_CD,  **arg)
    cash = res.json()['output']['ord_psbl_cash']
    Send_message(DISCORD_WEBHOOK_URL, msg='{0}'.format(NAME))
    Send_message(DISCORD_WEBHOOK_URL, msg="=" * (40), timestamp='False')
    Send_message(DISCORD_WEBHOOK_URL, msg='{0:<18} {1:>20,}'.format('Available Balance:', int(cash)), timestamp='False')
    return cash

def Get_stock_balance(URL_BASE, APP_KEY, APP_SECRET, ACCESS_TOKEN, CANO, ACNT_PRDT_CD, DISCORD_WEBHOOK_URL, **arg):
    res = inquire_balance(URL_BASE, APP_KEY, APP_SECRET, ACCESS_TOKEN, CANO, ACNT_PRDT_CD)
    stock_list = res.json()['output1']
    evaluation = res.json()['output2']  
    stock_dict = {}
    for stock in stock_list:
        if int(stock['hldg_qty']) > 0:
            stock_dict[stock['pdno']] = stock['hldg_qty']
            Send_message(DISCORD_WEBHOOK_URL, msg='{0:<2}{1}({2}): {3}주 {4}%'.format('+ ',stock['prdt_name'], stock['pdno'], stock['hldg_qty'], stock['evlu_pfls_rt']), timestamp='False')
    Send_message(DISCORD_WEBHOOK_URL, msg="-" * (40), timestamp='False')
    Send_message(DISCORD_WEBHOOK_URL, msg='{0:<18} {1:>20,}'.format('Evaluation Amount:', int(evaluation[0]['scts_evlu_amt'])), timestamp='False')
    Send_message(DISCORD_WEBHOOK_URL, msg='{0:<18} {1:>20,}'.format('Profits:', int(evaluation[0]['evlu_pfls_smtl_amt'])), timestamp='False')
    Send_message(DISCORD_WEBHOOK_URL, msg='{0:<18} {1:>20,}'.format('Total Balance: ', int(evaluation[0]['tot_evlu_amt'])), timestamp='False')
    Send_message(DISCORD_WEBHOOK_URL, msg="=" * (40), timestamp='False')
    return stock_dict

def Market_open(URL_BASE, APP_KEY, APP_SECRET, ACCESS_TOKEN, DISCORD_WEBHOOK_URL, **arg):
    t_now = datetime.datetime.now()
    t_exit = t_now.replace(hour=15, minute=40, second=0, microsecond=0)

    if t_exit < t_now:  # PM 03:20 ~ :프로그램 종료
        Send_message(DISCORD_WEBHOOK_URL, msg="Market_Time_Over")
        return False
    elif (check_holiday(URL_BASE, APP_KEY, APP_SECRET, ACCESS_TOKEN)['output'][0]['opnd_yn'] == 'N'):  # 토요일이나 일요일이면 자동 종료
        Send_message(DISCORD_WEBHOOK_URL, msg="Market_Closed")
        return False
    else:
        return True

def Liquidation(URL_BASE, APP_KEY, APP_SECRET, ACCESS_TOKEN, CANO, ACNT_PRDT_CD, DISCORD_WEBHOOK_URL, **arg):
    liquidation_stocks = []
    for stock in inquire_balance(URL_BASE, APP_KEY, APP_SECRET, ACCESS_TOKEN, CANO, ACNT_PRDT_CD).json()['output1']:
        if int(stock['hldg_qty']) >= 1 and int(stock['thdt_buyqty']) < 1 : # 금일 매수가 아니면서 position이 있으면
            liquidation_stocks.append(stock['pdno'])
            # print(stock['prdt_name'], stock['pdno'],  stock['hldg_qty'])
            order_cash_Sell(URL_BASE, APP_KEY, APP_SECRET, ACCESS_TOKEN, CANO, ACNT_PRDT_CD, code=stock['pdno'], qty=stock['hldg_qty'], price="0", side='market')
            MESSAGE = f"[청산] %s(%s) %s주" % (stock['prdt_name'], stock['pdno'], stock['hldg_qty'])
            Send_message(DISCORD_WEBHOOK_URL, msg=MESSAGE)
        else: pass

    if len(liquidation_stocks) == 0:
        MESSAGE = f"[청산] 청산할 종목이 없습니다."
        Send_message(DISCORD_WEBHOOK_URL, msg=MESSAGE)
    else: pass

def Send_message(DISCORD_WEBHOOK_URL, msg, timestamp='True', **arg):
    now = datetime.datetime.now()
    if timestamp == 'True':
        message = f"[{now.strftime('%H:%M:%S')}] {str(msg)}"
        message_discode = {"content": message}
    elif timestamp == 'False':
        message = f"{str(msg)}"
        message_discode = {"content": message}
    else: pass
    requests.post(DISCORD_WEBHOOK_URL, data=message_discode)
    print(message)

def Web_socket_connect(info, stock_infos):
    code_list_websocket = []
    if info['URL_BASE'] == "https://openapivts.koreainvestment.com:29443":
        code_list_websocket.append(['1','H0STCNI9', info['HTS_ID']])
    else:
        code_list_websocket.append(['1','H0STCNI0', info['HTS_ID']])
    for sym in stock_infos.keys():
        code_list_websocket.append(['1','H0STASP0',sym])
        code_list_websocket.append(['1','H0STCNT0',sym])

    senddata_list=[]
    for i,j,k in code_list_websocket:
        temp = '{"header":{"approval_key": "%s","custtype":"P","tr_type":"%s","content-type":"utf-8"},"body":{"input":{"tr_id":"%s","tr_key":"%s"}}}'%(info['APPROVAL_KEY'],i,j,k)
        senddata_list.append(temp)
        time.sleep(0.2)
    try: 
        ws.close()
    except: 
        pass
    ws = websocket.WebSocket()
    ws.connect(info['SOCKET_URL'], ping_interval=60)
    for senddata in senddata_list:
        try: 
            ws.send(senddata)
            data = ws.recv()
            if data[0] == '0' or data[0] == '1':  # 실시간 데이터일 경우
                pass
            else:
                jsonObject = json.loads(data)
                trid = jsonObject["header"]["tr_id"]
                if trid != "PINGPONG":
                    rt_cd = jsonObject["body"]["rt_cd"]
                    if rt_cd == '1':    # 에러일 경우 처리
                        print("[%s] ERROR RETURN CODE [%s] MSG [%s]" % (info['NAME'], rt_cd, jsonObject["body"]["msg1"]))
                    elif rt_cd == '0':  # 정상일 경우 처리
                        print("[%s] RETURN CODE [%s] MSG [%s]" % (info['NAME'], rt_cd, jsonObject["body"]["msg1"]))
                        if trid == "K0STCNI0" or trid == "K0STCNI9" or trid == "H0STCNI0" or trid == "H0STCNI9":
                            aes_key = jsonObject["body"]["output"]["key"]
                            aes_iv = jsonObject["body"]["output"]["iv"]
                            print("[%s] TRID [%s] KEY[%s] IV[%s]" % (info['NAME'], trid, aes_key, aes_iv))
                elif trid == "PINGPONG":
                    print("[%s] RECV [%s]" % (info['NAME'], trid))
                    print("[%s] SEND [%s]" % (info['NAME'], trid))
        except Exception as e: 
            print(e)
    return ws, aes_key, aes_iv
  
def write_JSON(data, file_name, sort_key=True):
    with open(file_name, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent="\t", sort_keys=sort_key)

def read_JSON(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data

def delete_JSON(filename):
    try:
        os.remove(filename)
    except OSError as e:
        print("Error: %s : %s" % (filename, e.strerror))

def create_Folder(DIR):
    try:
        if not os.path.exists(DIR):
            os.makedirs(DIR)
    except OSError:
        print ('Error: Creating directory. ' + DIR)

def delete_Folder(DIR):
    if os.path.isfile(DIR):
        os.remove(DIR)
    elif os.path.isdir(DIR):
        shutil.rmtree(DIR)
    else:
        pass
    




