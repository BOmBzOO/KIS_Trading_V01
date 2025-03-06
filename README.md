# KIS API 자동매매 시스템

한국투자증권 API를 활용한 자동매매 시스템입니다. 모의투자와 실전투자 계정을 모두 지원합니다.

## 주요 기능

- 실시간 주식 모니터링
- 자동 매수/매도 실행
- 멀티프로세싱을 통한 동시 계좌 운영
- Discord를 통한 거래 알림
- 모의투자/실전투자 계정 지원

## 시스템 요구사항

- Python 3.8 이상
- Windows 10/11
- 한국투자증권 계정 (모의투자 또는 실전투자)

## 설치 방법

1. 저장소 클론
```bash
git clone [repository-url]
cd [repository-name]
```

2. 가상환경 생성 및 활성화
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

3. 필요한 패키지 설치
```bash
pip install -r requirements.txt
```

## 설정 방법

1. `CONFIG_FILES` 디렉토리에 계정 설정 파일 생성
   - 모의투자: `paper_account.json`
   - 실전투자: `live_account.json`

2. 설정 파일 형식
```json
{
    "NAME": "계좌명",
    "ACNT_TYPE": "paper",  // paper 또는 live
    "CANO": "계좌번호",
    "ACNT_PRDT_CD": "01",
    "APP_KEY": "앱키",
    "APP_SECRET": "앱시크릿",
    "DISCORD_WEBHOOK_URL": "디스코드 웹훅 URL"
}
```

## 사용 방법

1. 프로그램 실행
```bash
python main_multiprocessing.py
```

2. 거래 모니터링
- Discord를 통해 실시간 거래 알림 확인
- `ID_ACCOUNT/[계좌명]` 디렉토리에서 거래 정보 확인

## 주의사항

- API 키와 시크릿은 절대 공개되지 않도록 주의
- 실전투자 시 충분한 테스트 후 사용 권장
- 거래 시간 외에는 프로그램을 종료하는 것을 권장

## 라이선스

이 프로젝트는 MIT 라이선스를 따릅니다.

## 기여 방법

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 문의

문제가 발생하거나 문의사항이 있으시면 이슈를 생성해주세요.

## 폴더 생성필요

1. CONFIG_FILES 생성 후
- infomation.yaml

#### PAPER Account
```
NAME: "gildong_509543433_paper"
APP_KEY: "PSaOefdskaflsdjffkds;lafkds;lfkrruFcN7mgHgrYuus"
APP_SECRET: "ImKZdYxKL/4b8JhcgjdsajlfkjjgklsafjdslkfjsdklfjsglajladklakrfjeJpDQggjlkdfjslkaCLuykR7mvlul4oqLujA="
CANO: "50443433" # 계좌번호 앞 8자리
ACNT_PRDT_CD: "01" # 계좌번호 뒤 2자리
ACNT_TYPE: "paper"
URL_BASE: "https://openapivts.koreainvestment.com:29443" #모의투자
SOCKET_URL: "ws://ops.koreainvestment.com:31000" # 모의계좌
HTS_ID: "hts_id" # HTS_ID

#디스코드 웹훅 URL
DISCORD_WEBHOOK_URL: "https://discord.com/api/webhooks/1124241654352364566/phiJ3kbfdsfksdl;fksd;lWBfsk;arke;lrgsdlkrjeoliwurewoijf79Z1tOK" # Paper Trading
```
#### Live Account
```
NAME: "gildong_50943433_live"
APP_KEY: "PSaOefdskaflsdjflkgjalerruFcN7mgHgrYuus"
APP_SECRET: "ImKZdYxKL/4b8Jhcgjdsajlfkjewslkrujlkouervflub6Tb7bnTW1bs4oArKkfjsdlakrfjeJpDQggjlkdfjslkaCLuykR7mvlul4oqLujA="
CANO: "50943433" # 계좌번호 앞 8자리
ACNT_PRDT_CD: "01" # 계좌번호 뒤 2자리
ACNT_TYPE: "live"
URL_BASE: "https://openapi.koreainvestment.com:9443" #실전계좌
SOCKET_URL: "ws://ops.koreainvestment.com:21000" # 실전계좌
HTS_ID: "hts_id" # HTS_ID

#디스코드 웹훅 URL
DISCORD_WEBHOOK_URL: "https://discord.com/api/webhooks/112424163544352364566/phiJ3kbfdsfkasfkds;lfkdsWBIU-0JUh4qkgjakljfgsdlkrjeoliwurewoijf79Z1tOK" # Live Trading
```

2. ID_ACCOUNT 폴더 생성

