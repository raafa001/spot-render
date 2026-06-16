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
                    if (!fileExists('scripts/start-instances.sh')) {
                        error 'scripts/start-instances.sh não encontrado!'
                    }
                }
            }
        }

        stage('Start Instances') {
            steps {
                withAWS(credentials: params.AWS_CREDENTIALS_ID, region: params.AWS_REGION) {
                    script {
                        sh '''
                        chmod +x scripts/start-instances.sh
                        ./scripts/start-instances.sh
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
            echo 'Instâncias iniciadas com sucesso.'
        }
        failure {
            echo 'Falha ao iniciar instâncias.'
        }
    }
}
