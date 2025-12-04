# notifications/firebase_init.py
import os
import firebase_admin
from firebase_admin import credentials
import logging

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(__file__)
FIREBASE_CRED_PATH = os.path.join(BASE_DIR, "firebase.json")


def initialize_firebase():
    """Initialize Firebase Admin SDK if not already initialized"""
    try:
        # Check if already initialized
        firebase_admin.get_app()
        logger.debug("✅ Firebase app already initialized")
        return True
    except ValueError:
        # Not initialized, so initialize it
        try:
            logger.debug("🚀 Initializing Firebase app...")
            logger.debug(f"🔧 Firebase JSON Path: {FIREBASE_CRED_PATH}")
            
            if not os.path.exists(FIREBASE_CRED_PATH):
                logger.error(f"❌ Firebase credentials file not found: {FIREBASE_CRED_PATH}")
                return False
            
            cred = credentials.Certificate(FIREBASE_CRED_PATH)
            firebase_admin.initialize_app(cred)
            logger.debug("✅ Firebase initialized successfully!")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to initialize Firebase: {str(e)}")
            return False


# Initialize on module import
initialize_firebase()