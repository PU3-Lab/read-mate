import os
from pathlib import Path

import gdown
from cryptography.fernet import Fernet

root = Path.cwd().parent

FILE_ID = '1PnjfxHcyQYcq6Lz4-61AhV0vPv5mj_J_'
SYMMETRIC_KEY = ''
URL = f'https://drive.google.com/uc?id={FILE_ID}'


def setup():
    enc_file = str(root / '.env.enc')
    target_file = str(root / '.env')

    # 1. gdown으로 다운로드 (이름을 .env.enc로 강제 지정)
    gdown.download(URL, enc_file)

    if not os.path.exists(enc_file):
        print(f'❌ 에러: {enc_file} 다운로드에 실패했습니다.')
        return

    try:
        # 2. 복호화 진행
        cipher_suite = Fernet(SYMMETRIC_KEY.encode())
        with open(enc_file, 'rb') as f:
            encrypted_data = f.read()

        decrypted_data = cipher_suite.decrypt(encrypted_data)

        # 3. .env 파일로 저장 (wb 모드로 덮어쓰기)
        with open(target_file, 'wb') as f:
            f.write(decrypted_data)

        # 4. 다운로드했던 암호화 파일 삭제
        if os.path.exists(enc_file):
            os.remove(enc_file)

        print('-' * 30)
        print(f'✅ 성공: {target_file} 파일이 생성되었습니다!')
        print(f'현재 위치: {os.getcwd()}')
        print('-' * 30)

    except Exception as e:
        print(f'❌ 실패: {e}')
