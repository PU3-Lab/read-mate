from pathlib import Path

from cryptography.fernet import Fernet

root = Path.cwd().parent


def encrypt():
    key = Fernet.generate_key()
    print(f'Your Symmetric Key: {key.decode()}')  # 이 값을 따로 메모해두세요!

    cipher_suite = Fernet(key)

    with open(root / '.env', 'rb') as f:
        encrypted_data = cipher_suite.encrypt(f.read())

    with open(root / '.env.enc', 'wb') as f:
        f.write(encrypted_data)

    print('.env.enc 파일이 생성되었습니다. 구글 드라이브에 업로드하세요.')
