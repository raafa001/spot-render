pipeline {
    agent any
    stages {
        stage('Checkout') {
            steps {
                git branch: 'main',
                    credentialsId: 'github-app',
                    url: 'https://github.com/raafa001/spot-render.git'
            }
        }
        stage('Deploy Monitoring') {
            steps {
                withAWS(credentials: 'aws-credentials', region: 'us-east-1') {
                    script {
                        echo 'Applying Grafana and Prometheus manifests from kubernetes directory...'
                        sh 'kubectl create namespace monitoring --dry-run=client -o yaml | kubectl apply -f -'
                        sh 'kubectl apply -f kubernetes/grafana-deployment.yaml -n monitoring'
                        sh 'kubectl apply -f kubernetes/grafana-service.yaml -n monitoring'
                        sh 'kubectl apply -f kubernetes/prometheus-deployment.yaml -n monitoring'
                        sh 'kubectl apply -f kubernetes/prometheus-service.yaml -n monitoring'
                        sh 'kubectl apply -f kubernetes/prometheus-configmap.yaml -n monitoring'
                        sh 'kubectl apply -f kubernetes/prometheus-rules.yaml -n monitoring'
                        sh 'kubectl apply -f kubernetes/grafana-datasource.yaml -n monitoring'
                        sh 'kubectl apply -f kubernetes/grafana-dashboard-provider.yaml -n monitoring'
                        sh 'kubectl apply -f kubernetes/grafana-dashboards.yaml -n monitoring'
                    }
                }
            }
        }
    }
}