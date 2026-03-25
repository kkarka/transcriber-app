#!/bin/bash

set -eo pipefail

# SAFETY CHECK: Force the script to run from the project root directory
cd "$(dirname "$0")/.." || exit
echo "📂 Working directory set to: $(pwd)"

echo "🚀 Starting Enterprise Clean Environment Setup..."

# ==========================================
# 0. SECURE CREDENTIAL CAPTURE
# ==========================================
read -s -p "Enter Redis Password for Vault: " REDIS_SECRET
echo "" 

read -s -p "Enter GitHub Token for Vault: " GITHUB_SECRET
echo ""

if [ -z "$REDIS_SECRET" ] || [ -z "$GITHUB_SECRET" ]; then
    echo "❌ Error: Secrets cannot be empty. Exiting."
    exit 1
fi


# ==========================================
# 1. KUBERNETES CLUSTER (KIND)
# ==========================================
if kind get clusters | grep -q "^transcriber-cluster$"; then
    echo "✅ Kind cluster 'transcriber-cluster' already exists. Skipping creation."
else
    echo "📦 Creating Kind cluster (transcriber-cluster) with custom networking..."
    kind create cluster --name transcriber-cluster --config infrastructure/kubernetes/kind-config.yaml --image kindest/node:v1.30.0 || { echo "❌ Failed to create cluster"; exit 1; }
fi

echo "🔑 Extracting internal Kubeconfig for Jenkins..."
kind get kubeconfig --name transcriber-cluster --internal > jenkins-kubeconfig.yaml
chmod 644 jenkins-kubeconfig.yaml


# ==========================================
# 2. HASHICORP VAULT
# ==========================================
echo "🔐 Setting up HashiCorp Vault..."

if [ "$(docker ps -aq -f name=^vault$)" ]; then
    if [ "$(docker inspect -f '{{.State.Running}}' vault)" == "true" ]; then
        echo "✅ Vault container is already running."
    else
        echo "🔄 Starting existing Vault container..."
        docker start vault
    fi
else
    echo "🚀 Creating new Vault container..."
    docker run -d \
      --name vault \
      --network kind \
      -p 8200:8200 \
      --cap-add=IPC_LOCK \
      -e 'VAULT_DEV_ROOT_TOKEN_ID=root' \
      -e 'VAULT_DEV_LISTEN_ADDRESS=0.0.0.0:8200' \
      hashicorp/vault
fi

echo "⏳ Waiting for Vault to fully initialize..."
VAULT_READY=false
# Increase attempts to 60 (2 minutes total)
for i in {1..60}; do
    # Try the API first
    if curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8200/v1/sys/health | grep -qE "200|501"; then
        echo "✅ Vault API is responding!"
        VAULT_READY=true
        break
    fi
    # Fallback: Try the internal CLI check
    if docker exec vault vault status > /dev/null 2>&1; then
        echo "✅ Vault CLI reports ready!"
        VAULT_READY=true
        break
    fi
    echo -n "."
    sleep 2
done

if [ "$VAULT_READY" = false ]; then
    echo "❌ Vault failed to initialize in time. Exiting."
    exit 1
fi

echo "💉 Injecting Redis secret into Vault..."
docker exec -e VAULT_ADDR=http://127.0.0.1:8200 -e VAULT_TOKEN=root vault vault kv put secret/transcriber-app REDIS_PASSWORD="$REDIS_SECRET" GITHUB_TOKEN="$GITHUB_SECRET" > /dev/null 2>&1

unset REDIS_SECRET
unset GITHUB_SECRET


# ==========================================
# 3. JENKINS
# ==========================================
echo "🏗️ Checking for custom Jenkins Docker image..."

if [[ "$(docker images -q custom-jenkins-devops:latest 2> /dev/null)" == "" ]]; then
    echo "📦 Image not found. Building custom Jenkins image..."
    docker build -t custom-jenkins-devops -f infrastructure/jenkins/Dockerfile .
