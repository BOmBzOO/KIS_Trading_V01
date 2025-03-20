"""
다중 프로세싱을 위한 유틸리티 함수들을 포함하는 모듈
웹소켓 연결, 계좌 정보 조회, 파일 관리 등의 기능을 담당

주요 기능:
1. 웹소켓 연결 및 실시간 데이터 구독
2. 계좌 정보 조회 및 표시
3. 파일 시스템 관리 (JSON 파일 읽기/쓰기)
4. 메시지 전송 (Discord)
"""

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
    """
    YAML 설정 파일을 읽어서 API 접속 정보를 반환
    
    Args:
        filename (str): 설정 파일 경로
        
    Returns:
        dict: API 접속 정보 딕셔너리
    """
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
    """
    계좌 상세 정보를 조회하고 Discord로 전송
    
    Args:
        NAME (str): 계좌 이름
        URL_BASE (str): API 기본 URL
        APP_KEY (str): API 앱 키
        APP_SECRET (str): API 앱 시크릿
        ACCESS_TOKEN (str): API 접근 토큰
        CANO (str): 계좌 번호
        ACNT_PRDT_CD (str): 계좌 상품 코드
        DISCORD_WEBHOOK_URL (str): Discord 웹훅 URL
    """
    now = datetime.datetime.now()
    time = f"[{now.strftime('%H:%M:%S')}]"
    name = f"@ {NAME}"
    
    # 주문 가능 금액 조회
    res = inquire_psbl_order(URL_BASE, APP_KEY, APP_SECRET, ACCESS_TOKEN, CANO, ACNT_PRDT_CD)
    cash = res.json()['output']['ord_psbl_cash']
    available_cash = '{0:<18} {1:>20,}'.format('Available Balance:', int(cash))
    
    # 계좌 잔고 조회
    res = inquire_balance(URL_BASE, APP_KEY, APP_SECRET, ACCESS_TOKEN, CANO, ACNT_PRDT_CD)
    stock_list = res.json()['output1']
    evaluation = res.json()['output2'] 

    double_line = "=" * (40)
    single_line = "-" * (40)

    # 보유 종목 정보 생성
    stocks_balance = ''
    for stock in stock_list:
        if int(stock['hldg_qty']) > 0:
            stock_balance = '{}{}({}):  {}주  {}%'.format('+ ',stock['prdt_name'], stock['pdno'], stock['hldg_qty'], stock['evlu_pfls_rt'])
            stocks_balance = stocks_balance + '\n' + stock_balance
    
    # 평가 정보 생성
    evaluation_amount = '{0:<18} {1:>20,}'.format('Evaluation Amount:', int(evaluation[0]['scts_evlu_amt']))
    profits = '{0:<18} {1:>20,}'.format('Profits:', int(evaluation[0]['evlu_pfls_smtl_amt']))
    total_balance = '{0:<18} {1:>20,}'.format('Total Balance: ', int(evaluation[0]['tot_evlu_amt']))
    
    # 메시지 생성 및 전송
    MESSAGE ='\n'+time+'\n'+name+'\n'+double_line+'\n'+available_cash+stocks_balance+'\n'+single_line+'\n'+evaluation_amount+'\n'+profits+'\n'+total_balance+'\n'+double_line
    Send_message(DISCORD_WEBHOOK_URL, msg=MESSAGE, timestamp='False')

