pipeline {
    agent any
    stages {
        stage('Checkout') {
            steps {
                git branch: 'main',
                    credentialsId: 'github-app', // Substitua pelo ID da sua credencial do GitHub
                    url: 'https://github.com/seu-repositorio/seu-projeto.git' // Substitua pela URL do seu repositório
            }
        }
        stage('Deploy to Kubernetes') {
            steps {
                withAWS(credentials: 'aws-credentials', region: 'sua-regiao-aws') { // Substitua pelo ID da sua credencial AWS e sua região
                    script {
                        sh 'kubectl apply -f deployment.yaml'
                        sh 'kubectl apply -f service.yaml'
                    }
                }
            }
        }
    }
}
