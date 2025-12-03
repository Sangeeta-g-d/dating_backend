# firebase_init.py

import firebase_admin
from firebase_admin import credentials
from firebase_admin import messaging
import os

# Load your Firebase service account JSON
FIREBASE_CRED_PATH = os.path.join(os.path.dirname(__file__), "firebase.json")

if not firebase_admin._apps:
    cred = credentials.Certificate(FIREBASE_CRED_PATH)
    firebase_admin.initialize_app(cred)