else
    echo "✅ Custom Jenkins image already exists. Skipping build."
    echo "💡 Tip: Run 'docker rmi custom-jenkins-devops' if you need to force a rebuild."
fi

FRESH_START=false
if [ -z "$(docker volume ls -q -f name=^jenkins_home$)" ]; then
    FRESH_START=true
    echo "🌟 First time Jenkins setup detected!"
else
    echo "♻️ Existing Jenkins data found. Skipping first-time setup."
fi

echo "⚙️ Setting up Jenkins..."

if [ "$(docker ps -aq -f name=^jenkins$)" ]; then
    if [ "$(docker inspect -f '{{.State.Running}}' jenkins)" == "true" ]; then
        echo "✅ Jenkins container is already running."
    else
        echo "🔄 Starting existing Jenkins container..."
        docker start jenkins
    fi
else
    echo "🚀 Creating new Jenkins container..."
    docker run -d \
      --name jenkins \
      --network kind \
      --user root \
      --privileged \
      -e DOCKER_BUILDKIT=1 \
      -p 8080:8080 -p 50000:50000 \
      -v jenkins_home:/var/jenkins_home \
      -v /var/run/docker.sock:/var/run/docker.sock \
      -v "${PWD}/jenkins-kubeconfig.yaml":/var/jenkins_home/.kube/config \
      custom-jenkins-devops
fi

if [ "$FRESH_START" = true ]; then
    echo "⏳ Waiting for Jenkins to boot and generate the initial password (this takes about 20-40 seconds)..."
    JENKINS_READY=false
    for i in {1..30}; do
        if docker exec jenkins test -f /var/jenkins_home/secrets/initialAdminPassword 2>/dev/null; then
            JENKINS_PASS=$(docker exec jenkins cat /var/jenkins_home/secrets/initialAdminPassword)
            echo "=========================================="
            echo "🚨 FIRST TIME LOGIN REQUIRED 🚨"
            echo "Your Initial Admin Password is:"
            echo -e "\033[1;32m$JENKINS_PASS\033[0m" 
            echo "Copy this password and go to http://localhost:8080"
            echo "=========================================="
            JENKINS_READY=true
            break
        fi
        sleep 2
    done

    if [ "$JENKINS_READY" = false ]; then
        echo "❌ Jenkins failed to initialize in time. Check 'docker logs jenkins'. Exiting."
        exit 1
    fi
else
    echo "=========================================="
    echo "🔐 JENKINS LOGIN"
    echo "Go to http://localhost:8080 and use your previously created username and password."
    echo "=========================================="
fi

# ==========================================
# 3.5 SONARQUBE
# ==========================================
echo "🛡️ Setting up SonarQube for Code Quality..."

if [ "$(docker ps -aq -f name=^sonarqube$)" ]; then
    if [ "$(docker inspect -f '{{.State.Running}}' sonarqube)" == "true" ]; then
        echo "✅ SonarQube container is already running."
    else
        echo "🔄 Starting existing SonarQube container..."
        docker start sonarqube
    fi
else
    echo "🚀 Creating new SonarQube container..."
    # SonarQube needs a bit more RAM, it's a heavy Java app!
    docker run -d \
      --name sonarqube \
      --network kind \
      -p 9000:9000 \
      sonarqube:lts-community
fi


# ==========================================
# 4. NGROK TUNNEL
# ==========================================
echo "🌐 Setting up Ngrok Tunnel..."
if pgrep -x "ngrok" > /dev/null; then
    echo "✅ Ngrok is already running."
else
    echo "🚀 Starting Ngrok..."
    nohup ngrok http --domain=nonfossiliferous-jovanni-geophilous.ngrok-free.dev 8080 > ngrok.log 2>&1 &
fi


# ==========================================
# 5. MONITORING (PROMETHEUS & GRAFANA)
# ==========================================
echo "📊 Setting up Prometheus & Grafana..."
if ! command -v helm &> /dev/null; then
    echo "⚠️ Helm is not installed. Skipping Prometheus/Grafana setup."