def Get_balance(NAME, URL_BASE, APP_KEY, APP_SECRET, ACCESS_TOKEN, CANO, ACNT_PRDT_CD, DISCORD_WEBHOOK_URL, **arg):
    """
    주문 가능 금액을 조회하고 Discord로 전송
    
    Args:
        NAME (str): 계좌 이름
        URL_BASE (str): API 기본 URL
        APP_KEY (str): API 앱 키
        APP_SECRET (str): API 앱 시크릿
        ACCESS_TOKEN (str): API 접근 토큰
        CANO (str): 계좌 번호
        ACNT_PRDT_CD (str): 계좌 상품 코드
        DISCORD_WEBHOOK_URL (str): Discord 웹훅 URL
        
    Returns:
        str: 주문 가능 금액
    """
    res = inquire_psbl_order(URL_BASE, APP_KEY, APP_SECRET, ACCESS_TOKEN, CANO, ACNT_PRDT_CD,  **arg)
    cash = res.json()['output']['ord_psbl_cash']
    Send_message(DISCORD_WEBHOOK_URL, msg='{0}'.format(NAME))
    Send_message(DISCORD_WEBHOOK_URL, msg="=" * (40), timestamp='False')
    Send_message(DISCORD_WEBHOOK_URL, msg='{0:<18} {1:>20,}'.format('Available Balance:', int(cash)), timestamp='False')
    return cash

def Get_stock_balance(URL_BASE, APP_KEY, APP_SECRET, ACCESS_TOKEN, CANO, ACNT_PRDT_CD, DISCORD_WEBHOOK_URL, **arg):
    """
    보유 종목 정보를 조회하고 Discord로 전송
    
    Args:
        URL_BASE (str): API 기본 URL
        APP_KEY (str): API 앱 키
        APP_SECRET (str): API 앱 시크릿
        ACCESS_TOKEN (str): API 접근 토큰
        CANO (str): 계좌 번호
        ACNT_PRDT_CD (str): 계좌 상품 코드
        DISCORD_WEBHOOK_URL (str): Discord 웹훅 URL
        
    Returns:
        dict: 보유 종목 정보 딕셔너리
    """
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
    """
    시장 운영 상태 확인
    
    Args:
        URL_BASE (str): API 기본 URL
        APP_KEY (str): API 앱 키
        APP_SECRET (str): API 앱 시크릿
        ACCESS_TOKEN (str): API 접근 토큰
        DISCORD_WEBHOOK_URL (str): Discord 웹훅 URL
        
    Returns:
        bool: 시장 운영 여부
    """
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
    """
    보유 종목 청산 실행
    
    Args:
        URL_BASE (str): API 기본 URL
        APP_KEY (str): API 앱 키
        APP_SECRET (str): API 앱 시크릿
        ACCESS_TOKEN (str): API 접근 토큰
        CANO (str): 계좌 번호
        ACNT_PRDT_CD (str): 계좌 상품 코드
        DISCORD_WEBHOOK_URL (str): Discord 웹훅 URL
    """
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
    """
    Discord로 메시지 전송
    
    Args:
        DISCORD_WEBHOOK_URL (str): Discord 웹훅 URL
        msg (str): 전송할 메시지
        timestamp (str): 타임스탬프 포함 여부 ('True'/'False')
    """
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
    """
    한국투자증권 웹소켓 연결 및 실시간 데이터 구독을 설정하는 함수
    
    Args:
        info (dict): API 접속 정보 (APPROVAL_KEY, URL_BASE, HTS_ID 등)
        stock_infos (dict): 모니터링할 종목 정보
    
    Returns:
        tuple: (websocket 객체, AES 암호화 키, AES 초기화 벡터)
    """
    # 웹소켓 구독할 TR 목록 초기화
    code_list_websocket = []
    
    # 모의투자/실전투자 구분하여 웹소켓 연결 TR 설정
    if info['URL_BASE'] == "https://openapivts.koreainvestment.com:29443":  # 모의투자
        code_list_websocket.append(['1','H0STCNI9', info['HTS_ID']])
    else:  # 실전투자
        code_list_websocket.append(['1','H0STCNI0', info['HTS_ID']])
        
    # 각 종목별 실시간 데이터 구독 TR 추가
    for sym in stock_infos.keys():
        code_list_websocket.append(['1','H0STASP0',sym])  # 실시간 호가
        code_list_websocket.append(['1','H0STCNT0',sym])  # 실시간 체결
        code_list_websocket.append(['1','H0STVI0',sym])   # 실시간 VI 정보

    # 웹소켓 연결 요청 데이터 생성
    senddata_list=[]
    for i,j,k in code_list_websocket:
        # TR 요청 데이터 포맷: tr_type, tr_id, tr_key
        temp = '{"header":{"approval_key": "%s","custtype":"P","tr_type":"%s","content-type":"utf-8"},"body":{"input":{"tr_id":"%s","tr_key":"%s"}}}'%(info['APPROVAL_KEY'],i,j,k)
        senddata_list.append(temp)
        time.sleep(0.2)  # API 호출 간격 조절

    # 기존 웹소켓 연결 종료
    try: 
        ws.close()
    except: 
        pass

    # 새로운 웹소켓 연결 생성
    ws = websocket.WebSocket()
    ws.connect(info['SOCKET_URL'], ping_interval=60)  # 60초마다 ping 전송

    # 각 TR 요청 데이터 전송 및 응답 처리
    for senddata in senddata_list:
        try: 
            ws.send(senddata)  # TR 요청 전송
            data = ws.recv()   # 응답 수신
            
            # 실시간 데이터인 경우 처리하지 않음
            if data[0] == '0' or data[0] == '1':
                pass
            else:
                # JSON 응답 파싱
                jsonObject = json.loads(data)
                trid = jsonObject["header"]["tr_id"]
                
                # PINGPONG이 아닌 경우 처리
                if trid != "PINGPONG":
                    rt_cd = jsonObject["body"]["rt_cd"]
                    if rt_cd == '1':    # 에러 응답 처리
                        print("[%s] ERROR RETURN CODE [%s] MSG [%s]" % (info['NAME'], rt_cd, jsonObject["body"]["msg1"]))
                    elif rt_cd == '0':  # 정상 응답 처리
                        print("[%s] RETURN CODE [%s] MSG [%s]" % (info['NAME'], rt_cd, jsonObject["body"]["msg1"]))
                        # 웹소켓 연결 키 발급 TR인 경우
                        if trid == "K0STCNI0" or trid == "K0STCNI9" or trid == "H0STCNI0" or trid == "H0STCNI9":
                            aes_key = jsonObject["body"]["output"]["key"]    # AES 암호화 키
                            aes_iv = jsonObject["body"]["output"]["iv"]      # AES 초기화 벡터
                            print("[%s] TRID [%s] KEY[%s] IV[%s]" % (info['NAME'], trid, aes_key, aes_iv))
                # PINGPONG 메시지 처리
                elif trid == "PINGPONG":
                    print("[%s] RECV [%s]" % (info['NAME'], trid))
                    print("[%s] SEND [%s]" % (info['NAME'], trid))
        except Exception as e: 
            print(e)
    
    return ws, aes_key, aes_iv  # 웹소켓 객체와 암호화 키 반환
  
