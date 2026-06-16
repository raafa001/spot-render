// OBSOLETO - Jenkins removido/desativado
// Substituido por: .github/workflows/kubernetes-deploy.yml
// Mantido apenas como referencia.

pipeline {
    agent any

    parameters {
        string(name: 'GIT_BRANCH', defaultValue: 'main', description: 'Branch do repositório')
        string(name: 'AWS_REGION', defaultValue: 'us-east-1', description: 'Região AWS')
        string(name: 'AWS_CREDENTIALS_ID', defaultValue: 'aws-credentials', description: 'ID da credencial AWS no Jenkins')
        string(name: 'KUBERNETES_NAMESPACE', defaultValue: 'monitoring', description: 'Namespace do Kubernetes para deploy')
        booleanParam(name: 'DRY_RUN', defaultValue: false, description: 'Executar em dry-run (apenas validação)')
    }

    stages {
        stage('Checkout') {
            steps {
                checkout([
                    $class: 'GitSCM',
                    branches: [[name: params.GIT_BRANCH ]],
                    userRemoteConfigs: [[
                        url: 'https://github.com/raafa001/spot-render.git',
                        credentialsId: 'github-app'
                    ]]
                ])
            }
        }

        stage('Validate Manifests') {
            steps {
                script {
                    def expectedFiles = [
                        'kubernetes/namespaces.yaml',
                        'kubernetes/grafana-deployment.yaml',
                        'kubernetes/grafana-service.yaml',
                        'kubernetes/prometheus-deployment.yaml',
                        'kubernetes/prometheus-service.yaml',
                        'kubernetes/prometheus-configmap.yaml',
                        'kubernetes/prometheus-rules.yaml',
                        'kubernetes/prometheus-datasource.yaml',
                        'kubernetes/prometheus-dashboard-provider.yaml',
                        'kubernetes/prometheus-dashboards.yaml',
                        'kubernetes/network-policy.yaml'
                    ]
                    expectedFiles.each { f ->
                        if (!fileExists(f)) {
                            error "Manifesto não encontrado: ${f}"
                        }
                    }
                    echo 'Todos os manifests Kubernetes estão presentes.'
                }
            }
        }

        stage('Deploy Monitoring') {
            steps {
                withAWS(credentials: params.AWS_CREDENTIALS_ID, region: params.AWS_REGION) {
                    script {
                        def dryRunFlag = params.DRY_RUN ? '--dry-run=client' : ''

                        sh "kubectl create namespace ${params.KUBERNETES_NAMESPACE} --dry-run=client -o yaml | kubectl apply -f -"

                        def manifests = [
                            'kubernetes/grafana-deployment.yaml',
                            'kubernetes/grafana-service.yaml',
                            'kubernetes/prometheus-deployment.yaml',
                            'kubernetes/prometheus-service.yaml',
                            'kubernetes/prometheus-configmap.yaml',
                            'kubernetes/prometheus-rules.yaml',
                            'kubernetes/prometheus-datasource.yaml',
                            'kubernetes/prometheus-dashboard-provider.yaml',
                            'kubernetes/prometheus-dashboards.yaml',
                            'kubernetes/network-policy.yaml'
                        ]

                        manifests.each { manifest ->
                            sh "kubectl apply -f ${manifest} -n ${params.KUBERNETES_NAMESPACE} ${dryRunFlag}"
                        }

                        echo "Deploy dos manifests concluído no namespace ${params.KUBERNETES_NAMESPACE}."
                    }
                }
            }
        }
    }

    post {
        always {
            cleanWs()
        }
        success {
            echo 'Deploy Kubernetes concluído com sucesso.'
        }
        failure {
            echo 'Deploy Kubernetes falhou.'
        }
    }
}
