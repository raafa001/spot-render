pipeline {
    agent any

    parameters {
        string(name: 'GIT_BRANCH', defaultValue: 'main', description: 'Branch do repositório')
        string(name: 'AWS_REGION', defaultValue: 'us-east-1', description: 'Região AWS')
        string(name: 'AWS_CREDENTIALS_ID', defaultValue: 'spot-render', description: 'ID da credencial AWS no Jenkins')
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

        stage('Validate Script') {
            steps {
                script {
                    if (!fileExists('scripts/stop-instances.sh')) {
                        error 'scripts/stop-instances.sh não encontrado!'
                    }
                }
            }
        }

        stage('Stop Instances') {
            steps {
                withAWS(credentials: params.AWS_CREDENTIALS_ID, region: params.AWS_REGION) {
                    script {
                        sh '''
                        chmod +x scripts/stop-instances.sh
                        ./scripts/stop-instances.sh
                        '''
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
            echo 'Instâncias paradas com sucesso.'
        }
        failure {
            echo 'Falha ao parar instâncias.'
        }
    }
}
