import requests
import time
import sys

SONAR_URL = "http://localhost:9000"
AUTH = ("admin", "admin")  # Default credentials

def wait_for_sonar():
    print("⏳ Waiting for SonarQube API to be ready...")
    for i in range(30):
        try:
            resp = requests.get(f"{SONAR_URL}/api/system/status", auth=AUTH)
            if resp.status_code == 200 and resp.json().get("status") == "UP":
                print("✅ SonarQube is UP!")
                return True
        except:
            pass
        time.sleep(5)
    return False

def setup_webhook():
    print("🔗 Configuring SonarQube Webhook for Jenkins...")
    webhook_data = {
        "name": "Jenkins",
        "url": "http://jenkins:8080/sonarqube-webhook/"
    }
    # Check if exists first to stay idempotent
    existing = requests.get(f"{SONAR_URL}/api/webhooks/list", auth=AUTH).json()
    if not any(w["name"] == "Jenkins" for w in existing.get("webhooks", [])):
        requests.post(f"{SONAR_URL}/api/webhooks/create", data=webhook_data, auth=AUTH)
        print("✅ Webhook created.")
    else:
        print("⏭️ Webhook already exists. Skipping.")

if __name__ == "__main__":
    if wait_for_sonar():
        setup_webhook()
    else:
        print("❌ SonarQube failed to start.")
        sys.exit(1)