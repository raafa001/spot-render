#!/bin/bash
set -euo pipefail

# configure-jenkins.sh - Install required Jenkins plugins and restart Jenkins
# Usage: ./configure-jenkins.sh

echo "=== configure-jenkins.sh ==="

# Validate prerequisites
if ! command -v java &>/dev/null; then
    echo "ERROR: Java is not installed. Please install Java first."
    exit 1
fi

if [ ! -f /var/lib/jenkins/secrets/initialAdminPassword ]; then
    echo "ERROR: Jenkins does not appear to be installed or configured."
    echo "Jenkins admin password file not found at /var/lib/jenkins/secrets/initialAdminPassword"
    exit 1
fi

if [ ! -f /var/cache/jenkins/war/WEB-INF/jenkins-cli.jar ]; then
    echo "ERROR: jenkins-cli.jar not found. Is Jenkins running?"
    exit 1
fi

# Jenkins configuration
JENKINS_URL="${JENKINS_URL:-http://localhost:8080}"
JENKINS_PLUGINS="${JENKINS_PLUGINS:-blueocean pipeline-aws workflow-aggregator kubernetes}"
ADMIN_PASSWORD=$(sudo cat /var/lib/jenkins/secrets/initialAdminPassword)

echo "Installing Jenkins plugins: $JENKINS_PLUGINS"

for plugin in $JENKINS_PLUGINS; do
    echo "Installing plugin: $plugin"
    sudo /usr/bin/java -jar /var/cache/jenkins/war/WEB-INF/jenkins-cli.jar \
        -auth "admin:$ADMIN_PASSWORD" \
        -s "$JENKINS_URL" \
        install-plugin "$plugin" || {
        echo "WARNING: Failed to install plugin $plugin"
    }
done

echo "Restarting Jenkins to apply changes..."
sudo systemctl restart jenkins

# Wait for Jenkins to come back
echo "Waiting for Jenkins to restart..."
for i in $(seq 1 30); do
    if curl -s -f "$JENKINS_URL" &>/dev/null; then
        echo "Jenkins is back online."
        break
    fi
    sleep 2
done

echo "=== configure-jenkins.sh completed ==="
