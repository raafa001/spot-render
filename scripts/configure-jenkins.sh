#!/bin/bash

# Instalar plugins necessários
JENKINS_PLUGINS="blueocean pipeline-aws workflow-aggregator kubernetes"

for plugin in $JENKINS_PLUGINS; do
    sudo /usr/bin/java -jar /var/cache/jenkins/war/WEB-INF/jenkins-cli.jar -auth admin:$(sudo cat /var/lib/jenkins/secrets/initialAdminPassword) -s http://localhost:8080/ install-plugin $plugin
done

# Reiniciar Jenkins
sudo systemctl restart jenkins