def write_JSON(data, file_name, sort_key=True):
    """
    JSON 파일로 데이터 저장
    
    Args:
        data (dict): 저장할 데이터
        file_name (str): 파일 경로
        sort_key (bool): 키 정렬 여부
    """
    with open(file_name, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent="\t", sort_keys=sort_key)

def read_JSON(filename):
    """
    JSON 파일에서 데이터 읽기
    
    Args:
        filename (str): 파일 경로
        
    Returns:
        dict: 읽은 데이터
    """
    with open(filename, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data

def delete_JSON(filename):
    """
    JSON 파일 삭제
    
    Args:
        filename (str): 파일 경로
    """
    try:
        os.remove(filename)
    except OSError as e:
        print("Error: %s : %s" % (filename, e.strerror))

def create_Folder(DIR):
    """
    디렉토리 생성
    
    Args:
        DIR (str): 디렉토리 경로
    """
    try:
        if not os.path.exists(DIR):
            os.makedirs(DIR)
    except OSError:
        print ('Error: Creating directory. ' + DIR)

def delete_Folder(DIR):
    """
    디렉토리 또는 파일 삭제
    
    Args:
        DIR (str): 삭제할 경로
    """
    if os.path.isfile(DIR):
        os.remove(DIR)
    elif os.path.isdir(DIR):
        shutil.rmtree(DIR)
    else:
        pass
    




