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

# Google Sheets API 認証
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SERVICE_ACCOUNT_FILE = 'credentials.json'
creds = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES
)
# 証明書の更新が必要な場合（オプションの手順）
creds.refresh(Request())

# Google Sheets API サービスオブジェクトの構築
service = build('sheets', 'v4', credentials=creds)

# Google Sheet ID
SPREADSHEET_ID = '10VVS8F0xmcibUQsyI7ZZkU_gzlyE5Y_hXAHEY2WgH5Q'

# Google Sheets のスプレッドシート名
ATTENDEES_SHEET = 'Attendees'
SUBJECTS_SHEET = 'Subjects'
ATTENDANCE_SHEET = 'Attendance'

# メール送信の設定
load_dotenv()
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587
SMTP_USERNAME = 'paca0118@gmail.com'
SMTP_PASSWORD = 'ipmy biow kjla cpvr'

# QRコードの保存ディレクトリ
QR_CODE_DIR = 'static/qr_codes'
os.makedirs(QR_CODE_DIR, exist_ok=True)

# 教室内ネットワークのIP範囲（実際のネットワークに応じて調整可能）
ALLOWED_IP_RANGES = [
    ipaddress.ip_network('192.168.0.0/24'),  # 仮に教室の内部ネットワーク範囲 192.168.0.0/24
    #ipaddress.ip_network('127.0.0.0/8')     # もう一つの許可されたネットワーク範囲
]

def is_ip_allowed(ip):
    """IPが許可されたネットワーク範囲内にあるかを確認"""
    try:
        ip_obj = ipaddress.ip_address(ip)
        return any(ip_obj in net for net in ALLOWED_IP_RANGES)
    except ValueError:
        return False

# カスタム授業時間帯
LESSON_TIMES = [
    {"start": dt_time(8, 30), "end": dt_time(9, 20), "status": "出席"},
    {"start": dt_time(9, 20), "end": dt_time(10, 50), "status": "遲到"},
    {"start": dt_time(10, 50), "end": dt_time(11, 0), "status": "出席"},
    {"start": dt_time(11, 0), "end": dt_time(12, 30), "status": "遲到"},
    {"start": dt_time(12, 30), "end": dt_time(13, 30), "status": "出席"},
    {"start": dt_time(13, 30), "end": dt_time(15, 0), "status": "遲到"},
    {"start": dt_time(15, 0), "end": dt_time(15, 10), "status": "出席"},
    {"start": dt_time(15, 10), "end": dt_time(16, 40), "status": "遲到"},
    # 必要に応じて他の時間帯を自由に追加可能
]
def determine_attendance_status(current_time):
    """現在の時間に基づいて正常出席または遅刻かどうかを判"""
    current_time_only = current_time.time()
    for lesson in LESSON_TIMES:
        if lesson["start"] <= current_time_only <= lesson["end"]:
            return lesson["status"]
    return "授業時間外"

