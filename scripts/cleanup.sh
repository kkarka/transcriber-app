#!/bin/bash

# SAFETY CHECK: Force the script to run from the project root directory
cd "$(dirname "$0")/.." || exit
echo "📂 Working directory set to: $(pwd)"

echo "🧹 Starting Environment Cleanup..."

# ==========================================
# 1. KILL NGROK TUNNEL
# ==========================================
echo "🌐 Shutting down Ngrok..."
# pkill finds the ngrok process and kills it safely. 
# The '|| true' ensures the script doesn't crash if ngrok is already dead.
pkill ngrok || true

# ==========================================
# 2. DESTROY KUBERNETES CLUSTER
# ==========================================
echo "📦 Deleting Kind cluster (transcriber-cluster)..."
kind delete cluster --name transcriber-cluster

# ==========================================
# 3. REMOVE DOCKER CONTAINERS & VOLUMES
# ==========================================
echo "🐳 Stopping and removing Jenkins and Vault..."
docker stop jenkins vault || true
docker rm jenkins vault || true

echo "💾 Removing Jenkins data volume for a true reset..."
docker volume rm jenkins_home || true

# ==========================================
# 4. REMOVE DOCKER IMAGES (DEEP CLEAN)
# ==========================================
echo "💿 Removing custom Docker images to free up space..."
# Remove the custom Jenkins image
docker rmi custom-jenkins-devops || true

# Remove the transcriber app CI/CD images
docker rmi worker:local api:local frontend:local || true

# Clean up any dangling "none" images left behind by old builds
docker image prune -f

# ==========================================
# 5. REMOVE LEFTOVER FILES
# ==========================================
echo "🗑️ Removing temporary local files..."
rm -f jenkins-kubeconfig.yaml ngrok.log

echo "=========================================="
echo "✨ CLEANUP COMPLETE!"
echo "Your system is completely reset."
echo "=========================================="