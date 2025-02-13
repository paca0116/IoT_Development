from flask import Flask, render_template, request, redirect, url_for, flash, Response, jsonify, abort
import qrcode
import time
import cv2
import os
import google.auth
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from google.oauth2 import service_account
from datetime import datetime, timedelta
from datetime import time as dt_time
import socket
import smtplib
from functools import lru_cache
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from PIL import Image
import numpy as np
import ipaddress
from dotenv import load_dotenv
# Custom SSL context with the correct protocol
import ssl
import requests
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager
from urllib3.util.ssl_ import create_urllib3_context
from threading import Lock

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Google Sheets API 驗證
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SERVICE_ACCOUNT_FILE = 'credentials.json'
creds = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES
)
# 如果凭证需要刷新（可选步骤）
creds.refresh(Request())

# 构建 Google Sheets API 服务对象
service = build('sheets', 'v4', credentials=creds)

# Google Sheet ID
SPREADSHEET_ID = '10VVS8F0xmcibUQsyI7ZZkU_gzlyE5Y_hXAHEY2WgH5Q'

# Google Sheets 表格名稱
ATTENDEES_SHEET = 'Attendees'
SUBJECTS_SHEET = 'Subjects'
ATTENDANCE_SHEET = 'Attendance'

# 發送電子郵件的設定
load_dotenv()
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587
SMTP_USERNAME = 'paca0118@gmail.com'
SMTP_PASSWORD = 'ipmy biow kjla cpvr'

# QR 碼儲存目錄
QR_CODE_DIR = 'static/qr_codes'
os.makedirs(QR_CODE_DIR, exist_ok=True)

# 教室內部網路的 IP 範圍（可以根據實際網絡調整）
ALLOWED_IP_RANGES = [
    ipaddress.ip_network('192.168.0.0/24'),  # 假設教室內部網段是 192.168.0.0/24
    #ipaddress.ip_network('127.0.0.0/8')      # 另一個允許的網段
]

def is_ip_allowed(ip):
    """檢查 IP 是否在允許的網段內"""
    try:
        ip_obj = ipaddress.ip_address(ip)
        return any(ip_obj in net for net in ALLOWED_IP_RANGES)
    except ValueError:
        return False

# 自訂上課時間段
LESSON_TIMES = [
    {"start": dt_time(8, 30), "end": dt_time(9, 20), "status": "出席"},
    {"start": dt_time(9, 20), "end": dt_time(10, 50), "status": "遲到"},
    {"start": dt_time(10, 50), "end": dt_time(11, 0), "status": "出席"},
    {"start": dt_time(11, 0), "end": dt_time(12, 30), "status": "遲到"},
    {"start": dt_time(12, 30), "end": dt_time(13, 30), "status": "出席"},
    {"start": dt_time(13, 30), "end": dt_time(15, 0), "status": "遲到"},
    {"start": dt_time(15, 0), "end": dt_time(15, 10), "status": "出席"},
    {"start": dt_time(15, 10), "end": dt_time(16, 40), "status": "遲到"},
    # 你可以自由增加其他時間段
]
def determine_attendance_status(current_time):
    """根據當前時間判斷是否為正常出席或遲到"""
    current_time_only = current_time.time()
    for lesson in LESSON_TIMES:
        if lesson["start"] <= current_time_only <= lesson["end"]:
            return lesson["status"]
    return "未在上課時間內"

@app.route('/')
def index():
    # 從 Google Sheets 獲取年級和科目資料
    sheet = service.spreadsheets()
    subjects_result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=f"{SUBJECTS_SHEET}!A2:B").execute()
    subjects_data = subjects_result.get('values', [])

    grades = set([row[0] for row in subjects_data])
    subjects = {grade: [] for grade in grades}
    for row in subjects_data:
        subjects[row[0]].append(row[1])

    # 從 Google Sheets 獲取出席者資料
    attendees_result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=f"{ATTENDEES_SHEET}!A2:C").execute()
    attendees_data = attendees_result.get('values', [])

    attendees = {grade: [] for grade in grades}
    for row in attendees_data:
        grade = row[2]
        attendees[grade].append({'email': row[0], 'name': row[1]})

    return render_template('index.html', grades=grades, subjects=subjects, attendees=attendees)