@app.route('/')
def index():
    # 從 Google Sheets 学年と科目データの取得
    sheet = service.spreadsheets()
    subjects_result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=f"{SUBJECTS_SHEET}!A2:B").execute()
    subjects_data = subjects_result.get('values', [])

    grades = set([row[0] for row in subjects_data])
    subjects = {grade: [] for grade in grades}
    for row in subjects_data:
        subjects[row[0]].append(row[1])

    # 從 Google Sheets 出席者データの取得
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

    # 出席者データの検索
    attendees_result = service.spreadsheets().values().get(spreadsheetId=SPREADSHEET_ID, range=f"{ATTENDEES_SHEET}!A2:C").execute()
    attendees_data = attendees_result.get('values', [])
    attendee_info = next((attendee for attendee in attendees_data if attendee[0] == email and attendee[2] == grade), None)

     # すべてのパラメータに値があることを確認
    if not grade or not email or not subject:
        flash('必要なパラメータが不足しています')
        return redirect(url_for('index'))

    timestamp = int(time.time())
    token = f"{email}|{subject}|{timestamp}"  # 科目情報を含む Token
    qr_data = f"{request.host_url}verify_page?token={token}"  # 在 URL 中嵌入 Token
    img = qrcode.make(qr_data)
    qr_path = os.path.join(QR_CODE_DIR, f'{email}_qr.png')
    img.save(qr_path)

    # リンク付きメールの送信
    try:
        msg = MIMEMultipart()
        msg['From'] = SMTP_USERNAME
        msg['To'] = email
        msg['Subject'] = 'あなたの出席QRコード'

        body = f'''
       以下のQRコードを使用して出席認証を行うか、画像をクリックしてFace ID認証ページに移動してください：<br>
        <a href="{qr_data}"><img src="cid:qr_code" style="width:200px;height:200px;"></a><br>
        このコードは30秒以内に有効です。
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
        flash(f'SMTP認証に失敗しました。SMTPのユーザー名とパスワードを確認してください：{e}')
    except smtplib.SMTPException as e:
        flash(f'メールを送信できませんでした。SMTPの設定を確認してください: {e}')
    except Exception as e:
        flash(f'メール送信に失敗しました：{e}')
        return redirect(url_for('index'))

    flash('QRコードが生成され、メールに送信されました。30秒以内にスキャンしてください。')
    return redirect(url_for('index'))

verify_qr_lock = Lock()
@app.route('/verify_qr', methods=['POST'])
def verify_qr():
    if not verify_qr_lock.acquire(blocking=False):
        return jsonify({'status': 'error', 'message': '現在、他の認証処理が行われています。しばらくしてからもう一度お試しください。', 'pauseCamera': False})
    try:
        # デバッグ出力
        print("Received QR data:", request.json)

        # クライアントのIPアドレスを取得
        client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)

        # IPアドレスのデバッグ出力
        print(f"Client IP: {client_ip}")

        # IPアドレスが許可範囲内かを確認
        if not is_ip_allowed(client_ip):
            return jsonify({'status': 'error', 'message': 'あなたは許可されたネットワーク内にいないため、出席認証を行うことができません！'}), 403

        data = request.json.get('data')
        print(f"Received QR data: {data}")
        if data:
            try:
                # URL からトークンを抽出
                if "token=" in data:
                    token = data.split("token=")[1]  # トークンの抽出
                else:
                    return jsonify({'status': 'error', 'message': 'QRコードが不足しています Token'})

                # トークンの解析
                email, subject, timestamp = token.split('|')
                print(f"QRコード解析結果 - Email: {email}, Subject: {subject}, Timestamp: {timestamp}")

                current_time = datetime.now()
                qr_time = datetime.fromtimestamp(int(timestamp))

                # QRコードが有効期限内か確認
                if (current_time - qr_time).total_seconds() > 30:
                    return jsonify({'status': 'error', 'message': 'QRコードが期限切れです！', 'pauseCamera': False})

                # Google Sheets から出席者データを検索
                sheet = service.spreadsheets()
                attendees_result = sheet.values().get(
                    spreadsheetId=SPREADSHEET_ID,
                    range=f"{ATTENDEES_SHEET}!A2:C"  # 仮に A 列が Email、B 列が氏名
                ).execute()
                attendees_data = attendees_result.get('values', [])
                print(f"Google Sheets 出席者データ: {attendees_data}")

                # メールアドレスの照合
                attendee_info = next((attendee for attendee in attendees_data if attendee[0].strip().lower() == email.strip().lower()), None)
                if not attendee_info:
                    return jsonify({'status': 'error', 'message': '該当する出席者データが見つかりません'})

                name = attendee_info[1]
                attendance_status = determine_attendance_status(current_time)

                # クライアント IP の取得
                client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)

                # IP が他のユーザーに使用されているか確認
                sheet = service.spreadsheets()
                existing_records = sheet.values().get(
                    spreadsheetId=SPREADSHEET_ID,
                    range=f"{ATTENDANCE_SHEET}!A2:G"
                ).execute().get('values', [])

                for record in existing_records:
                    if len(record) >= 7 and record[6] == client_ip and record[0] != name:
                        return jsonify({'status': 'error', 'message': 'この IP はすでに他のユーザーに使用されています！'})

                # 出席表の更新
                values = [[name, subject, "QRコードのスキャン", attendance_status, current_time.isoformat(), client_ip]]
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
                    'message': '検証に成功しました',
                    'name': name,
                    'subject': subject,
                    'attendance_status': attendance_status,
                    'time': current_time.strftime("%Y-%m-%d %H:%M:%S")
                })
            except ValueError as e:
                return jsonify({'status': 'error', 'message': f'無効な QRコードフォーマット: {e}'})
            except Exception as e:
                app.logger.error(f"Error occurred: {str(e)}")
                return jsonify({'status': 'error', 'message': f'エラーが発生しました: {e}'})
        return jsonify({'status': 'error', 'message': '無効なQRコードデータです！', 'pauseCamera': False})
    finally:
        verify_qr_lock.release()

@app.route('/verify_page', methods=['GET'])
def verify_page():
    token = request.args.get('token')
    #  トークンがない場合、新しいトークンにリダイレクト
    if not token:
        import time
        email = "test@example.com"
        subject = "Math"
        new_token = f"{email}|{subject}|{int(time.time())}"
        return redirect(f"/verify_page?token={new_token}")

    # トークンのデコード
    try:
        # デコードロジックと生成ロジックが一致していることを確認
        email, subject, timestamp = token.split('|')
        current_time = datetime.now()
        token_time = datetime.fromtimestamp(int(timestamp))


        # トークンの有効期限を確認
        if (current_time - token_time).total_seconds() > 30:
            return "この認証リンクは期限切れです！", 403
    except ValueError as e:
        return f"無効なトークンフォーマット: {e}", 400
    except Exception as e:
        return f"無効なトークン: {e}", 400

    # 生体認証ページをレンダリングし、email と subject をテンプレートに渡す
    return render_template('verify_page.html', email=email, subject=subject)

@lru_cache(maxsize=100)
def get_attendees():
    """Attendees データをキャッシュし、API リクエストを削減""""
    sheet = service.spreadsheets()
    result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=f"{ATTENDEES_SHEET}!A2:D").execute()
    return result.get('values', [])

@app.route('/check_biometric', methods=['GET'])
def check_biometric():
    email = request.args.get('email')
    if not email:
        return jsonify({'registered': False, 'message': 'メールアドレスのパラメータが不足しています'})

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
        return jsonify({'status': 'error', 'message': '必要なパラメータが不足しています'})

    # ユーザーが登録済みか確認
    attendees_data = get_attendees()
    user_row_index = next((i for i, row in enumerate(attendees_data) if row[0].strip().lower() == email.strip().lower()), None)

    if user_row_index is None:
        return jsonify({'status': 'error', 'message': '該当ユーザーが見つかりません'})

    existing_biometric_data = attendees_data[user_row_index][3] if len(attendees_data[user_row_index]) > 3 else None
    name = attendees_data[user_row_index][1]

    if action == 'biometric-init':
        if existing_biometric_data:
            return jsonify({'status': 'error', 'message': '生体認証が登録済み'})

        attendees_data[user_row_index].append(biometric_data)
        service.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{ATTENDEES_SHEET}!D{user_row_index + 2}",
            valueInputOption="USER_ENTERED",
            body={"values": [[biometric_data]]}
        ).execute()

        return jsonify({'status': 'success', 'message': '生体認証が登録済み'})

    elif action == 'biometric-verify':
        if existing_biometric_data == biometric_data:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            attendance_data = [[name, subject, "生体認証の確認", "出席", current_time]]
            service.spreadsheets().values().append(
                spreadsheetId=SPREADSHEET_ID,
                range=f"{ATTENDANCE_SHEET}!A2:E",
                valueInputOption="USER_ENTERED",
                body={"values": attendance_data}
            ).execute()

            return jsonify({'status': 'success', 'message': '認証成功', 'name': name, 'subject': subject, 'attendance_status': '出席', 'time': current_time})

        return jsonify({'status': 'error', 'message': '生体認証に失敗しました'})

if __name__ == '__main__':
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile='cert.pem', keyfile='key.pem')

    app.run(host='0.0.0.0', port=8080, ssl_context=context)
