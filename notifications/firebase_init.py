import os
import firebase_admin
from firebase_admin import credentials, messaging

BASE_DIR = os.path.dirname(__file__)
FIREBASE_CRED_PATH = os.path.join(BASE_DIR, "firebase.json")

if not firebase_admin._apps:
    cred = credentials.Certificate(FIREBASE_CRED_PATH)
    firebase_admin.initialize_app(cred)