@app.route('/generate_qr', methods=['POST'])
def generate_qr():
    grade = request.form['grade']
    email = request.form['name']
    subject = request.form['subject']

    # 查找出席者資料
    attendees_result = service.spreadsheets().values().get(spreadsheetId=SPREADSHEET_ID, range=f"{ATTENDEES_SHEET}!A2:C").execute()
    attendees_data = attendees_result.get('values', [])
    attendee_info = next((attendee for attendee in attendees_data if attendee[0] == email and attendee[2] == grade), None)

     # 確保所有參數都有值
    if not grade or not email or not subject:
        flash('缺少必要參數')
        return redirect(url_for('index'))

    timestamp = int(time.time())
    token = f"{email}|{subject}|{timestamp}"  # 包含科目信息的 Token
    qr_data = f"{request.host_url}verify_page?token={token}"  # 在 URL 中嵌入 Token
    img = qrcode.make(qr_data)
    qr_path = os.path.join(QR_CODE_DIR, f'{email}_qr.png')
    img.save(qr_path)

    # 發送帶有鏈接的電子郵件
    try:
        msg = MIMEMultipart()
        msg['From'] = SMTP_USERNAME
        msg['To'] = email
        msg['Subject'] = '您的出席 QR 碼'

        body = f'''
        請使用以下的 QR 碼進行出席驗證，或點擊圖示跳轉到生物識別驗證頁面：<br>
        <a href="{qr_data}"><img src="cid:qr_code" style="width:200px;height:200px;"></a><br>
        該碼將在 30 秒後過期。
        '''
        msg.attach(MIMEText(body, 'html'))

        with open(qr_path, 'rb') as qr_file:
            img_data = qr_file.read()
            image = MIMEImage(img_data, name=os.path.basename(qr_path))
            image.add_header('Content-ID', '<qr_code>')
            msg.attach(image)

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.sendmail(SMTP_USERNAME, email, msg.as_string())
        server.quit()


    except smtplib.SMTPException as e:
        flash(f'SMTP 身份验证失败，请检查您的 SMTP 用户名和密码：{e}')
    except smtplib.SMTPException as e:
        flash(f'無法發送電子郵件，請檢查您的 SMTP 設定: {e}')
    except Exception as e:
        flash(f'發送郵件失敗：{e}')
        return redirect(url_for('index'))

    flash('QR 碼已生成並發送到您的電子郵件。請於 30 秒內完成掃描驗證。')
    return redirect(url_for('index'))

verify_qr_lock = Lock()
@app.route('/verify_qr', methods=['POST'])
def verify_qr():
    if not verify_qr_lock.acquire(blocking=False):
        return jsonify({'status': 'error', 'message': '目前有其他驗證正在進行，請稍後再試。', 'pauseCamera': False})
    try:
        # 調試輸出
        print("Received QR data:", request.json)

        # 獲取客戶端的 IP 地址
        client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)

        # 調試輸出 IP 地址
        print(f"Client IP: {client_ip}")

        # 如果是開發環境，跳過 IP 檢查
        #if os.getenv('FLASK_ENV') == 'development':
            #client_ip = '192.168.0.1'  # 模擬內部 IP 地址

        # 驗證 IP 地址是否在允許的範圍內
        if not is_ip_allowed(client_ip):
            return jsonify({'status': 'error', 'message': '您不在允許的網絡內，無法進行出席驗證！'}), 403

        data = request.json.get('data')
        print(f"Received QR data: {data}")
        if data:
            try:
                # 從 URL 中提取 Token
                if "token=" in data:
                    token = data.split("token=")[1]  # 提取 token
                else:
                    return jsonify({'status': 'error', 'message': 'QR 碼中缺少 Token'})

                # 解析 Token
                email, subject, timestamp = token.split('|')
                print(f"QR碼解析結果 - Email: {email}, Subject: {subject}, Timestamp: {timestamp}")

                current_time = datetime.now()
                qr_time = datetime.fromtimestamp(int(timestamp))

                # 確認 QR 碼是否在有效期內
                if (current_time - qr_time).total_seconds() > 30:
                    return jsonify({'status': 'error', 'message': 'QR 碼已過期！', 'pauseCamera': False})

                # 從 Google Sheets 查找出席者資料
                sheet = service.spreadsheets()
                attendees_result = sheet.values().get(
                    spreadsheetId=SPREADSHEET_ID,
                    range=f"{ATTENDEES_SHEET}!A2:C"  # 假設 A 列是 Email，B 列是姓名
                ).execute()
                attendees_data = attendees_result.get('values', [])
                print(f"Google Sheets 出席者數據: {attendees_data}")

                # 匹配 Email
                attendee_info = next((attendee for attendee in attendees_data if attendee[0].strip().lower() == email.strip().lower()), None)
                if not attendee_info:
                    return jsonify({'status': 'error', 'message': '找不到對應的出席者資料'})

                name = attendee_info[1]
                attendance_status = determine_attendance_status(current_time)

                # 獲取客戶端 IP
                client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)

                # 驗證 IP 是否已被其他用戶使用
                sheet = service.spreadsheets()
                existing_records = sheet.values().get(
                    spreadsheetId=SPREADSHEET_ID,
                    range=f"{ATTENDANCE_SHEET}!A2:G"
                ).execute().get('values', [])

                for record in existing_records:
                    if len(record) >= 7 and record[6] == client_ip and record[0] != name:
                        return jsonify({'status': 'error', 'message': '該 IP 已被其他用戶使用！'})

                # 更新出席表
                values = [[name, subject, "掃描 QR 碼", attendance_status, current_time.isoformat(), client_ip]]
                body = {'values': values}
                #sheet = service.spreadsheets()
                sheet.values().append(
                    spreadsheetId=SPREADSHEET_ID,
                    range=f"{ATTENDANCE_SHEET}!A2:F",
                    valueInputOption="USER_ENTERED",
                    body=body
                ).execute()

                return jsonify({
                    'status': 'success',
                    'message': '驗證成功',
                    'name': name,
                    'subject': subject,
                    'attendance_status': attendance_status,
                    'time': current_time.strftime("%Y-%m-%d %H:%M:%S")
                })
            except ValueError as e:
                return jsonify({'status': 'error', 'message': f'無效的 QR 碼格式: {e}'})
            except Exception as e:
                app.logger.error(f"Error occurred: {str(e)}")
                return jsonify({'status': 'error', 'message': f'發生錯誤: {e}'})
        return jsonify({'status': 'error', 'message': '無效的 QR 碼數據！', 'pauseCamera': False})
    finally:
        verify_qr_lock.release()