else
    kubectl create namespace monitoring --dry-run=client -o yaml | kubectl apply -f -
    helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
    helm repo update
    
    # 🚀 Step A: Install/Upgrade the Stack
    echo "📦 Syncing kube-prometheus-stack (Revision 5+)..."
    helm upgrade --install prometheus prometheus-community/kube-prometheus-stack \
        --namespace monitoring \
        -f infrastructure/kubernetes/grafana-values.yaml \
        --set prometheusOperator.createCustomResource=false \
        --timeout 10m

    # 🚀 Step B: Apply Custom Rules & Dashboards
    echo "💉 Injecting Custom Alerts & Dashboards..."
    kubectl apply -f infrastructure/kubernetes/custom-alerts.yaml -n monitoring
    kubectl apply -f infrastructure/kubernetes/grafana-dashboard.yaml -n monitoring

    # 🚀 Step C: The "Kick" (Ensure the Operator sees the new rules)
    echo "🔄 Refreshing Monitoring Operator..."
    kubectl rollout restart deployment prometheus-kube-prometheus-operator -n monitoring
fi


# ==========================================
# 6. CLUSTER PREREQUISITES (KEDA & METRICS)
# ==========================================
echo "⚙️ Setting up Core Cluster Prerequisites..."

echo "Installing/Updating Metrics Server..."
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml || true
kubectl patch deployment metrics-server -n kube-system --type='json' -p='[{"op": "add", "path": "/spec/template/spec/containers/0/args/-", "value": "--kubelet-insecure-tls"}]' || true

echo "Installing/Updating KEDA via Helm..."
if helm ls -n keda | grep -q keda; then
    echo "✅ KEDA is already installed."
else
    helm repo add kedacore https://kedacore.github.io/charts
    helm repo update
    helm upgrade --install keda kedacore/keda --namespace keda --create-namespace --timeout 10m
fi


# ==========================================
# 7. FINAL VERIFICATION
# ==========================================
echo "=========================================="
echo "✅ ENVIRONMENT FULLY PROVISIONED!"
echo "=========================================="
echo "🔗 Jenkins:       http://localhost:8080"
echo "🔗 Vault:         http://localhost:8200 (Login Token: root)"
echo "🔗 GitHub Webhook: https://nonfossiliferous-jovanni-geophilous.ngrok-free.dev"
echo "🔗 Grafana:        http://localhost/grafana"
echo "💡 To view Prometheus Rules: kubectl port-forward svc/prometheus-kube-prometheus-prometheus -n monitoring 9090:9090"
echo "💡 To view Alerts:         kubectl port-forward svc/prometheus-kube-prometheus-alertmanager -n monitoring 9093:9093"
echo "=========================================="

echo "🔍 Performing Final Health Check..."
containers=("jenkins" "vault")
for container in "${containers[@]}"; do
    if [ "$(docker inspect -f '{{.State.Running}}' $container)" == "true" ]; then
        echo "✅ $container is healthy."
    else
        echo "❌ $container failed to start! Check 'docker logs $container'"
    fi
done

# ==========================================
# 8. PYTHON VENV SETUP (FOR SCRIPTS)
# ==========================================
echo "🐍 Setting up Python Virtual Environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

# Ensure aiohttp is installed in the venv
./venv/bin/pip install aiohttp --quiet

echo "✅ Stress test environment ready! Run: source venv/bin/activate && python3 scripts/stress_test.py"


# ==========================================
# 9. SONARQUBE API CONFIGURATION
# ==========================================
echo "⚙️ Configuring SonarQube API & Webhooks..."
# Ensure requests is installed in your venv
./venv/bin/pip install requests --quiet
./venv/bin/python3 scripts/setup_sonarqube.py


echo ""
echo "✨ APP ACCESS READY ✨"
echo "Your NGINX Gateway is routing traffic directly from your localhost to the cluster."
echo "👉 View the application at: http://localhost"
echo "👉 View the API directly at: http://localhost/api/"
