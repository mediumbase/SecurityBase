import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Load API credentials
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_snapshot_to_telegram(filepath):
    """
    Send a snapshot to a Telegram chat.
    
    Args:
        filepath (str): Path to the snapshot file to send.
    """
    if not BOT_TOKEN or not CHAT_ID:
        print("Error: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set in .env")
        return False
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    
    try:
        with open(filepath, 'rb') as photo:
            files = {'photo': photo}
            data = {'chat_id': CHAT_ID}
            response = requests.post(url, files=files, data=data)
            response.raise_for_status()
            print(f"Snapshot sent to Telegram: {filepath}")
            return True
    except Exception as e:
        print(f"Error sending snapshot to Telegram: {e}")
        return False

if __name__ == "__main__":
    snapshot_dir = os.path.expanduser(os.getenv("SNAPSHOT_DIR", "snapshots"))
    snapshots = sorted(
        [f for f in os.listdir(snapshot_dir) if f.endswith(".jpg")],
        reverse=True
    )
    if snapshots:
        latest_snapshot = os.path.join(snapshot_dir, snapshots[0])
        send_snapshot_to_telegram(latest_snapshot)
    else:
        print("No snapshots found")