@app.route('/verify_page', methods=['GET'])
def verify_page():
    token = request.args.get('token')
    # 🔹 如果沒有 Token，重新導向到新的 Token
    if not token:
        import time
        email = "test@example.com"
        subject = "Math"
        new_token = f"{email}|{subject}|{int(time.time())}"
        return redirect(f"/verify_page?token={new_token}")

    # 解碼 Token
    try:
        # 確保解碼邏輯與生成邏輯一致
        email, subject, timestamp = token.split('|')
        current_time = datetime.now()
        token_time = datetime.fromtimestamp(int(timestamp))


        # 確認 Token 是否過期
        if (current_time - token_time).total_seconds() > 300000000:
            return "此驗證鏈接已過期！", 403
    except ValueError as e:
        return f"無效的 Token 格式: {e}", 400
    except Exception as e:
        return f"無效的 Token: {e}", 400

    # 渲染生物識別驗證頁面，將 email 和 subject 傳遞給模板
    return render_template('verify_page.html', email=email, subject=subject)

@lru_cache(maxsize=100)
def get_attendees():
    """快取 Attendees 資料，減少 API 請求"""
    sheet = service.spreadsheets()
    result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=f"{ATTENDEES_SHEET}!A2:D").execute()
    return result.get('values', [])

@app.route('/check_biometric', methods=['GET'])
def check_biometric():
    email = request.args.get('email')
    if not email:
        return jsonify({'registered': False, 'message': '缺少 email 參數'})

    attendees_data = get_attendees()
    user_row = next((row for row in attendees_data if row[0].strip().lower() == email.strip().lower()), None)
    if user_row and len(user_row) > 3 and user_row[3]:
        return jsonify({'registered': True})

    return jsonify({'registered': False})

@app.route('/biometric_auth', methods=['POST'])
def biometric_auth():
    data = request.json
    email = data.get('email')
    subject = data.get('subject')
    action = data.get('action')
    biometric_data = data.get('biometric_data')

    if not email or not biometric_data:
        return jsonify({'status': 'error', 'message': '缺少必要參數'})

    # 檢查用戶是否已註冊
    attendees_data = get_attendees()
    user_row_index = next((i for i, row in enumerate(attendees_data) if row[0].strip().lower() == email.strip().lower()), None)

    if user_row_index is None:
        return jsonify({'status': 'error', 'message': '找不到該用戶'})

    existing_biometric_data = attendees_data[user_row_index][3] if len(attendees_data[user_row_index]) > 3 else None
    name = attendees_data[user_row_index][1]

    if action == 'biometric-init':
        if existing_biometric_data:
            return jsonify({'status': 'error', 'message': '生物識別已註冊'})

        attendees_data[user_row_index].append(biometric_data)
        service.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{ATTENDEES_SHEET}!D{user_row_index + 2}",
            valueInputOption="USER_ENTERED",
            body={"values": [[biometric_data]]}
        ).execute()

        return jsonify({'status': 'success', 'message': '生物識別已註冊'})

    elif action == 'biometric-verify':
        if existing_biometric_data == biometric_data:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            attendance_data = [[name, subject, "生物識別驗證", "出席", current_time]]
            service.spreadsheets().values().append(
                spreadsheetId=SPREADSHEET_ID,
                range=f"{ATTENDANCE_SHEET}!A2:E",
                valueInputOption="USER_ENTERED",
                body={"values": attendance_data}
            ).execute()

            return jsonify({'status': 'success', 'message': '驗證成功', 'name': name, 'subject': subject, 'attendance_status': '出席', 'time': current_time})

        return jsonify({'status': 'error', 'message': '生物識別驗證失敗'})

if __name__ == '__main__':
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile='cert.pem', keyfile='key.pem')

    app.run(host='0.0.0.0', port=8080, ssl_context=context)